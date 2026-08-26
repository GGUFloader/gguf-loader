"""
Chat bubble widget (ChatGPT-style).

The user message is a solid accent pill anchored to the right; the
assistant message is a soft card anchored to the left. Both use
asymmetric "tail" corners and are capped at ~75% of the conversation
column by their containing row (ui/chat_panel._BubbleRow).
"""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMenu, QSizePolicy, QTextEdit, QVBoxLayout, QWidget
from PySide6.QtGui import (
    QColor, QFontMetrics, QTextCharFormat, QTextCursor, QTextDocumentFragment,
    QTextOption,
)
from PySide6.QtCore import Qt
import re
from ggufloader.utils import detect_persian_text
from ggufloader.config import CHAT_BUBBLE_FONT_SIZE

# Asymmetric radii: TL TR BR BL - the corner nearest the message edge is
# almost flat, mimicking ChatGPT's "tail". Mirrored for RTL conversations.
_TAIL_RADIUS_LTR = "20px 20px 4px 20px"    # bubble on the right -> tail BR
_TAIL_RADIUS_RTL = "20px 4px 20px 20px"    # bubble on the left  -> tail BL


def _theme_pair():
    # Imported lazily: ggufloader.ui.__init__ eagerly imports main_window, and an
    # eager import here makes widgets -> ui -> widgets a circular import.
    from ggufloader.ui.theme import DARK_TOKENS, LIGHT_TOKENS
    return DARK_TOKENS, LIGHT_TOKENS


_CODE_FENCE_RE = re.compile(r"```([A-Za-z0-9_+\-#]*)[ \t]*\n(.*?)(?:```|\Z)", re.DOTALL)


def split_code_segments(text: str) -> list:
    """Split a reply into ``('md', prose)`` / ``('code', (lang, code))`` parts.

    Unclosed fences (stream cut mid-block) still yield their content.
    """
    segs: list = []
    pos = 0
    for m in _CODE_FENCE_RE.finditer(text):
        if m.start() > pos:
            segs.append(("md", text[pos:m.start()]))
        segs.append(("code", (m.group(1).lower(), m.group(2))))
        pos = m.end()
    if pos < len(text):
        segs.append(("md", text[pos:]))
    return segs or [("md", text)]


def _active_tokens(widget):
    """Palette of the nearest themed ancestor (falls back to light)."""
    dark_tokens, light_tokens = _theme_pair()
    w = widget
    while w is not None:
        dark = getattr(w, "_is_dark_mode", getattr(w, "_is_dark", None))
        if dark is not None:
            return dark_tokens if dark else light_tokens
        w = w.parentWidget()
    return light_tokens


def _styled_text_menu(menu: QMenu, widget) -> None:
    """Theme a standard Copy/Select-All popup (black-clears on Windows)."""
    t = _active_tokens(widget)
    menu.setAttribute(Qt.WA_TranslucentBackground, True)
    menu.setStyleSheet(f"""
        QMenu {{
            background-color: {t["surface"]};
            color: {t["text"]};
            border: 1px solid {t["borderStrong"]};
            border-radius: 8px;
            padding: 4px;
        }}
        QMenu::item {{
            padding: 6px 24px 6px 14px;
            border-radius: 6px;
            background: transparent;
        }}
        QMenu::item:selected {{ background-color: {t["elevatedHover"]}; }}
        QMenu::item:disabled {{ color: {t["textMuted"]}; }}
    """)


class _BubbleText(QTextEdit):
    """Read-only text area for bubbles that breaks long unbroken runs.

    QLabel's word-wrap only breaks at word boundaries, so token-streamed
    text without spaces (common with raw llama.cpp output), code and URLs
    overflowed the bubble in one endless line. QTextEdit with
    ``WrapAtWordBoundaryOrAnywhere`` breaks anywhere, and keeps native
    selection/copy/context menu. QSS ``font-size`` does not drive a
    QTextEdit's document, so the font is set explicitly in pixels.
    """

    _PAD_X = 32  # matches the QSS padding (10px 16px) the bubble applies
    _PAD_Y = 20  # 10px top + 10px bottom

    def __init__(self, text: str = "", parent=None) -> None:
        # Construct empty and set the text as PLAIN text explicitly: the
        # QTextEdit(QString) constructor auto-detects HTML, which would
        # swallow angle brackets in ordinary user/AI messages.
        super().__init__("", parent)
        self.setPlainText(text)
        self.setReadOnly(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self.setMinimumSize(0, 0)
        self.document().setDocumentMargin(0)
        self._rich = False

    # --- ChatBubble's label API -------------------------------------
    def setWordWrap(self, wrap: bool) -> None:
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)

    def setTextFormat(self, fmt) -> None:
        self._rich = fmt == Qt.RichText

    def setText(self, text: str) -> None:
        if self._rich:
            self.setHtml(text)
        else:
            self.setPlainText(text)

    def text(self) -> str:
        return self.toPlainText()

    def setFont(self, font) -> None:
        # The bubble historically styled labels with QSS ``font-size: Npx``.
        # QSS sizes do not reach a QTextEdit's document, so translate the
        # point size the caller passes into the same numeric pixel size.
        if font.pointSizeF() > 0 and font.pixelSize() < 0:
            font.setPixelSize(max(int(font.pointSizeF()), 1))
        super().setFont(font)

    def contextMenuEvent(self, event) -> None:
        """Standard Copy/Select-All menu, themed for light/dark mode."""
        menu = self.createStandardContextMenu()
        _styled_text_menu(menu, self)
        extra = {}
        bubble = getattr(self, "bubble", None)
        if bubble is not None:
            extra = bubble.extend_context_menu(menu)
        chosen = menu.exec(event.globalPos())
        if chosen is not None and chosen in extra:
            extra[chosen]()
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        """Code-card copy headers + safe link opening (post-generation)."""
        anchor = self.anchorAt(event.pos())
        if anchor and anchor.startswith("__copy__"):
            from PySide6.QtWidgets import QApplication
            try:
                idx = int(anchor[len("__copy__"):])
                codes = getattr(self.bubble, "_code_segments", [])
                if 0 <= idx < len(codes):
                    QApplication.clipboard().setText(codes[idx])
            except Exception:  # noqa: BLE001
                pass
            event.accept()
            return
        if anchor and anchor.startswith(("http://", "https://")):
            bubble = getattr(self, "bubble", None)
            locked = bool(getattr(bubble, "links_locked", False))
            if not locked:
                from PySide6.QtGui import QDesktopServices, QUrl
                QDesktopServices.openUrl(QUrl(anchor))
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def setAlignment(self, alignment) -> None:
        # QTextEdit only aligns blocks horizontally; strip vertical flags.
        horizontal = alignment & (Qt.AlignLeft | Qt.AlignRight | Qt.AlignHCenter | Qt.AlignJustify)
        if not horizontal:
            horizontal = Qt.AlignLeft
        super().setAlignment(horizontal)

    def heightForWidth(self, w: int) -> int:
        """Height the wrapped text needs at widget width *w*."""
        text_w = max(int(w) - self._PAD_X, 1)
        doc = self.document()
        doc.setDefaultFont(self.font())
        doc.setTextWidth(text_w)
        return int(doc.size().height()) + self._PAD_Y

    def adjustSize(self) -> None:
        # The bubble is fixed-size; the inner text area must not fight it.
        return


class ChatBubble(QFrame):
    """Custom chat bubble widget with automatic RTL/LTR detection"""
    def __init__(self, text: str, is_user: bool, force_rtl: bool = None):
        super().__init__()
        self.is_user = is_user
        self.text = text
        # Auto-detect RTL if not forced
        self.is_rtl = force_rtl if force_rtl is not None else detect_persian_text(text)
        self._is_dark_mode = False
        self._current_font_size = CHAT_BUBBLE_FONT_SIZE
        self._fit_max_width = None  # cap for fit_width(); None = no cap
        # Rich (markdown) rendering for assistant replies; users write raw.
        self.rich_enabled = not is_user
        # Optional callback fired from the context menu ("Regenerate").
        self.on_regenerate = None
        # Optional K5 feedback callback: called with "up" or "down".
        self.on_feedback = None
        # Optional callback fired from the context menu ("Delete message").
        self.on_delete = None
        # Optional callback fired from the context menu ("Edit message").
        self.on_edit = None
        # While True (generation active) links don't open — prevents
        # clicking half-streamed URLs.
        self.links_locked = False
        # Raw code bodies for the click-to-copy headers (rich mode).
        self._code_segments: list = []
        self.setup_ui(text)

    def extend_context_menu(self, menu: QMenu) -> dict:
        """Message-level actions appended to the text-edit popup."""
        actions: dict = {}
        menu.addSeparator()
        copy_msg = menu.addAction("Copy message")
        actions[copy_msg] = lambda: self._copy_message()
        if not self.is_user:
            rich_action = menu.addAction("Rich rendering")
            rich_action.setCheckable(True)
            rich_action.setChecked(self.rich_enabled)
            actions[rich_action] = self._toggle_rich
            if self.on_regenerate is not None:
                regen = menu.addAction("↻ Regenerate response")
                actions[regen] = self.on_regenerate
            if self.on_feedback is not None:
                up = menu.addAction("👍 Good response")
                actions[up] = lambda: self.on_feedback("up")
                down = menu.addAction("👎 Bad response…")
                actions[down] = lambda: self.on_feedback("down")
        if self.on_delete is not None:
            delete_action = menu.addAction("🗑 Delete message")
            actions[delete_action] = lambda: self.on_delete(self.text)
        elif self.on_edit is not None:
            edit_action = menu.addAction("✏ Edit message")
            actions[edit_action] = lambda: self.on_edit(self.text)
        return actions

    def _copy_message(self) -> None:
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self.text)

    def _toggle_rich(self) -> None:
        self.rich_enabled = not self.rich_enabled
        self.update_text(self.text)

    def _render(self, text: str) -> None:
        """Plain, or segmented markdown + framed code cards (assistant)."""
        if not (self.rich_enabled and not self.is_user and text):
            self.label.setTextFormat(Qt.PlainText)
            self.label.setPlainText(text)
            return
        try:
            self._render_segments(text)
        except Exception:  # noqa: BLE001 - never lose a reply to a render bug
            self.label.setTextFormat(Qt.PlainText)
            self.label.setPlainText(text)

    def _render_segments(self, text: str) -> None:
        from PySide6.QtGui import QTextDocument

        t = _active_tokens(self)
        features = (QTextDocument.MarkdownFeature.MarkdownDialectGitHub
                    | QTextDocument.MarkdownFeature.MarkdownNoHTML)

        doc = self.label.document()
        doc.clear()
        fs = max(self._current_font_size - 1, 10)
        doc.setDefaultStyleSheet(
            f"a {{ color: {t['accent']}; text-decoration: none; }}"
        )

        mono = QTextCharFormat()
        mono.setFontFamilies(["Consolas", "'Courier New'", "monospace"])
        mono.setFontPointSize(fs)
        mono.setBackground(QColor(t["elevated"]))
        mono.setForeground(QColor(t["text"]))

        cursor = QTextCursor(doc)
        segments = split_code_segments(text)
        self._code_segments = [p[1].rstrip("\n") for k, p in segments if k == "code"]
        idx = 0
        first_block = True
        for kind, payload in segments:
            if not first_block:
                cursor.insertBlock()
            first_block = False
            if kind == "md":
                prose = payload.strip("\n")
                if not prose.strip():
                    continue
                tmp = QTextDocument()
                tmp.setDefaultFont(self.label.font())
                tmp.setMarkdown(prose, features)  # NoHTML: never trust source
                cursor.insertFragment(QTextDocumentFragment(tmp))
            else:
                lang, code = payload
                header = (f'<a href="__copy__{idx}">⧉ {lang or "code"} '
                          f"— click to copy</a><br>")
                cursor.insertHtml(header)
                raw = code.rstrip("\n")
                try:
                    from ggufloader.widgets.syntax_highlighter import insert_highlighted_code
                    insert_highlighted_code(cursor, raw, lang, self._is_dark_mode, mono)
                except Exception:  # noqa: BLE001 - fallback to plain mono
                    cursor.insertText(raw, mono)
                cursor.insertBlock()
                first_block = True  # trailing block already added by code
                idx += 1
        self.label.setTextFormat(Qt.RichText)

    def setup_ui(self, text: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create text area (wraps anywhere, see _BubbleText)
        self.label = _BubbleText(text)
        self.label.bubble = self  # back-reference for the context menu
        self.label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        self.label.setContextMenuPolicy(Qt.DefaultContextMenu)

        # Bubble hugs its content; the containing row caps the width.
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        self.setMinimumWidth(200)  # Reasonable minimum for readability

        # Set alignment based on RTL/LTR detection
        layout.addWidget(self.label)
        self.update_alignment()

        # Apply initial styling
        self.update_style(is_dark_mode=False)
        self.fit_width()

    def fit_width(self, max_width=None):
        """Size the bubble to fit its text, capped at *max_width*.

        QLabel with word-wrap reports a tiny sizeHint (the width of the
        longest word), so without this the bubble collapses to a narrow
        column and text wraps after a few words even though the row is
        much wider. We measure the text with the label's font metrics and
        fix the bubble's width *and* wrapped height instead, so the bubble
        hugs its text (up to the cap) instead of wrapping every 3-4 words.
        """
        if max_width is not None:
            self._fit_max_width = max_width
        cap = self._fit_max_width or 4096

        # Measure with a pixel-size font so it matches the QSS
        # ``font-size: Npx`` that actually renders the label.
        font = self.label.font()
        font.setPixelSize(self._current_font_size)
        fm = QFontMetrics(font)

        pad_x = 32  # QSS label padding 10px 16px -> 32px horizontal (floating chat: 14px + 2px margins)
        pad_y = 24  # 10px top + 10px bottom (floating chat adds 2px margins)
        text = self.text or " "

        # Ideal single-line width, clamped to the cap.
        width = min(max(fm.horizontalAdvance(text) + pad_x, self.minimumWidth()), cap)

        # Fix the width first so the label's available area is known.
        self.setFixedWidth(width)
        # The label's horizontal room is the frame's contents rect (QSS
        # border + margin excluded).
        label_w = self.contentsRect().width()
        if label_w <= 0:
            label_w = max(width - pad_x, 1)

        # Height: ask the label itself how tall it needs to be at that
        # width. QFontMetrics.boundingRect under-estimates the wrapped
        # height, clipping the bottom lines of multi-line bubbles (their
        # text ran under the bubble padding). QLabel.heightForWidth uses
        # the label's real layout engine and QSS font, so it is
        # authoritative. Add back the vertical chrome (border + margin).
        label_h = self.label.heightForWidth(label_w)
        if label_h <= 0:
            label_h = fm.height()
        inset_y = self.height() - self.contentsRect().height()
        height = max(label_h + inset_y, fm.height() + pad_y)

        if self.width() != width or self.height() != height:
            self.setFixedSize(width, height)

    def update_text(self, text: str):
        """Update text and re-detect RTL if needed"""
        self.text = text
        # Re-detect RTL for the new text
        self.is_rtl = detect_persian_text(text)

        self._render(text)

        # Update alignment after text change
        self.update_alignment()
        self.fit_width()

    def update_alignment(self):
        """Update text alignment based on RTL detection"""
        if self.is_rtl:
            self.label.setAlignment(Qt.AlignRight | Qt.AlignTop)
            self.label.setLayoutDirection(Qt.RightToLeft)
        else:
            self.label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            self.label.setLayoutDirection(Qt.LeftToRight)

    def update_style(self, is_dark_mode: bool):
        """Apply ChatGPT-style styling based on theme and current font size"""
        self._is_dark_mode = is_dark_mode
        font_size = getattr(self, '_current_font_size', 14)

        dark_tokens, light_tokens = _theme_pair()
        t = dark_tokens if is_dark_mode else light_tokens
        # The tail corner points at the conversation edge: a user bubble sits
        # on the right in LTR (tail BR) but on the left in RTL (tail BL);
        # assistant bubbles mirror that (is_user XOR is_rtl => right side).
        radius = _TAIL_RADIUS_LTR if self.is_user != self.is_rtl else _TAIL_RADIUS_RTL
        if self.is_user:
            # Solid accent pill, like ChatGPT's user bubble.
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {t["accent"]};
                    border: none;
                    border-radius: {radius};
                }}
                QFrame:hover {{ background-color: {t["accentHover"]}; }}
                QLabel, QTextEdit {{
                    color: {t["onAccent"]};
                    font-size: {font_size}px;
                    padding: 10px 16px;
                    background: transparent;
                    border: none;
                    selection-background-color: {t["accentSelection"]};
                    selection-color: {t["onAccent"]};
                }}
            """)
        else:
            # Soft elevated card, like ChatGPT's assistant bubble.
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {t["elevated"]};
                    border: 1px solid {t["border"]};
                    border-radius: {radius};
                }}
                QFrame:hover {{ background-color: {t["elevatedHover"]};
                                border-color: {t["borderStrong"]}; }}
                QLabel, QTextEdit {{
                    color: {t["text"]};
                    font-size: {font_size}px;
                    padding: 10px 16px;
                    background: transparent;
                    border: none;
                    selection-background-color: {t["accentSoft"]};
                    selection-color: {t["text"]};
                }}
            """)
        # Also ensure the font object matches (for size calculations)
        font = self.label.font()
        font.setPointSize(font_size)
        self.label.setFont(font)

        # Force update
        self.label.adjustSize()
        self.adjustSize()
        self.update()
        self.fit_width()

    def set_rtl_mode(self, is_rtl: bool):
        """Manually set RTL mode"""
        self.is_rtl = is_rtl
        self.update_alignment()

    def get_text(self) -> str:
        """Get the current text content"""
        return self.text

    def is_rtl_text(self) -> bool:
        """Check if current text is RTL"""
        return self.is_rtl

    def set_font_size(self, size: int):
        """Set the font size for this bubble and refresh styles"""
        self._current_font_size = size
        # Re-apply the current style mode with new font size
        self.update_style(self._is_dark_mode)


class _BubbleRow(QWidget):
    """Row that anchors a bubble to its side and caps its width.

    ChatGPT-style: user bubbles sit on the right, assistant on the left,
    and neither stretches full-width - they hug their content up to ~75%
    of the conversation column.
    """

    def __init__(self, bubble: ChatBubble, is_user: bool, is_rtl: bool = False,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bubble = bubble
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        # Same XOR as the bubble's tail: user bubbles go right in LTR but
        # left in RTL (ChatGPT mirrors the whole conversation).
        if is_user != is_rtl:
            row.addStretch(1)
            row.addWidget(bubble)
        else:
            row.addWidget(bubble)
            row.addStretch(1)
        self._apply_max_width()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        super().resizeEvent(event)
        self._apply_max_width()

    def _apply_max_width(self) -> None:
        width = self.width()
        if width <= 0:
            return
        # Fit the bubble to its text, capped at 75% of the conversation column.
        self._bubble.fit_width(max(240, int(width * 0.75)))