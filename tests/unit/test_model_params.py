"""Per-model chat parameter overrides."""

import json

from ggufloader.core.llm.model_params import load_model_params


def test_exact_substring_match(tmp_path):
    f = tmp_path / "model_params.json"
    f.write_text(json.dumps({
        "lfm2.5": {"temperature": 0.2, "top_k": 80, "repeat_penalty": 1.05},
        "qwen3": {"temperature": 0.6},
    }), encoding="utf-8")
    got = load_model_params(r"F:\models\LFM2.5-8B-Q4_K_M.gguf", overrides_file=f)
    assert got == {"temperature": 0.2, "top_k": 80, "repeat_penalty": 1.05}
    assert load_model_params(r"F:\models\Qwen3-4B.gguf", overrides_file=f) == {
        "temperature": 0.6
    }


def test_no_match_returns_empty(tmp_path):
    f = tmp_path / "model_params.json"
    f.write_text(json.dumps({"lfm2.5": {"temperature": 0.2}}), encoding="utf-8")
    assert load_model_params(r"F:\models\gemma-3-12b.gguf", overrides_file=f) == {}


def test_missing_file_returns_empty(tmp_path):
    assert load_model_params("x.gguf", overrides_file=tmp_path / "nope.json") == {}


def test_invalid_entries_ignored(tmp_path):
    f = tmp_path / "model_params.json"
    f.write_text(json.dumps({
        "lfm": {"temperature": "hot", "top_k": 80, "bogus": 1},  # bad value/key dropped
    }), encoding="utf-8")
    assert load_model_params("lfm.gguf", overrides_file=f) == {"top_k": 80}


def test_corrupt_json_returns_empty(tmp_path):
    f = tmp_path / "model_params.json"
    f.write_text("{broken", encoding="utf-8")
    assert load_model_params("lfm.gguf", overrides_file=f) == {}
