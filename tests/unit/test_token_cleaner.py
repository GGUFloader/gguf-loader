from ggufloader.core.agent.token_cleaner import get_cleaner


def test_gemma4_cleaner_strips_channel_name_leakage():
    cleaner = get_cleaner("gemma4")
    raw = "<|channel|>analysis<|message|>thinking<|channel|>final<|message|>A is the first letter of the alphabet.<|end|>"
    cleaned = cleaner.clean(raw)
    assert "analysis" not in cleaned, f"leaked channel name: {cleaned!r}"
    assert "final" not in cleaned, f"leaked channel name: {cleaned!r}"
    assert "<|" not in cleaned
    assert "A is the first letter of the alphabet." in cleaned


def test_gemma4_cleaner_preserves_plain_text():
    cleaner = get_cleaner("gemma4")
    assert cleaner.clean("A is the first letter of the alphabet.") == "A is the first letter of the alphabet."


def test_gemma4_cleaner_preserves_json():
    cleaner = get_cleaner("gemma4")
    raw = '{"answer": "A is the first letter."}'
    assert cleaner.clean(raw) == raw


def test_gemma4_cleaner_strips_start_end_turn_markers():
    cleaner = get_cleaner("gemma4")
    raw = "<|start|>assistant\nA is the first letter.<|end|>"
    cleaned = cleaner.clean(raw)
    assert "assistant" not in cleaned
    assert "A is the first letter." in cleaned

# ---------------------------------------------------------------------------
# Task 8: true Gemma turn tokens clean BEFORE json parse
# ---------------------------------------------------------------------------

def test_gemma_turn_tokens_leave_no_residue():
    from ggufloader.core.agent.token_cleaner import GemmaCleaner
    c = GemmaCleaner()
    out = c.clean('<start_of_turn>user\n{"answer": "hi"}<end_of_turn>')
    assert out.strip() == '{"answer": "hi"}'
    assert "user" not in out.replace('"answer"', "")


def test_request_action_cleans_before_parse():
    """The JSON parser must never see raw turn/channel markers."""
    import inspect
    from ggufloader.core.agent.graph_agent import GraphAgent
    src = inspect.getsource(GraphAgent._request_action)
    # Every parse site feeds the CLEANED text: extract_json(self._clean(raw))
    # (first try + each retry => at least two sites).
    assert src.count("extract_json(self._clean(raw))") >= 2
