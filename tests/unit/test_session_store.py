"""Headless tests for the chat session store."""

import json

import pytest

from ggufloader.core.sessions import SessionStore, derive_title


@pytest.fixture()
def store(tmp_path):
    return SessionStore(tmp_path / "chats")


def test_create_defaults(store):
    s = store.create()
    assert s["version"] == 1
    assert s["mode"] == "chat"
    assert s["workspace"] is None
    assert s["title"] is None
    assert s["messages"] == []
    assert s["id"]


def test_save_load_round_trip(store):
    s = store.create("agent", workspace="w")
    store.append_message(s, "user", "hello world")
    store.append_tool_result(s, {"tool_name": "list_directory", "status": "success"})
    store.append_message(s, "assistant", "done")
    store.save(s)

    loaded = store.load(s["id"])
    assert loaded == s
    assert loaded["messages"][1]["tool_result"]["tool_name"] == "list_directory"


def test_save_is_atomic_no_tmp_residue(store):
    s = store.create()
    store.save(s)
    files = [p.name for p in store.root.iterdir()]
    assert f"{s['id']}.json" in files
    assert not any(name.endswith(".tmp") for name in files)


def test_list_sessions_sorted_by_updated_desc(store):
    a = store.create(); store.save(a)
    b = store.create(); store.save(b)
    metas = store.list_sessions()
    assert [m["id"] for m in metas] == [b["id"], a["id"]]


def test_list_reports_corrupt_file_without_raising(store):
    good = store.create(); store.save(good)
    (store.root / "broken.json").write_text("{not json", encoding="utf-8")
    metas = {m["id"]: m for m in store.list_sessions()}
    assert "corrupt" not in metas[good["id"]]
    assert metas["broken"]["corrupt"] is True
    assert "error" in metas["broken"]


def test_delete_removes_file_and_returns_false_when_missing(store):
    s = store.create(); store.save(s)
    assert store.delete(s["id"]) is True
    assert store.load(s["id"]) is None
    assert store.delete(s["id"]) is False


def test_rename_persists_and_allows_clearing_to_auto(store):
    s = store.create()
    store.append_message(s, "user", "first message sets title")
    store.save(s)
    assert store.rename(s["id"], "My custom title") is True
    assert store.load(s["id"])["title"] == "My custom title"
    assert store.rename(s["id"], "   ") is True  # empty -> back to None
    assert store.load(s["id"])["title"] is None
    assert store.rename("missing-id", "x") is False


def test_append_message_sets_title_from_first_user_message_only(store):
    s = store.create()
    store.append_message(s, "assistant", "hi there")
    assert s["title"] is None
    store.append_message(s, "user", "what is gguf?")
    assert s["title"] == "what is gguf?"
    store.append_message(s, "user", "second question")
    assert s["title"] == "what is gguf?"


def test_derive_title_truncates_at_word_boundary():
    long_text = "help me refactor the loader module because it is getting messy"
    title = derive_title(long_text, max_chars=40)
    assert len(title) <= 40
    assert title.startswith("help me refactor the loader")
    assert not title.endswith(" ")  # no trailing space after cut
    assert derive_title("short") == "short"


def test_path_rejects_traversal_ids(store):
    import pytest as _pytest
    with _pytest.raises(ValueError):
        store._path_for("../evil")
    with _pytest.raises(ValueError):
        store._path_for("")


def test_load_returns_none_for_missing(store):
    assert store.load("does-not-exist") is None


def test_saved_json_matches_schema_keys(store):
    s = store.create("chat")
    store.append_message(s, "user", "hey")
    store.save(s)
    data = json.loads((store.root / f"{s['id']}.json").read_text(encoding="utf-8"))
    assert set(data) >= {"version", "id", "title", "created", "updated",
                         "mode", "workspace", "messages"}
