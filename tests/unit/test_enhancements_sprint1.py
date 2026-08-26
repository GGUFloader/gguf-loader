"""Sprint-1 enhancements: stop holdback, context fit, GPU honesty, GGUF limits."""

import struct

from ggufloader.core.llm.model_backend import holdback_stream
from ggufloader.core.llm.model_profiles import (
    read_gguf_general_metadata,
    read_model_limits,
)


# ---------------------------------------------------------------------------
# A1: stop-string partial-match holdback
# ---------------------------------------------------------------------------

def collect(chunks, stops):
    return "".join(holdback_stream(iter(chunks), stops))


def test_holdback_passthrough_without_stops():
    assert collect(["a", "b"], []) == "ab"


def test_holdback_releases_complete_stop_tail():
    out = collect(["Hello <|im_end", "|>bye"], ["<|im_end|>"])
    assert out == "Hello bye"


def test_holdback_withholds_split_prefix_then_resolves():
    chunks = ["answer<|im_", "end|>next"]
    out = collect(chunks, ["<|im_end|>"])
    # The complete stop is dropped; text after it continues.
    assert out.startswith("answer")
    assert "<|im_" not in out


def test_holdback_flushes_non_stop_tail():
    assert collect(["abc"], ["<|endoftext|>"]) == "abc"


def test_holdback_never_leaks_partial_across_boundary():
    text = "keep this <|return|>tail"
    out = collect([text], ["<|return|>"])
    assert "keep this" in out and "<|return|>" not in out


# ---------------------------------------------------------------------------
# A2: context-fit trimming
# ---------------------------------------------------------------------------

class FakeBackend:
    """count_tokens = words; n_ctx small for tests."""

    def __init__(self, n_ctx=100):
        self.n_ctx_value = n_ctx

    @property
    def n_ctx(self):
        return self.n_ctx_value

    def count_tokens(self, text):
        return len(text.split())


def _fit(messages, params, backend=None):
    from types import SimpleNamespace
    from ggufloader.ui.main_window import MainWindow
    backend = backend or FakeBackend()
    win = SimpleNamespace(
        chat_panel=type("CP", (), {"add_system_message": staticmethod(lambda t: None)})(),
        _model_service=SimpleNamespace(backend=backend),
    )
    return MainWindow._fit_messages_to_context(win, messages, params)


def _make_window():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from ggufloader.ui.main_window import MainWindow
    win = MainWindow.__new__(MainWindow)
    win.chat_panel = type("CP", (), {"add_system_message": staticmethod(lambda t: None)})()
    return win


def test_fit_returns_untouched_when_within_budget():
    msgs = [{"role": "system", "content": "sys"},
            {"role": "user", "content": "one two"},
            {"role": "assistant", "content": "three"}]
    out, trimmed, too_long = _fit(msgs, {"max_tokens": 32})
    assert out == msgs and trimmed is False and too_long is False


def test_fit_trims_oldest_turns_first():
    long = "word " * 50
    msgs = [{"role": "system", "content": "sys"}]
    for i in range(4):
        msgs.append({"role": "user", "content": f"u{i} {long}"})
        msgs.append({"role": "assistant", "content": f"a{i} " + "x " * 10})
    msgs.append({"role": "user", "content": "new question here"})
    out, trimmed, too_long = _fit(msgs, {"max_tokens": 16}, backend=FakeBackend(n_ctx=300))
    contents = [m["content"] for m in out]
    assert trimmed is True and too_long is False
    assert "new question here" in contents[-1]
    assert not any("u0" in c for c in contents)  # oldest turn dropped


def test_fit_flags_too_long_single_message():
    huge = "word " * 500  # way over n_ctx=100 minus budget
    msgs = [{"role": "system", "content": "sys"},
            {"role": "user", "content": huge}]
    out, trimmed, too_long = _fit(msgs, {"max_tokens": 16})
    assert too_long is True and trimmed is False


# ---------------------------------------------------------------------------
# B1: gpu_status honesty
# ---------------------------------------------------------------------------

def test_gpu_status_reports_cpu_fallback():
    from ggufloader.core.llm.model_backend import ModelBackend
    b = ModelBackend("fake.gguf", use_gpu=True)
    b._llama = object()  # pretend loaded; probe will report build support
    status = b.gpu_status
    assert status["requested"] is True
    assert status["state"] in ("gpu", "cpu_fallback")  # env-dependent probe


def test_gpu_status_cpu_by_choice():
    from ggufloader.core.llm.model_backend import ModelBackend
    b = ModelBackend("fake.gguf", use_gpu=False)
    b._llama = object()
    s = b.gpu_status
    assert s["state"] == "cpu_by_choice" and "toggled off" in s["reason"]


# ---------------------------------------------------------------------------
# B3: GGUF context_length / block_count parsing
# ---------------------------------------------------------------------------

def _kv_u32(key: str, val: int) -> bytes:
    k = key.encode()
    return struct.pack("<Q", len(k)) + k + struct.pack("<I", 4) + struct.pack("<I", val)


def _kv_str(key: str, val: str) -> bytes:
    k = key.encode()
    v = val.encode()
    return struct.pack("<Q", len(k)) + k + struct.pack("<I", 8) + \
        struct.pack("<Q", len(v)) + v


def test_read_model_limits(tmp_path):
    kvs = (_kv_str("general.architecture", "lfm2moe")
           + _kv_u32("lfm2moe.context_length", 32768)
           + _kv_u32("lfm2moe.block_count", 32)
           + _kv_str("general.name", "LFM2.5-8B"))
    blob = (b"GGUF" + struct.pack("<I", 3) + struct.pack("<Q", 1)
            + struct.pack("<Q", 4) + kvs)
    p = tmp_path / "m.gguf"
    p.write_bytes(blob)
    meta = read_gguf_general_metadata(p)
    assert meta["architecture"] == "lfm2moe"
    limits = read_model_limits(p)
    assert limits == {"max_context": 32768, "layers": 32}
