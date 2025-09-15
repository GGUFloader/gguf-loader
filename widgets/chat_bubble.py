"""
Custom chat bubble widget
"""

from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from utils import detect_persian_text
from config import CHAT_BUBBLE_MIN_WIDTH, CHAT_BUBBLE_MAX_WIDTH, CHAT_BUBBLE_FONT_SIZE

class ChatBubble(QFrame):
    """Custom chat bubble widget with automatic RTL/LTR detection"""
    def __init__(self, text: str, is_user: bool, force_rtl: bool = None):
        super().__init__()
        self.is_user = is_user
        self.text = text
        # Auto-detect RTL if not forced
        self.is_rtl = force_rtl if force_rtl is not None else detect_persian_text(text)
        self.setup_ui(text)

    def setup_ui(self, text: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)

        # Create text label
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        # Set bubble sizing
        self.setMinimumWidth(CHAT_BUBBLE_MIN_WIDTH)
        self.setMaximumWidth(CHAT_BUBBLE_MAX_WIDTH)

        # Set font size
        font = self.label.font()
        font.setPointSize(CHAT_BUBBLE_FONT_SIZE)
        self.label.setFont(font)

        # Set alignment based on RTL/LTR detection
        layout.addWidget(self.label)
        self.update_alignment()

        # Apply default styling
        self.update_style(is_dark_mode=False)

    def update_text(self, text: str):
        """Update text and re-detect RTL if needed"""
        self.text = text
        # Re-detect RTL for the new text
        self.is_rtl = detect_persian_text(text)

        if not self.is_user:
            # Style reasoning sections differently
            if "<استدلال>" in text or "<reasoning>" in text:
                styled_text = text
                # Persian reasoning
                styled_text = styled_text.replace("<استدلال>", '<span style="color:#888; font-style:italic">')
                styled_text = styled_text.replace("</استدلال>", '</span>')
                # English reasoning
                styled_text = styled_text.replace("<reasoning>", '<span style="color:#888; font-style:italic">')
                styled_text = styled_text.replace("</reasoning>", '</span>')
                # Answer styling
                styled_text = styled_text.replace("<پاسخ>", '<span style="color:black; font-weight:bold">')
                styled_text = styled_text.replace("</پاسخ>", '</span>')
                styled_text = styled_text.replace("<answer>", '<span style="color:black; font-weight:bold">')
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

    def update_alignment(self):
        """Update text alignment based on RTL detection"""
        if self.is_rtl:
            self.label.setAlignment(Qt.AlignRight | Qt.AlignTop)
            self.label.setLayoutDirection(Qt.RightToLeft)
        else:
            self.label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            self.label.setLayoutDirection(Qt.LeftToRight)

    def update_style(self, is_dark_mode: bool):
        """Apply styling based on theme"""
        if self.is_user:
            if is_dark_mode:
                self.setStyleSheet("""
                    QFrame {
                        background-color: #2d5a2d;
                        border-radius: 15px;
                        margin: 5px;
                    }
                    QLabel { 
                        color: white; 
                        font-size: 14px; 
                        padding: 12px 16px;
                        line-height: 1.6;
                    }
                """)
            else:
                self.setStyleSheet("""
                    QFrame {
                        background-color: #dcf8c6;
                        border-radius: 15px;
                        margin: 5px;
                    }
                    QLabel { 
                        color: black; 
                        font-size: 14px; 
                        padding: 12px 16px;
                        line-height: 1.6;
                    }
                """)
        else:
            if is_dark_mode:
                self.setStyleSheet("""
                    QFrame {
                        background-color: #404040;
                        border-radius: 15px;
                        margin: 5px;
                    }
                    QLabel { 
                        color: white; 
                        font-size: 14px; 
                        padding: 12px 16px;
                        line-height: 1.6;
                    }
                """)
            else:
                self.setStyleSheet("""
                    QFrame {
                        background-color: #f0f0f0;
                        border-radius: 15px;
                        margin: 5px;
                    }
                    QLabel { 
                        color: black; 
                        font-size: 14px; 
                        padding: 12px 16px;
                        line-height: 1.6;
                    }
                """)

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