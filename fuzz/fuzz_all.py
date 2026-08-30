"""Interleaved fuzz target — exercises all entry points in a single harness.

The first byte selects which target to fuzz, giving the fuzzer a shared
corpus that may find interesting cross-target inputs.

Run with: atheris fuzz_all.py
"""
import atheris
import sys
import os
import pathlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ggufloader.core.agent.text_extract import (
    _docx_text,
    _minimal_pdf_text,
    _extract_text_operators,
    _unescape_pdf_string,
)
from ggufloader.core.agent.agent_engine import extract_json
from ggufloader.core.llm.model_profiles import _template_supports_system


def TestOneInput(data: bytes) -> None:
    """Route fuzzed bytes to the appropriate target."""
    if len(data) < 2:
        return

    mode = data[0] % 6
    payload = data[1:]

    try:
        if mode == 0:
            _docx_text(payload)
        elif mode == 1:
            _minimal_pdf_text(payload)
        elif mode == 2:
            text = payload.decode("latin-1", errors="replace")
            _extract_text_operators(text)
        elif mode == 3:
            text = payload.decode("latin-1", errors="replace")
            _unescape_pdf_string(text)
        elif mode == 4:
            text = payload.decode("utf-8", errors="replace")
            extract_json(text)
        elif mode == 5:
            text = payload.decode("utf-8", errors="replace")
            _template_supports_system(text)
    except Exception:
        pass


def main():
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
