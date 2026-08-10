"""
text_extract - dependency-free text extraction for agent tools.

Reads text out of the file formats the agent can meaningfully consume:

* plain text / Markdown / code  - decoded by the registry's ``_decode_bytes``
* ``.docx``                      - zip container + ``word/document.xml`` parsed
                                   with the stdlib ``zipfile``/``ElementTree``
* ``.pdf``                       - optional ``pypdf`` when the user installs it
                                   (much higher fidelity); otherwise a minimal
                                   extractor that unzips ``FlateDecode`` content
                                   streams and pulls ``(...) Tj`` / ``[...] TJ``
                                   text-showing operators

Everything here is pure stdlib so the agent works offline with no extra
packages. ``is_binary`` is the shared NUL-byte sniff used to keep binary
garbage out of both ``read_file`` and ``search_files``.
"""

from __future__ import annotations

import io
import re
import zipfile
import zlib
from pathlib import Path
from typing import Optional

BINARY_SNIFF_LEN = 4096
MAX_EXTRACT_CHARS = 200_000  # cap extracted text so it never blows the context

# File types treated as plain text (decoded, not extracted).
TEXT_EXTENSIONS = frozenset({
    ".txt", ".md", ".rst", ".py", ".js", ".ts", ".jsx", ".tsx", ".json",
    ".csv", ".tsv", ".log", ".html", ".htm", ".css", ".scss", ".yml", ".yaml",
    ".ini", ".cfg", ".toml", ".xml", ".svg", ".sh", ".bat", ".ps1", ".sql",
    ".java", ".c", ".h", ".cpp", ".hpp", ".go", ".rs", ".rb", ".php", ".lua",
})

_UTF16_32_BOMS = (b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff", b"\xff\xfe", b"\xfe\xff")


def is_binary(data: bytes) -> bool:
    """NUL-byte sniff: real binary formats (PDFs aside) carry NULs early on."""
    return b"\x00" in data[:BINARY_SNIFF_LEN]


def looks_like_binary_text(data: bytes) -> bool:
    """True for non-text bytes that aren't a UTF-16/32 document (which legitimately has NULs)."""
    if data.startswith(_UTF16_32_BOMS):
        return False
    return is_binary(data)


def extract_text(path: Path, data: Optional[bytes] = None, max_chars: int = MAX_EXTRACT_CHARS) -> Optional[str]:
    """Return extracted text for PDF/DOCX, or None when it cannot be parsed.

    Plain-text files are NOT handled here (they go through the registry's
    decoder so encoding detection stays in one place).
    """
    if data is None:
        try:
            data = path.read_bytes()
        except OSError:
            return None
    ext = path.suffix.lower()
    if ext == ".docx":
        text = _docx_text(data)
    elif ext == ".pdf":
        text = _pdf_text(data)
    else:
        return None
    if not text:
        return None
    return text[:max_chars]


# ---------------------------------------------------------------------------
# DOCX
# ---------------------------------------------------------------------------
_DOCX_MAIN_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _docx_text(data: bytes) -> Optional[str]:
    """Extract paragraph text from a .docx (zip of OOXML parts)."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if "word/document.xml" not in archive.namelist():
                return None
            xml_bytes = archive.read("word/document.xml")
    except Exception:  # noqa: BLE001 - malformed zip
        return None
    try:
        from xml.etree import ElementTree as ET
        root = ET.fromstring(xml_bytes)
    except Exception:  # noqa: BLE001 - malformed XML
        return None

    paragraphs: list[str] = []
    for paragraph in root.iter(f"{_DOCX_MAIN_NS}p"):
        line: list[str] = []
        for element in paragraph.iter():
            tag = element.tag
            if tag == f"{_DOCX_MAIN_NS}t":
                line.append(element.text or "")
            elif tag == f"{_DOCX_MAIN_NS}tab":
                line.append("\t")
            elif tag in (f"{_DOCX_MAIN_NS}br", f"{_DOCX_MAIN_NS}cr"):
                line.append("\n")
        paragraphs.append("".join(line))
    text = "\n".join(paragraphs).strip()
    return text or None


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------
# A text-showing operator: a literal string followed by Tj/'/", or an array
# of strings (and kerning numbers) followed by TJ.
_PDF_SHOW_RE = re.compile(
    r"(\[(?:\\.|[^\[\]])*\])\s*TJ"
    r"|(\((?:\\.|[^\\()])*\))\s*(?:Tj|'|\")"
)
_PDF_LITERAL_RE = re.compile(r"\((?:\\.|[^\\()])*\)")
# Operators that move to a new text line - a hint for inserting line breaks.
_PDF_MOVE_RE = re.compile(r"(?:T[dDm*]|ET)")
_STREAM_RE = re.compile(rb"stream\r?\n(.*?)\r?\nendstream", re.DOTALL)


def _pdf_text(data: bytes) -> Optional[str]:
    """Extract text from a PDF; prefers pypdf when it is installed."""
    try:
        import pypdf  # type: ignore[import-not-found]  # optional dependency
        reader = pypdf.PdfReader(io.BytesIO(data))
        pages: list[str] = []
        for page in reader.pages:
            try:
                pages.append(page.extract_text() or "")
            except Exception:  # noqa: BLE001 - a bad page shouldn't kill the read
                continue
        text = "\n".join(pages).strip()
        if text:
            return text
    except ImportError:
        pass
    except Exception:  # noqa: BLE001 - corrupt PDF; fall back to the minimal extractor
        pass
    return _minimal_pdf_text(data)


def _minimal_pdf_text(data: bytes) -> Optional[str]:
    """Stdlib-only PDF text extraction (FlateDecode streams + Tj/TJ operators).

    Handles the common case of text PDFs with compressed or raw content
    streams. Not a full PDF parser: CID/Type3 fonts and complex encodings
    yield nothing, in which case None is returned so callers can say so.
    """
    pieces: list[str] = []
    for match in _STREAM_RE.finditer(data):
        raw = match.group(1)
        try:
            content = zlib.decompress(raw).decode("latin-1")
        except Exception:  # noqa: BLE001 - not flate-compressed; use as-is
            try:
                content = raw.decode("latin-1")
            except Exception:  # noqa: BLE001 - defensive
                continue
        text = _extract_text_operators(content)
        if text:
            pieces.append(text)
    text = "\n".join(pieces).strip()
    return text or None


def _extract_text_operators(content: str) -> str:
    """Pull the strings shown by Tj/'/\" and TJ operators, in document order."""
    out: list[str] = []
    prev_end = 0
    for match in _PDF_SHOW_RE.finditer(content):
        gap = content[prev_end:match.start()]
        if out and (_PDF_MOVE_RE.search(gap) or "\n" in gap):
            out.append("\n")
        if match.group(1):  # [...] TJ array
            for literal in _PDF_LITERAL_RE.findall(match.group(1)):
                out.append(_unescape_pdf_string(literal[1:-1]))
        else:  # (string) Tj / ' / "
            out.append(_unescape_pdf_string(match.group(2)[1:-1]))
        prev_end = match.end()
    return "".join(out)


def _unescape_pdf_string(value: str) -> str:
    """Decode PDF string escapes: \\n \\r \\t \\\\( \\\\) \\\\ and octal \\ddd."""
    def _simple(match: "re.Match[str]") -> str:
        return {"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f",
                "(": "(", ")": ")", "\\": "\\"}.get(match.group(1), match.group(1))
    value = re.sub(r"\\([nrtbf()\\])", _simple, value)
    value = re.sub(r"\\(\d{1,3})", lambda m: chr(int(m.group(1), 8)), value)
    return value.replace("\x00", "")
