"""File render routes - return file content with metadata for inline rendering."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/render")
async def render_file(path: str = Query(...), search: str = Query(default="")) -> dict:
    """Return file content optimized for inline rendering.
    
    Returns:
        - content: extracted/rendered text
        - type: file type (markdown, pdf, docx, code, text)
        - filename: base filename
        - metadata: type-specific info (pages, sections, line count, etc.)
        - matches: search result positions if search query provided
    """
    file_path = Path(path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    
    ext = file_path.suffix.lower()
    filename = file_path.name
    
    try:
        data = file_path.read_bytes()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cannot read file: {e}")
    
    # Determine file type and extract content
    if ext == ".pdf":
        return await _render_pdf(file_path, data, filename, search)
    elif ext == ".docx":
        return await _render_docx(file_path, data, filename, search)
    elif ext in (".md", ".markdown", ".mdx"):
        return await _render_markdown(file_path, data, filename, search)
    elif ext in (".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp", ".h",
                  ".go", ".rs", ".rb", ".php", ".lua", ".sh", ".bat", ".sql",
                  ".json", ".yaml", ".yml", ".toml", ".xml", ".html", ".css",
                  ".scss", ".less", ".vue", ".svelte"):
        return await _render_code(file_path, data, filename, ext, search)
    else:
        return await _render_text(file_path, data, filename, search)


async def _render_pdf(file_path: Path, data: bytes, filename: str, search: str) -> dict:
    """Render PDF with page-separated text."""
    from ggufloader.core.agent.text_extract import _pdf_text, _minimal_pdf_text
    
    # Try pypdf first for page-level extraction
    pages = []
    try:
        import pypdf
        import io
        reader = pypdf.PdfReader(io.BytesIO(data))
        for i, page in enumerate(reader.pages):
            try:
                text = page.extract_text() or ""
                if text.strip():
                    pages.append({"page": i + 1, "text": text.strip()})
            except Exception:
                continue
    except ImportError:
        # Fallback: extract all text as one block
        text = _pdf_text(data) or _minimal_pdf_text(data) or ""
        if text:
            pages.append({"page": 1, "text": text})
    
    content = "\n\n---\n\n".join(f"**Page {p['page']}**\n\n{p['text']}" for p in pages) if pages else "Could not extract text from PDF"
    
    matches = _find_matches(content, search) if search else []
    
    return {
        "content": content,
        "type": "pdf",
        "filename": filename,
        "metadata": {
            "pages": len(pages),
            "total_chars": sum(len(p["text"]) for p in pages),
            "has_images": True,  # PDFs typically have images
        },
        "matches": matches,
    }


async def _render_docx(file_path: Path, data: bytes, filename: str, search: str) -> dict:
    """Render DOCX with paragraph structure."""
    # Try mammoth for HTML conversion
    html_content = None
    try:
        import mammoth
        import io
        result = mammoth.convert_to_html(io.BytesIO(data))
        html_content = result.value
    except ImportError:
        pass
    except Exception:
        pass
    
    # Also extract plain text for search
    from ggufloader.core.agent.text_extract import _docx_text
    plain_text = _docx_text(data) or ""
    
    # Parse paragraphs from plain text
    paragraphs = [p.strip() for p in plain_text.split("\n") if p.strip()]
    
    # Detect headings (lines that are short, capitalized, or end with colon)
    sections = []
    for i, p in enumerate(paragraphs):
        if len(p) < 80 and (p.isupper() or p.endswith(":") or (len(p) < 50 and p[0:1].isupper())):
            sections.append({"index": i, "title": p})
    
    content = html_content if html_content else "\n\n".join(paragraphs)
    matches = _find_matches(plain_text, search) if search else []
    
    return {
        "content": content,
        "content_format": "html" if html_content else "markdown",
        "type": "docx",
        "filename": filename,
        "metadata": {
            "paragraphs": len(paragraphs),
            "sections": sections[:20],  # cap at 20 section headers
            "total_chars": len(plain_text),
        },
        "matches": matches,
    }


async def _render_markdown(file_path: Path, data: bytes, filename: str, search: str) -> dict:
    """Render Markdown with section detection."""
    try:
        content = data.decode("utf-8")
    except UnicodeDecodeError:
        content = data.decode("latin-1")
    
    # Extract headings for navigation
    import re
    headings = []
    for i, line in enumerate(content.split("\n")):
        match = re.match(r"^(#{1,6})\s+(.+)", line)
        if match:
            level = len(match.group(1))
            headings.append({"level": level, "title": match.group(2), "line": i + 1})
    
    matches = _find_matches(content, search) if search else []
    
    return {
        "content": content,
        "type": "markdown",
        "filename": filename,
        "metadata": {
            "headings": headings[:50],
            "total_chars": len(content),
            "line_count": content.count("\n") + 1,
        },
        "matches": matches,
    }


async def _render_code(file_path: Path, data: bytes, filename: str, ext: str, search: str) -> dict:
    """Render code with syntax highlighting metadata."""
    try:
        content = data.decode("utf-8")
    except UnicodeDecodeError:
        content = data.decode("latin-1")
    
    lines = content.split("\n")
    matches = _find_matches(content, search) if search else []
    
    # Detect functions/classes for navigation
    import re
    symbols = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Python
        if ext == ".py" and (stripped.startswith("def ") or stripped.startswith("class ")):
            symbols.append({"type": "function" if stripped.startswith("def ") else "class", "name": stripped.split("(")[0].split(":")[0].replace("def ", "").replace("class ", ""), "line": i + 1})
        # JS/TS
        elif ext in (".js", ".ts", ".jsx", ".tsx") and ("function " in stripped or "const " in stripped or "class " in stripped or "export " in stripped):
            name = stripped.replace("export ", "").replace("default ", "").split("(")[0].split("=")[0].strip()
            if name.startswith("const ") or name.startswith("let "):
                name = name.split()[-1] if " " in name else name
            if len(name) < 60:
                symbols.append({"type": "symbol", "name": name, "line": i + 1})
    
    return {
        "content": content,
        "type": "code",
        "filename": filename,
        "metadata": {
            "language": ext.lstrip("."),
            "line_count": len(lines),
            "symbols": symbols[:50],
        },
        "matches": matches,
    }


async def _render_text(file_path: Path, data: bytes, filename: str, search: str) -> dict:
    """Render plain text."""
    try:
        content = data.decode("utf-8")
    except UnicodeDecodeError:
        content = data.decode("latin-1")
    
    lines = content.split("\n")
    matches = _find_matches(content, search) if search else []
    
    return {
        "content": content,
        "type": "text",
        "filename": filename,
        "metadata": {
            "line_count": len(lines),
            "total_chars": len(content),
        },
        "matches": matches,
    }


def _find_matches(content: str, query: str) -> list:
    """Find search matches with line numbe
rs and context."""
    if not query:
        return []
    
    matches = []
    lines = content.split(chr(10))
    query_lower = query.lower()
    
    for i, line in enumerate(lines):
        if query_lower in line.lower():
            start = max(0, i - 1)
            end = min(len(lines), i + 2)
            context = chr(10).join(lines[start:end])
            matches.append({
                "line": i + 1,
                "text": line.strip(),
                "context": context,
            })
            if len(matches) >= 50:
                break
    
    return matches
