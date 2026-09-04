"""Tests for dependency-free text extraction (PDF/DOCX) and tool wiring."""

import io
import zipfile
import zlib
from pathlib import Path

from ggufloader.core.agent.text_extract import extract_text, is_binary, looks_like_binary_text
from ggufloader.core.agent.tool_registry import ToolRegistry


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------
def make_docx(paragraphs: list[str]) -> bytes:
    ns = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    body = []
    for para in paragraphs:
        runs = []
        parts = para.split("\t")
        for i, part in enumerate(parts):
            runs.append(f'<w:r><w:t xml:space="preserve">{part}</w:t></w:r>')
            if i < len(parts) - 1:
                runs.append("<w:r><w:tab/></w:r>")
        body.append(f"<w:p>{''.join(runs)}</w:p>")
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<w:document {ns}><w:body>{"".join(body)}</w:body></w:document>'
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/'
            'package/2006/content-types"><Default Extension="xml" '
            'ContentType="application/xml"/></Types>',
        )
        archive.writestr("word/document.xml", xml)
    return buf.getvalue()


def make_pdf(content_stream: bytes, compress: bool = False) -> bytes:
    stream = zlib.compress(content_stream) if compress else content_stream
    return (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R >> endobj\n"
        b"4 0 obj << /Length "
        + str(len(stream)).encode()
        + b" >>\nstream\n"
        + stream
        + b"\nendstream\nendobj\n"
        b"trailer << /Root 1 0 R >>\n%%EOF\n"
    )


SAMPLE_CONTENT = (
    b"BT /F1 12 Tf 72 720 Td (Day 4: Control Flow) Tj\n"
    b"0 -14 Td (Loops are fun for kids) Tj\n"
    b"ET\n"
)


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------
def test_docx_extraction() -> None:
    data = make_docx(["Introduction to loops", "A while loop\tkeeps going", "Break exits early"])
    text = extract_text(Path("x.docx"), data)
    assert text is not None
    assert "Introduction to loops" in text
    assert "A while loop\tkeeps going" in text
    assert "Break exits early" in text
    assert text.count("\n") == 2


def test_docx_missing_part_returns_none() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("random.txt", "not a docx")
    assert extract_text(Path("x.docx"), buf.getvalue()) is None


def test_pdf_uncompressed_extraction() -> None:
    text = extract_text(Path("x.pdf"), make_pdf(SAMPLE_CONTENT))
    assert text is not None
    assert "Day 4: Control Flow" in text
    assert "Loops are fun for kids" in text


def test_pdf_flate_extraction() -> None:
    text = extract_text(Path("x.pdf"), make_pdf(SAMPLE_CONTENT, compress=True))
    assert text is not None
    assert "Day 4: Control Flow" in text
    assert "Loops are fun for kids" in text


def test_pdf_string_escapes() -> None:
    # In PDF a literal backslash is written \\, so the Python bytes need \\\\
    stream = b"BT /F1 12 Tf 72 720 Td (Escaped \\(paren\\) and \\\\backslash) Tj ET"
    text = extract_text(Path("x.pdf"), make_pdf(stream, compress=True))
    assert text is not None
    assert "Escaped (paren) and \\backslash" in text


def test_pdf_tj_array() -> None:
    stream = b"BT /F1 12 Tf 72 720 Td [(Day) 20 (4)] TJ ET"
    text = extract_text(Path("x.pdf"), make_pdf(stream))
    assert text is not None
    assert "Day" in text and "4" in text


def test_garbage_pdf_returns_none() -> None:
    assert extract_text(Path("x.pdf"), b"not a pdf at all") is None


def test_binary_sniff() -> None:
    assert is_binary(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
    assert not is_binary(b"plain text, no nulls")
    assert not looks_like_binary_text(b"\xff\xfe" + "héllo".encode("utf-16-le"))


# ---------------------------------------------------------------------------
# Tool wiring
# ---------------------------------------------------------------------------
def test_read_file_pdf_and_docx(tmp_path: Path) -> None:
    registry = ToolRegistry(tmp_path)
    (tmp_path / "report.pdf").write_bytes(make_pdf(SAMPLE_CONTENT, compress=True))
    (tmp_path / "notes.docx").write_bytes(make_docx(["Paragraph one", "Paragraph two"]))

    pdf = registry.execute("read_file", {"path": "report.pdf"})
    assert pdf["status"] == "success"
    assert "Day 4: Control Flow" in pdf["result"]
    assert pdf["encoding"] == "pdf"

    docx = registry.execute("read_file", {"path": "notes.docx"})
    assert docx["status"] == "success"
    assert "Paragraph two" in docx["result"]
    assert docx["encoding"] == "docx"


def test_read_file_binary_rejected(tmp_path: Path) -> None:
    registry = ToolRegistry(tmp_path)
    (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRgarbage")
    result = registry.execute("read_file", {"path": "image.png"})
    assert result["status"] == "error"
    assert "binary" in result["error"].lower()


def test_read_file_utf16_allowed(tmp_path: Path) -> None:
    registry = ToolRegistry(tmp_path)
    (tmp_path / "utf16.txt").write_bytes(b"\xff\xfe" + "héllo wörld".encode("utf-16-le"))
    result = registry.execute("read_file", {"path": "utf16.txt"})
    assert result["status"] == "success"
    assert "héllo wörld" in result["result"]


def test_search_files_skips_binary(tmp_path: Path) -> None:
    registry = ToolRegistry(tmp_path)
    (tmp_path / "notes.txt").write_text("the gpu offload section", encoding="utf-8")
    (tmp_path / "blob.pdf").write_bytes(b"%PDF-1.4\ngpu inside binary stream\n%%EOF\x00\x00")

    result = registry.execute("search_files", {"pattern": "gpu"})
    assert result["status"] == "success"
    assert result["result"] == ["notes.txt"]


def test_search_files_pipe_is_alternation(tmp_path: Path) -> None:
    """'one|two' must match files containing EITHER term - models pass
    regex-style alternations, not literal pipes."""
    registry = ToolRegistry(tmp_path)
    (tmp_path / "a.txt").write_text("purpose statement here", encoding="utf-8")
    (tmp_path / "b.txt").write_text("overview section", encoding="utf-8")
    (tmp_path / "c.txt").write_text("alpha|beta literal pipe only", encoding="utf-8")
    (tmp_path / "d.txt").write_text("unrelated", encoding="utf-8")

    result = registry.execute("search_files", {"pattern": "purpose|overview"})
    assert result["status"] == "success"
    paths = {Path(x).name for x in result["result"]}
    assert paths == {"a.txt", "b.txt"}, paths


def test_search_files_head_only_and_ext_skips(tmp_path: Path) -> None:
    """Head-only scanning + extension/name skips must not cost matches an
    agent cares about: hits in the readable head are found, hits beyond the
    head or inside binary/generated files are (deliberately) not."""
    registry = ToolRegistry(tmp_path)
    # 1) match inside the readable head -> found
    (tmp_path / "a.txt").write_text("needle near the top", encoding="utf-8")
    # 2) match only beyond the 256 KB head -> not found (documented trade-off)
    big = tmp_path / "b.txt"
    big.write_bytes(b"padding" * 60000 + b" needle far below", )  # > 256 KB
    # 3) binary extension containing the needle -> skipped by ext, no read
    (tmp_path / "img.png").write_bytes(b"needle inside png bytes")
    # 4) minified JS containing the needle -> skipped by name marker
    (tmp_path / "app.min.js").write_text("needle in bundle", encoding="utf-8")

    result = registry.execute("search_files", {"pattern": "needle"})
    assert result["status"] == "success"
    paths = {Path(x).name for x in result["result"]}
    assert paths == {"a.txt"}, paths


def test_glob_prunes_vendor_dirs_and_reports_empty(tmp_path: Path) -> None:
    """Glob must prune dependency/build dirs (like search_files) so a **
    pattern never stalls on node_modules/.git, and a zero-match glob must
    say so explicitly instead of returning silent success."""
    registry = ToolRegistry(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("x", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "dep.py").write_text("x", encoding="utf-8")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "site.py").write_text("x", encoding="utf-8")

    result = registry.execute("glob", {"pattern": "**/*.py"})
    assert result["status"] == "success"
    assert result["result"] == ["src/main.py"], result
    assert "node_modules" not in "\n".join(result["result"])
    assert "site.py" not in "\n".join(result["result"])

    empty = registry.execute("glob", {"pattern": "**/*.rs"})
    assert empty["status"] == "success"
    assert empty["result"] == []
    assert "No files matched" in empty["note"]


def test_glob_recursive_and_nested_patterns(tmp_path: Path) -> None:
    """** crosses directories; a plain prefix pattern is scoped to it."""
    registry = ToolRegistry(tmp_path)
    (tmp_path / "a.py").write_text("x", encoding="utf-8")
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "deep.py").write_text("x", encoding="utf-8")
    (tmp_path / "pkg" / "nested").mkdir()
    (tmp_path / "pkg" / "nested" / "deep.py").write_text("x", encoding="utf-8")

    recursive = registry.execute("glob", {"pattern": "**/*.py"})
    assert set(recursive["result"]) == {"a.py", "pkg/deep.py", "pkg/nested/deep.py"}

    scoped = registry.execute("glob", {"pattern": "pkg/**/*.py"})
    assert set(scoped["result"]) == {"pkg/deep.py", "pkg/nested/deep.py"}
