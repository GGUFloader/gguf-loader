"""
Chat bubble widget (ChatGPT-style).

The user message is a solid accent pill anchored to the right; the
assistant message is a soft card anchored to the left. Both use
asymmetric "tail" corners and are capped at ~75% of the conversation
column by their containing row (ui/chat_panel._BubbleRow).
"""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QTextEdit, QVBoxLayout, QWidget
from PySide6.QtGui import QFontMetrics, QTextOption
from PySide6.QtCore import Qt
from ggufloader.utils import detect_persian_text
from ggufloader.config import CHAT_BUBBLE_FONT_SIZE
from ggufloader.ui.theme import DARK_TOKENS, LIGHT_TOKENS

# Asymmetric radii: TL TR BR BL - the corner nearest the message edge is
# almost flat, mimicking ChatGPT's "tail". Mirrored for RTL conversations.
_TAIL_RADIUS_LTR = "20px 20px 4px 20px"    # bubble on the right -> tail BR
_TAIL_RADIUS_RTL = "20px 4px 20px 20px"    # bubble on the left  -> tail BL


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
        self.setup_ui(text)

    def setup_ui(self, text: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create text area (wraps anywhere, see _BubbleText)
        self.label = _BubbleText(text)
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

        if not self.is_user:
            # Style reasoning sections differently
            if "<استدلال>" in text or "<reasoning>" in text:
                styled_text = text
                t = DARK_TOKENS if self._is_dark_mode else LIGHT_TOKENS
                # Persian reasoning
                styled_text = styled_text.replace("<استدلال>", f'<span style="color:{t["textMuted"]}; font-style:italic">')
                styled_text = styled_text.replace("</استدلال>", '</span>')
                # English reasoning
                styled_text = styled_text.replace("<reasoning>", f'<span style="color:{t["textMuted"]}; font-style:italic">')
                styled_text = styled_text.replace("</reasoning>", '</span>')
                # Answer styling
                styled_text = styled_text.replace("<پاسخ>", f'<span style="color:{t["text"]}; font-weight:bold">')
                styled_text = styled_text.replace("</پاسخ>", '</span>')
                styled_text = styled_text.replace("<answer>", f'<span style="color:{t["text"]}; font-weight:bold">')
                styled_text = styled_text.replace("</answer>", '</span>')

                # Set the styled text with rich text support
                self.label.setTextFormat(Qt.RichText)
                self.label.setText(styled_text)
            else:
                # Default text display
                self.label.setTextFormat(Qt.PlainText)
                self.label.setText(text)
        else:
            # User messages are always plain text
            self.label.setTextFormat(Qt.PlainText)
            self.label.setText(text)

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

        t = DARK_TOKENS if is_dark_mode else LIGHT_TOKENS
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