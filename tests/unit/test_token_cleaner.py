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