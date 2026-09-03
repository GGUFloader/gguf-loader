"""Task 4: the router forwards the whole strategy and owns the ladder.

ModelBackend must be a pure executor: given n_gpu_layers it tries exactly
once. ModelRouter.load() walks full → partial → CPU and records every
attempt on strategy.attempts.
"""

import pytest

from ggufloader.core.router import ModelProfile, ModelRouter, SystemProfile


class FakeBackend:
    """Records construction kwargs; fails N times then succeeds."""

    instances = []
    failures_before_success = 0

    def __init__(self, path, **kw):
        self.path = path
        self.kw = kw
        FakeBackend.instances.append(self)

    def load(self):
        if len(FakeBackend.instances) <= FakeBackend.failures_before_success:
            raise RuntimeError("CUDA out of memory")
        return self


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch):
    FakeBackend.instances = []
    FakeBackend.failures_before_success = 0
    monkeypatch.setattr(
        "ggufloader.core.llm.model_backend.ModelBackend", FakeBackend)


def _gemma_profile(tmp_path):
    # Router inspects the file; build a minimal GGUF so inspect() works.
    import struct
    kvs = b""
    for key, val in (("general.architecture", "gemma3"),
                     ("general.name", "gemma-3-8b-it")):
        k = key.encode(); v = val.encode()
        kvs += (struct.pack("<Q", len(k)) + k + struct.pack("<I", 8)
                + struct.pack("<Q", len(v)) + v)
    for key, val in (("gemma3.context_length", 8192),
                     ("gemma3.block_count", 32)):
        k = key.encode()
        kvs += struct.pack("<Q", len(k)) + k + struct.pack("<I", 4) + struct.pack("<I", val)
    p = tmp_path / "gemma-3-8b-it-Q4_K_M.gguf"
    p.write_bytes(b"GGUF" + struct.pack("<I", 3) + struct.pack("<Q", 1)
                  + struct.pack("<Q", 4) + kvs + b"\x00" * 64)
    return str(p)


def test_load_forwards_full_strategy(tmp_path):
    r = ModelRouter(system=SystemProfile(ram_gb=32.0, vram_gb=24.0,
                                         has_gpu_support=True))
    path = _gemma_profile(tmp_path)
    backend, profile, strategy, config = r.load(path)
    seen = FakeBackend.instances[-1].kw
    assert seen["use_gpu"] is True
    assert seen["n_ctx"] == strategy.n_ctx
    assert seen["n_gpu_layers"] == strategy.n_gpu_layers
    assert seen["n_batch"] == strategy.batch_size
    assert seen["use_mmap"] is strategy.use_mmap
    assert seen["flash_attn"] is strategy.flash_attn
    assert "full_gpu" in strategy.attempts


def test_load_ladder_records_each_attempt(tmp_path):
    FakeBackend.failures_before_success = 2  # full + partial fail, CPU wins
    r = ModelRouter(system=SystemProfile(ram_gb=32.0, vram_gb=24.0,
                                         has_gpu_support=True))
    path = _gemma_profile(tmp_path)
    backend, _p, strategy, _c = r.load(path)
    assert strategy.attempts == ["full_gpu", "partial_gpu", "cpu"]
    # The CPU attempt shrank ctx and disabled flash attention.
    last = FakeBackend.instances[-1].kw
    assert last["use_gpu"] is False
    assert last["n_gpu_layers"] == 0
    assert last["flash_attn"] is False
    assert last["n_ctx"] <= 8192


def test_load_raises_with_suggestion_after_all_attempts(tmp_path):
    FakeBackend.failures_before_success = 999
    r = ModelRouter(system=SystemProfile(ram_gb=32.0, vram_gb=24.0,
                                         has_gpu_support=True))
    path = _gemma_profile(tmp_path)
    with pytest.raises(RuntimeError, match="after 3 attempt"):
        r.load(path)
    assert len(FakeBackend.instances) == 3


def test_cpu_only_strategy_single_attempt(tmp_path):
    r = ModelRouter(system=SystemProfile(ram_gb=32.0, vram_gb=0.0,
                                         has_gpu_support=False))
    path = _gemma_profile(tmp_path)
    backend, _p, strategy, _c = r.load(path)
    assert strategy.attempts == ["cpu"]
    assert FakeBackend.instances[-1].kw["use_gpu"] is False
