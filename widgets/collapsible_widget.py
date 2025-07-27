"""
Collapsible Widget for AI Chat Application
A widget that can be collapsed/expanded with smooth animations
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFrame, QGraphicsOpacityEffect, QSizePolicy
)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, Signal
from PySide6.QtGui import QFont


class CollapsibleWidget(QWidget):
    """A collapsible widget container with animated expand/collapse"""

    toggled = Signal(bool) # Signal emitted when collapsed state changes

    def __init__(self, title="", icon="", parent=None):
        super().__init__(parent)
        self.is_collapsed = True
        self.animation_duration = 200

        self.setup_ui(title, icon)
        self.setup_animation()

    def setup_ui(self, title, icon):
        """Setup the user interface"""
        self.setFixedWidth(280)

        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(0)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        # Header (always visible)
        self.header = QFrame()
        self.header.setFrameStyle(QFrame.Box)
        self.header.setFixedHeight(35)
        self.header.setCursor(Qt.PointingHandCursor)

        # Header layout
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(8, 4, 8, 4)
        header_layout.setSpacing(8)

        # Icon label
        self.icon_label = QLabel(icon)
        self.icon_label.setFixedSize(20, 20)
        self.icon_label.setAlignment(Qt.AlignCenter)

        # Title label
        self.title_label = QLabel(title)
        self.title_label.setFont(QFont("Arial", 11, QFont.Bold))

        # Expand/collapse indicator
        self.indicator = QLabel("▶")
        self.indicator.setFixedSize(15, 15)
        self.indicator.setAlignment(Qt.AlignCenter)

        # Add to header layout
        header_layout.addWidget(self.icon_label)
        header_layout.addWidget(self.title_label)
        header_layout.addWidget(self.indicator)

        # Content area (collapsible)
        self.content_area = QFrame()
        self.content_area.setFrameStyle(QFrame.Box)
        self.content_area.setVisible(False)

        # Content layout
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(5, 5, 5, 5)
        self.content_layout.setSpacing(5)

        # Add to main layout
        self.main_layout.addWidget(self.header)
        self.main_layout.addWidget(self.content_area)

        # Connect header click
        self.header.mousePressEvent = self.on_header_clicked

    def setup_animation(self):
        """Setup the collapse/expand animation"""
        self.animation = QPropertyAnimation(self, b"maximumHeight")
        self.animation.setDuration(self.animation_duration)
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)

    def on_header_clicked(self, event):
        """Handle header click to toggle collapse state"""
        if event.button() == Qt.LeftButton:
            self.toggle_collapsed()

    def toggle_collapsed(self):
        """Toggle the collapsed state with animation"""
        if self.is_collapsed:
            self.expand()
        else:
            self.collapse()

    def expand(self):
        """Expand the widget"""
        if not self.is_collapsed:
            return

        self.is_collapsed = False
        self.content_area.setVisible(True)

        # Update indicator
        self.indicator.setText("▼")

        # Calculate target height
        header_height = self.header.sizeHint().height()
        content_height = self.content_area.sizeHint().height()
        target_height = header_height + content_height + 10  # Extra padding

        # Start animation
        self.animation.setStartValue(self.height())
        self.animation.setEndValue(target_height)
        self.animation.start()

        # Emit signal
        self.toggled.emit(False)

    def collapse(self):
        """Collapse the widget"""
        if self.is_collapsed:
            return

        self.is_collapsed = True

        # Update indicator
        self.indicator.setText("▶")

        # Calculate target height (header only)
        header_height = self.header.sizeHint().height()

        # Start animation
        self.animation.setStartValue(self.height())
        self.animation.setEndValue(header_height)
        self.animation.finished.connect(self.on_collapse_finished)
        self.animation.start()

        # Emit signal
        self.toggled.emit(True)

    def on_collapse_finished(self):
        """Called when collapse animation finishes"""
        self.content_area.setVisible(False)
        self.animation.finished.disconnect(self.on_collapse_finished)

    def add_content_widget(self, widget):
        """Add a widget to the content area"""
        self.content_layout.addWidget(widget)

    def add_content_layout(self, layout):
        """Add a layout to the content area"""
        self.content_layout.addLayout(layout)

    def clear_content(self):
        """Clear all content widgets"""
        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def set_title(self, title):
        """Set the title text"""
        self.title_label.setText(title)

    def set_icon(self, icon):
        """Set the icon text"""
        self.icon_label.setText(icon)

    def update_dark_mode(self, is_dark_mode):
        """Update styling for dark/light mode"""
        if is_dark_mode:
            # Dark theme
            self.setStyleSheet("""
                CollapsibleWidget {
                    background-color: #2d2d2d;
                    border: 1px solid #404040;
                    border-radius: 6px;
                }

                QFrame {
                    background-color: #2d2d2d;
                    border: 1px solid #404040;
                    border-radius: 4px;
                }

                QLabel {
                    color: #ffffff;
                    background-color: transparent;
                    border: none;
                }

                QFrame:hover {
                    background-color: #3a3a3a;
                }
            """)
        else:
            # Light theme
            self.setStyleSheet("""
                CollapsibleWidget {
                    background-color: #f8f9fa;
                    border: 1px solid #dee2e6;
                    border-radius: 6px;
                }

                QFrame {
                    background-color: #f8f9fa;
                    border: 1px solid #dee2e6;
                    border-radius: 4px;
                }

                QLabel {
                    color: #000000;
                    background-color: transparent;
                    border: none;
                }

                QFrame:hover {
                    background-color: #e9ecef;
                }
            """)

    def sizeHint(self):
        """Return the preferred size"""
        if self.is_collapsed:
            return self.header.sizeHint()
        else:
            header_height = self.header.sizeHint().height()
            content_height = self.content_area.sizeHint().height()
            return self.header.sizeHint() + self.content_area.sizeHint()

    def minimumSizeHint(self):
        """Return the minimum size"""
        return self.header.minimumSizeHint()


# Example usage and test widget
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton

    app = QApplication(sys.argv)

    # Create main window
    window = QMainWindow()
    window.setWindowTitle("Collapsible Widget Test")
    window.resize(400, 600)

    # Central widget
    central = QWidget()
    window.setCentralWidget(central)

    layout = QVBoxLayout(central)

    # Create collapsible widgets
    collapsible1 = CollapsibleWidget("Settings", "⚙️")
    collapsible1.add_content_widget(QPushButton("Option 1"))
    collapsible1.add_content_widget(QPushButton("Option 2"))

    collapsible2 = CollapsibleWidget("Tools", "🔧")
    collapsible2.add_content_widget(QPushButton("Tool 1"))
    collapsible2.add_content_widget(QPushButton("Tool 2"))
    collapsible2.add_content_widget(QPushButton("Tool 3"))

    collapsible3 = CollapsibleWidget("Add-ons", "🔌")
    collapsible3.add_content_widget(QLabel("No add-ons installed"))

    layout.addWidget(collapsible1)
    layout.addWidget(collapsible2)
    layout.addWidget(collapsible3)

    # Dark mode toggle
    dark_mode_btn = QPushButton("Toggle Dark Mode")
    is_dark = False


    def toggle_dark():
        global is_dark
        is_dark = not is_dark
        collapsible1.update_dark_mode(is_dark)
        collapsible2.update_dark_mode(is_dark)
        collapsible3.update_dark_mode(is_dark)

        if is_dark:
            window.setStyleSheet("QMainWindow { background-color: #1e1e1e; }")
        else:
            window.setStyleSheet("QMainWindow { background-color: #ffffff; }")


    dark_mode_btn.clicked.connect(toggle_dark)
    layout.addWidget(dark_mode_btn)

    layout.addStretch()

    window.show()
    sys.exit(app.exec())