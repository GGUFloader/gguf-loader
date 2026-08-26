"""Syntax highlighting for code blocks (J-full).

Mirrors GPT4All's chatviewtextprocessor.cpp:717-767 language dispatch,
but implemented as manual QTextCursor formatting at insertion time (no
persistent QSyntaxHighlighter needed — code blocks are static).
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtGui import QFont


def _fmt(color: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(color))
    if bold:
        fmt.setFontWeight(QFont.Bold)
    if italic:
        fmt.setFontItalic(True)
    return fmt


# Color roles tuned for both light/dark surfaces (derived from theme tokens)
_DARK_COLORS = {
    "keyword": "#e6a23c",  # amber accent
    "string": "#6abf69",
    "comment": "#7d8590",
    "number": "#79c0ff",
    "type": "#ff7b72",
}
_LIGHT_COLORS = {
    "keyword": "#a97014",
    "string": "#1f9d63",
    "comment": "#8a93a4",
    "number": "#0550ae",
    "type": "#cf222e",
}

_LANG_ALIASES = {
    "py": "python",
    "js": "javascript",
    "ts": "typescript",
    "sh": "bash",
    "shell": "bash",
    "c++": "cpp",
    "cc": "cpp",
    "hpp": "cpp",
    "c": "cpp",
    "jsonc": "json",
}

# Regex patterns per language: list of (pattern, color_key, bold, italic)
_RULES: Dict[str, List[Tuple[str, str, bool, bool]]] = {
    "python": [
        (r"\b(and|as|assert|async|await|break|class|continue|def|del|elif|else|except|exec|finally|for|from|global|if|import|in|is|lambda|nonlocal|not|or|pass|raise|return|try|while|with|yield)\b", "keyword", True, False),
        (r"\b(True|False|None|self|cls)\b", "type", False, False),
        (r"#.*", "comment", False, True),
        (r'""".*?"""|\'\'\'.*?\'\'\'|".*?"|\'.*?\'', "string", False, False),
        (r"\b\d+\.?\d*\b", "number", False, False),
    ],
    "javascript": [
        (r"\b(break|case|catch|class|const|continue|debugger|default|delete|do|else|export|extends|false|finally|for|function|if|import|in|instanceof|new|null|return|super|switch|this|throw|true|try|typeof|var|void|while|with|yield|let|await|async|static|get|set)\b", "keyword", True, False),
        (r"//.*|/\*[\s\S]*?\*/", "comment", False, True),
        (r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`(?:\\.|[^`\\])*`', "string", False, False),
        (r"\b\d+\.?\d*\b", "number", False, False),
    ],
    "typescript": [
        (r"\b(break|case|catch|class|const|continue|debugger|default|delete|do|else|export|extends|false|finally|for|function|if|import|in|instanceof|new|null|return|super|switch|this|throw|true|try|typeof|var|void|while|with|yield|let|await|async|static|get|set|interface|type|implements|declare|namespace|module|public|private|protected|readonly)\b", "keyword", True, False),
        (r"//.*|/\*[\s\S]*?\*/", "comment", False, True),
        (r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`(?:\\.|[^`\\])*`', "string", False, False),
        (r"\b\d+\.?\d*\b", "number", False, False),
    ],
    "cpp": [
        (r"\b(alignas|alignof|and|and_eq|asm|auto|bitand|bitor|bool|break|case|catch|char|char8_t|char16_t|char32_t|class|compl|concept|const|consteval|constexpr|constinit|continue|co_await|co_return|co_yield|decltype|default|delete|do|double|dynamic_cast|else|enum|explicit|export|extern|false|float|for|friend|goto|if|inline|int|long|mutable|namespace|new|noexcept|not|not_eq|nullptr|operator|or|or_eq|private|protected|public|register|reinterpret_cast|requires|return|short|signed|sizeof|static|static_assert|static_cast|struct|switch|template|this|thread_local|throw|true|try|typedef|typeid|typename|union|unsigned|using|virtual|void|volatile|wchar_t|while|xor|xor_eq)\b", "keyword", True, False),
        (r"//.*|/\*[\s\S]*?\*/", "comment", False, True),
        (r'"(?:\\.|[^"\\])*"', "string", False, False),
        (r"\b\d+\.?\d*\b", "number", False, False),
        (r"#\s*include.*", "type", False, False),
    ],
    "json": [
        (r'"[^"]*"\s*:', "type", False, False),
        (r':\s*"(?:\\.|[^"\\])*"', "string", False, False),
        (r"\b(true|false|null)\b", "keyword", True, False),
        (r"\b-?\d+\.?\d*([eE][+-]?\d+)?\b", "number", False, False),
    ],
    "bash": [
        (r"\b(if|then|else|elif|fi|for|while|do|done|case|esac|function|select|until|echo|printf|exit|return|local|export|source|alias)\b", "keyword", True, False),
        (r"#.*", "comment", False, True),
        (r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', "string", False, False),
    ],
}

# Map typescript alias etc. to reuse rules
_RULES["js"] = _RULES["javascript"]


def _normalize_lang(lang: str) -> str:
    lang = (lang or "").strip().lower()
    return _LANG_ALIASES.get(lang, lang)


def get_rules(lang: str, is_dark: bool) -> List[Tuple[re.Pattern, QTextCharFormat]]:
    key = _normalize_lang(lang)
    raw = _RULES.get(key)
    if raw is None:
        return []
    colors = _DARK_COLORS if is_dark else _LIGHT_COLORS
    compiled = []
    for pat, color_key, bold, italic in raw:
        try:
            rx = re.compile(pat)
        except re.error:
            continue
        fmt = _fmt(colors[color_key], bold, italic)
        # Store mono font family on format
        fmt.setFontFamilies(["Consolas", "'Courier New'", "monospace"])
        compiled.append((rx, fmt))
    return compiled


def insert_highlighted_code(cursor: QTextCursor, code: str, lang: str, is_dark: bool, base_format: QTextCharFormat):
    """Insert *code* at *cursor* with syntax highlighting.

    Uses simple interval filling: find all regex matches, sort by start,
    skip overlaps, fill gaps with base_format. This is fast for code
    blocks (< few KB) and avoids a persistent QSyntaxHighlighter.
    """
    rules = get_rules(lang, is_dark)
    if not rules:
        cursor.insertText(code, base_format)
        return

    # Collect all matches
    spans: List[Tuple[int, int, QTextCharFormat]] = []
    for rx, fmt in rules:
        for m in rx.finditer(code):
            s, e = m.span()
            if s == e:
                continue
            spans.append((s, e, fmt))
    spans.sort(key=lambda x: (x[0], -(x[1] - x[0])))

    # Remove overlaps (keep earliest longest)
    filtered: List[Tuple[int, int, QTextCharFormat]] = []
    last_end = -1
    for s, e, fmt in spans:
        if s >= last_end:
            filtered.append((s, e, fmt))
            last_end = e

    pos = 0
    for s, e, fmt in filtered:
        if pos < s:
            cursor.insertText(code[pos:s], base_format)
        cursor.insertText(code[s:e], fmt)
        pos = e
    if pos < len(code):
        cursor.insertText(code[pos:], base_format)
