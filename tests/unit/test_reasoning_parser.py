"""Tests for the reasoning stream parser (all headless)."""

from ggufloader.core.reasoning import ReasoningStreamParser, split_reasoning, strip_markers


def run(parser, chunk=None):
    """Feed chunk(s), finish, and return (thought, answer) strings."""
    thoughts, answers = [], []
    chunks = [chunk] if isinstance(chunk, str) else (chunk or [])
    for c in chunks:
        for kind, text in parser.feed(c):
            (thoughts if kind == "thought" else answers).append(text)
    for kind, text in parser.finish():
        (thoughts if kind == "thought" else answers).append(text)
    return "".join(thoughts).strip(), "".join(answers).strip()


def test_plain_text_is_answer():
    assert split_reasoning("Just a normal reply.") == ("", "Just a normal reply.")


def test_think_tags():
    t, a = split_reasoning("<think>private chain</think>Visible answer")
    assert t == "private chain"
    assert a == "Visible answer"


def test_thinking_variant():
    t, a = split_reasoning("<thinking>hmm ok</thinking>Answer!")
    assert t == "hmm ok" and a == "Answer!"


def test_unclosed_think_all_thought():
    t, a = split_reasoning("<think>never closed still thinking")
    assert t == "never closed still thinking"
    assert a == ""


def test_harmony_full_sequence():
    raw = ("<|start|>assistant<|channel|>analysis<|message|>reason here<|end|>"
           "<|start|>assistant<|channel|>final<|message|>Final words")
    t, a = split_reasoning(raw)
    assert t == "reason here"
    assert a == "Final words"


def test_harmony_final_only():
    t, a = split_reasoning("assistant<|channel|>final<|message|>Hello there")
    assert t in ("", "assistant")  # preamble scrubbed or empty
    assert a == "Hello there"


def test_dropped_pipe_variants():
    t, a = split_reasoning("<channel|>analysis<message|>why<|end|><|channel|>final<|message|>So")
    assert t == "why" and a == "So"


def test_stray_prefix_before_marker_joins_thought():
    # The exact artifact reported from the UI: leading word then channel tag.
    t, a = split_reasoning("thought<|channel|>final<|message|>I'm doing well!")
    assert "thought" in t
    assert a == "I'm doing well!"


def test_char_by_char_streaming():
    raw = "<think>abc def</think>The answer"
    p = ReasoningStreamParser()
    t, a = run(p, list(raw))          # one char at a time
    assert t == "abc def" and a == "The answer"


def test_split_across_tag_boundary():
    raw = "<thi nk>".replace(" ", "") + "in</think>out"
    p = ReasoningStreamParser()
    t, a = run(p, ["<th", "ink>", "in</thi", "nk>", "out"])
    assert t == "in" and a == "out"


def test_stop_tag_terminates_answer():
    t, a = split_reasoning("<|channel|>final<|message|>Answer text<|return|>")
    assert a == "Answer text"


def test_strip_markers():
    assert strip_markers("<think>x</think>clean") == "clean"


def test_missing_open_tag_close_only_streaming():
    """<think> decodes to empty (special token); </think> arrives as text."""
    p = ReasoningStreamParser()
    t, a = run(p, list("[SYS] junk reasoning about numbers </think>Real answer"))
    assert "junk" in t and "SYS" in t
    assert a == "Real answer"


def test_missing_open_tag_word_chunks():
    raw = ("The user wants the product. Let's compute it step by step. "
           "</think>\n454,708,228,458,330")
    t, a = split_reasoning(raw)
    assert a == "454,708,228,458,330"
    assert "product" in t


def test_format_answer_unwraps_boxed():
    from ggufloader.core.reasoning import format_answer
    assert format_answer("\\boxed{454,708,228,458,330}") == "454,708,228,458,330"
    assert format_answer("Result: \\boxed{42} done") == "Result: 42 done"
    assert format_answer("a\\boxed{b\\boxed{c}}") == "abc"
    assert format_answer("plain\n\n\n\nanswer") == "plain\n\nanswer"


def test_format_answer_strips_template_artifacts():
    from ggufloader.core.reasoning import format_answer
    junk = ('</INST>5940354 × 76545645</s><</SYS>\n'
            '</</SYS>\n<s>[INST]2345*6543=?</s> real words remain')
    cleaned = format_answer(junk)
    assert cleaned == "5940354 × 76545645\n2345*6543=? real words remain", repr(cleaned)
    assert "SYS" not in cleaned and "INST" not in cleaned
    assert "<s>" not in cleaned and "</" not in cleaned
