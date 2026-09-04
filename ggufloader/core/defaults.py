"""Canonical defaults — the single table of performance constants.

Every module in the app must import its load/sampling/stops defaults from
here instead of declaring magic numbers. If a default ever needs to change,
it changes in exactly one place.

Reference rig this was tuned against: the pinned single model, Gemma 4 12B
Instruct Q4_K_M. Official Gemma 4 chat sampling is temperature 1.0 /
top_p 0.95 / top_k 64, but 4-bit quantization measurably degrades that
regime into repetition attractors, so the agent lanes below trade a little
of the official temperature for anti-degeneration headroom: purpose temps
sit well below 1.0 and every agent role carries a repeat-penalty floor
(see router.route()). Context budgets stay conservative so a runaway
loop burns tokens without filling the window.
"""

# Context / batch -----------------------------------------------------------
DEFAULT_CTX = 8192
CTX_OPTIONS = (2048, 4096, 8192, 16384, 32768)
N_BATCH_DEFAULT = 512

# Sampling ------------------------------------------------------------------
# Purpose-selected temperatures for the agent (Gemma 4 12B Q4_K_M tuned).
#   action: structured JSON (plans / tool calls). Near-greedy, but not
#           ultra-low: below ~0.2 a 4-bit model can freeze into a repeated
#           key/action loop instead of choosing the next step.
#   answer: final prose. Official chat temp (1.0) drifts into repetition
#           on Q4_K_M; 0.7 keeps answers fluent without the attractor.
TEMP_ACTION = 0.25       # tool-call/planning decisions: near-greedy JSON
TEMP_ANSWER = 0.7        # final prose answers: mild creativity
# Anti-degeneration floor for quantized structured/agent output (applied by
# router.route() to the AGENT role and used as llm_factory's fallback).
# Community Gemma-4 Q4_K_M guidance lands repeat penalty in 1.15-1.25.
REPEAT_PENALTY_FLOOR = 1.15
MAX_TOKENS_CHAT = 4096
MAX_TOKENS_AGENT_ACTION = 2048   # cap per action/plan call: bounds JSON loops
MAX_TOKENS_AGENT_ANSWER = 4096   # cap per prose answer call

# Memory headroom -----------------------------------------------------------
VRAM_HEADROOM = 0.85     # usable fraction of VRAM for model+KV
RAM_HEADROOM = 0.8       # usable fraction of RAM for model+KV
CUDA_RESERVE_GB = 1.0    # VRAM reserved for CUDA context / activations

# Stop tokens ---------------------------------------------------------------
# Unified across chat, agent, and both UIs. Never add bare lowercase
# "user:" / "assistant:" markers here — they truncate mid-word in prose.
STOP_TOKENS_UNIFIED = [
    "<|im_end|>", "<|endoftext|>", "<|eot_id|>", "</s>",
    "<|end_of_text|>", "<|return|>",
    "<end_of_turn>", "<start_of_turn>",
]
