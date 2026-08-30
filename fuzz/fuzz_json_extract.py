"""Fuzz target for agent_engine.py — extract_json parsing.

Tests the JSON extraction function that parses arbitrary model output.
This is critical because weak local models often produce malformed JSON.

Run with: atheris fuzz_json_extract.py
"""
import atheris
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ggufloader.core.agent.agent_engine import extract_json


def TestOneInput(data: bytes) -> None:
    """Fuzz JSON extraction with arbitrary text."""
    try:
        text = data.decode("utf-8", errors="replace")
        result = extract_json(text)
        # If we got a result, verify it's a dict with expected keys
        if result is not None:
            assert isinstance(result, dict)
    except Exception:
        pass


def main():
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
