"""Fuzz target for text_extract.py — PDF and DOCX parsing.

Tests the three main entry points:
- _docx_text(data) — DOCX zip+XML parsing
- _minimal_pdf_text(data) — stdlib PDF extraction
- _extract_text_operators(content) — PDF text operator regex

Run with: atheris fuzz_text_extract.py
"""
import atheris
import sys
import os

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ggufloader.core.agent.text_extract import (
    _docx_text,
    _minimal_pdf_text,
    _extract_text_operators,
    _unescape_pdf_string,
    extract_text,
)


def TestOneInput(data: bytes) -> None:
    """Fuzz all text extraction paths with raw bytes."""
    if len(data) < 1:
        return

    # Use first byte to select target
    mode = data[0] % 5
    payload = data[1:]

    if mode == 0:
        # Fuzz DOCX extraction (expects zip bytes)
        try:
            _docx_text(payload)
        except Exception:
            pass

    elif mode == 1:
        # Fuzz minimal PDF extraction (expects PDF bytes)
        try:
            _minimal_pdf_text(payload)
        except Exception:
            pass

    elif mode == 2:
        # Fuzz PDF text operator extraction (expects string)
        try:
            text = payload.decode("latin-1", errors="replace")
            _extract_text_operators(text)
        except Exception:
            pass

    elif mode == 3:
        # Fuzz PDF string unescaping (expects string)
        try:
            text = payload.decode("latin-1", errors="replace")
            _unescape_pdf_string(text)
        except Exception:
            pass

    elif mode == 4:
        # Fuzz the public extract_text API
        # Create a temp file with the right extension
        ext = b".pdf" if payload[:4] == b"%PDF" else b".docx"
        try:
            extract_text(pathlib.Path(f"dummy{ext.decode()}"), data=payload)
        except Exception:
            pass


def main():
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
