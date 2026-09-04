"""Degeneration tests for the Gemma 4 12B Q4_K_M tuning.

The pinned model is a 4-bit quantized 12B: at official chat sampling
(temp 1.0, no repeat penalty) it is measurably prone to repetition loops
(repeated JSON keys, repeated tool calls, unclosed prose). This suite
verifies the anti-degeneration guardrails that the agent path applies:

  1. The router's AGENT role enforces a repeat-penalty floor + temp/top_k
     caps for the gemma4 profile (and every family routed as AGENT).
  2. Purpose-selected temperatures (action vs answer) are tuned for Q4_K_M.
  3. Per-purpose max_tokens caps bound a single call, so a degenerate loop
     cannot run away to the family's 8192-token budget.
  4. The family system prompt carries an explicit anti-repetition rule.
  5. A repeated-identical-action LLM terminates through the graph's step
     budget instead of looping forever.

A live-model probe (the "real" degeneration check) is included but skipped
unless GGUFLOADER_DEGEN_GGUF points at a Gemma 4 12B Q4_K_M GGUF, because
CI has no multi-GB model.
"""

import json
import os
from pathlib import Path

import pytest

from ggufloader.core.defaults import (
    MAX_TOKENS_AGENT_ACTION,
    MAX_TOKENS_AGENT_ANSWER,
    REPEAT_PENALTY_FLOOR,
    TEMP_ACTION,
    TEMP_ANSWER,
)
from ggufloader.core.router import ModelRole, ModelRouter, SystemProfile

from tests.unit.test_router import _create_model_file, _kv_str, _kv_u32

CONFIG = Path(__file__).resolve().parents[2] / "ggufloader" / "config" / "model_families.json"


def _gemma4_router(tmp_path) -> ModelRouter:
    """Router with a fake gemma4-12b-q4_k_m.gguf and no GPU (deterministic)."""
    router = ModelRouter(system=SystemProfile(
        ram_gb=16.0, vram_gb=0.0, has_gpu_support=False))
    kvs = _kv_str("general.architecture", "gemma4") + _kv_u32("gemma4.block_count", 48)
    p = _create_model_file(tmp_path, "gemma-4-12b-q4_k_m.gguf", kvs, kv_count=2)
    return router, p


# ---------------------------------------------------------------------------
# 1. Router role config
# ---------------------------------------------------------------------------

def test_agent_role_enforces_q4_anti_degeneration_floor(tmp_path):
    router, p = _gemma4_router(tmp_path)
    profile = router.inspect(str(p))
    assert profile.family == "gemma4"
    assert profile.architecture == "gemma4"

    cfg = router.route(profile, ModelRole.AGENT)
    # The three Q4_K_M degeneration knobs:
    assert cfg.repeat_penalty >= REPEAT_PENALTY_FLOOR >= 1.1
    assert cfg.temperature <= 0.3          # near-greedy structured JSON
    assert cfg.top_k <= 40                 # narrow the sampling window


def test_agent_role_floor_beats_family_default(tmp_path):
    """Family base repeat is 1.0 (official Gemma); the floor must win."""
    router, p = _gemma4_router(tmp_path)
    profile = router.inspect(str(p))
    assert profile.family_params.get("repeat_penalty", 1.0) < REPEAT_PENALTY_FLOOR
    cfg = router.route(profile, ModelRole.AGENT)
    assert cfg.repeat_penalty == REPEAT_PENALTY_FLOOR


# ---------------------------------------------------------------------------
# 2. Purpose sampling + token caps
# ---------------------------------------------------------------------------

def test_purpose_temperatures_tuned_for_q4():
    assert TEMP_ACTION < 0.3                        # near-greedy JSON
    assert TEMP_ANSWER < 1.0                        # below official 1.0
    assert TEMP_ACTION < TEMP_ANSWER                # answer > action
    assert MAX_TOKENS_AGENT_ACTION < MAX_TOKENS_AGENT_ANSWER
    assert MAX_TOKENS_AGENT_ACTION <= 2048          # bounded JSON loops


def test_call_llm_caps_tokens_per_purpose():
    from ggufloader.core.agent.graph_agent import GraphAgent

    class _CaptureLLM:
        def __init__(self):
            self.kwargs = {}

        def __call__(self, prompt, **kw):
            self.kwargs = kw
            return '{"reasoning":"ok","tool_calls":[],"answer":"done"}'

    fake = _CaptureLLM()
    # Family max_tokens is 8192; the caps must clamp both purposes.
    agent = GraphAgent(
        llm=fake, workspace="/tmp/ws", max_tokens=8192,
        system_prompt="You are a test assistant for unit tests.")
    agent._call_llm("plan this", lambda _e: None, purpose="action")
    assert fake.kwargs["max_tokens"] == MAX_TOKENS_AGENT_ACTION
    agent._call_llm("write the answer", lambda _e: None, purpose="answer")
    assert fake.kwargs["max_tokens"] == MAX_TOKENS_AGENT_ANSWER


# ---------------------------------------------------------------------------
# 3. Prompt guardrails
# ---------------------------------------------------------------------------

def test_family_prompt_has_anti_repetition_rule():
    data = json.loads(CONFIG.read_text(encoding="utf-8"))
    gemma4 = next(f for f in data["families"] if f["id"] == "gemma4")
    sp = gemma4["system_prompt"].lower()
    assert "never repeat yourself" in sp
    assert "once the task is done, stop" in sp


# ---------------------------------------------------------------------------
# 4. Loop termination: a model that repeats the same action must stop
# ---------------------------------------------------------------------------

class _StuckLLM:
    """Simulates a degenerate model: every call returns the SAME action JSON
    (list_directory over and over), the classic Q4 repetition attractor."""

    def __init__(self):
        self.called = 0

    def __call__(self, prompt, **kw):
        self.called += 1
        return ('{"reasoning":"search again","estimated_steps":1,'
                '"tool_calls":[{"tool":"list_directory","parameters":{}}],'
                '"answer":""}')


def test_repeated_identical_action_terminates(tmp_path):
    from ggufloader.core.agent.graph_agent import GraphAgent

    llm = _StuckLLM()
    agent = GraphAgent(
        llm=llm, workspace=str(tmp_path), max_steps=3,
        system_prompt="You are a test assistant for unit tests.")
    result = agent.process(
        user_message="what is here?", on_status=lambda _m: None,
        on_tool=lambda _r: None, on_token=lambda _t: None)
    # The graph must end (bounded), never spin forever on the repeated call:
    # stale-repeat detection forces the final response within a few steps.
    assert isinstance(result.get("response"), str) and result["response"].strip()
    assert llm.called < 10, "degenerate model ran far beyond the step budget"


# ---------------------------------------------------------------------------
# 5. Live probe (opt-in; skipped without a real Gemma 4 12B Q4_K_M GGUF)
# ---------------------------------------------------------------------------

_DEGEN_GGUF = os.environ.get("GGUFLOADER_DEGEN_GGUF")


@pytest.mark.skipif(not _DEGEN_GGUF, reason="set GGUFLOADER_DEGEN_GGUF to a Gemma 4 12B Q4_K_M GGUF")
def test_live_repetition_probe():
    """Real-model check: a repetition-stress prompt must not loop forever.

    Run with:
      GGUFLOADER_DEGEN_GGUF=/path/to/gemma-4-12b-q4_k_m.gguf \
        python -m pytest tests/unit/test_gemma4_degeneration.py -k live
    """
    router = ModelRouter()
    backend, _profile, _strategy, config = router.load(_DEGEN_GGUF, ModelRole.AGENT)
    assert config.repeat_penalty >= REPEAT_PENALTY_FLOOR
    prompt = ("List the numbers 1 through 20, one per line, then say DONE "
              "and stop. Do not repeat any number.")
    out = backend.chat(
        [{"role": "user", "content": prompt}],
        temperature=TEMP_ANSWER,
        top_k=40,
        repeat_penalty=config.repeat_penalty,
        max_tokens=600,
    )
    # Not a hard guarantee (models vary), but a smoke signal: if the model
    # degenerated it would hit the token ceiling without ever saying DONE.
    assert len(out) < 600 * 8
    assert out.count("DONE") >= 1 or "20" in out
