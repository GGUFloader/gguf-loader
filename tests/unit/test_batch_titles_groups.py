"""Batch: code-card segmentation, date buckets, embedding flag."""

from datetime import datetime, timedelta

from ggufloader.widgets.chat_bubble import split_code_segments
from ggufloader.ui.sidebar_panel import SettingsSidebar


def test_split_no_fence():
    assert split_code_segments("plain answer") == [("md", "plain answer")]


def test_split_single_closed_fence():
    segs = split_code_segments("before```python\nprint(1)\n```after")
    assert segs[0] == ("md", "before")
    assert segs[1] == ("code", ("python", "print(1)\n"))
    assert segs[2] == ("md", "after")


def test_split_unclosed_fence_keeps_content():
    segs = split_code_segments("intro\n```js\nlet x = 1;")
    assert segs[-1] == ("code", ("js", "let x = 1;"))


def test_split_multiple_and_langless():
    segs = split_code_segments("```\nraw\n```mid```rust\nfn(){}")
    kinds = [k for k, _ in segs]
    assert kinds == ["code", "md", "code"]
    assert segs[0] == ("code", ("", "raw\n"))
    assert segs[2] == ("code", ("rust", "fn(){}"))


def test_date_buckets():
    now = datetime.now()
    f = SettingsSidebar._date_bucket
    assert f(now.isoformat()) == "Today"
    assert f((now - timedelta(days=1)).isoformat()) == "Yesterday"
    assert f((now - timedelta(days=5)).isoformat()) == "This week"
    assert f((now - timedelta(days=12)).isoformat()) == "This month"
    assert f((now - timedelta(days=400)).isoformat()) == str(now.year - 1 if now.month <= 6 and (now - timedelta(days=400)).year != now.year else str((now - timedelta(days=400)).year))
    assert f("garbage") == "Older"


def test_embedding_flag_in_profile(tmp_path, monkeypatch):
    from ggufloader.core.llm import model_params as mp
    from ggufloader.core.llm.model_profiles import resolve_chat_config
    monkeypatch.setattr(mp, "_candidate_files", lambda: [])
    # Build a tiny GGUF header with an embedding arch + name.
    import struct

    def kv_s(k, v):
        kb, vb = k.encode(), v.encode()
        return struct.pack("<Q", len(kb)) + kb + struct.pack("<I", 8) + \
            struct.pack("<Q", len(vb)) + vb

    blob = (b"GGUF" + struct.pack("<I", 3) + struct.pack("<Q", 0)
            + struct.pack("<Q", 3)
            + kv_s("general.architecture", "nomic-bert")
            + kv_s("general.name", "nomic-embed-text-v1.5")
            + kv_s("general.basename", "nomic-embed-text-v1.5"))
    p = tmp_path / "embed.gguf"
    p.write_bytes(blob)
    cfg = resolve_chat_config(str(p))
    assert cfg["is_embedding_model"] is True
