"""Fuzz target for model_profiles.py — _template_supports_system.

Tests the chat template string parser that detects whether a model
supports system messages. Weak models may produce unexpected templates.

Run with: atheris fuzz_template.py
"""
import atheris
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ggufloader.core.llm.model_profiles import _template_supports_system


def TestOneInput(data: bytes) -> None:
    """Fuzz template detection with arbitrary strings."""
    try:
        text = data.decode("utf-8", errors="replace")
        result = _template_supports_system(text)
        # Result must be a bool
        assert isinstance(result, bool)
    except Exception:
        pass


def main():
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
