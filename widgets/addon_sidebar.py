"""
Addon Sidebar Widget - Displays addon launcher buttons
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFrame, QScrollArea, QSpacerItem, QSizePolicy, QToolTip
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

try:
    from config import FONT_FAMILY
except ImportError:
    FONT_FAMILY = "Arial"


class AddonSidebar(QWidget):
    """Sidebar widget for addon launcher buttons"""

    def __init__(self, addon_manager, parent=None):
        super().__init__(parent)
        self.addon_manager = addon_manager
        self.addon_buttons = {}
        self.setup_ui()
        self.refresh_addons()

    def setup_ui(self):
        """Setup the sidebar UI"""
        self.setFixedWidth(200)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # Title
        title = QLabel("🧩 Addons")
        title.setFont(QFont(FONT_FAMILY, 14, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Scroll area for addon buttons
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Container for buttons
        self.button_container = QWidget()
        self.button_layout = QVBoxLayout(self.button_container)
        self.button_layout.setSpacing(5)
        self.button_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area.setWidget(self.button_container)
        layout.addWidget(scroll_area)

        # Control buttons
        control_layout = QHBoxLayout()

        # Refresh button
        refresh_btn = QPushButton("🔄")
        refresh_btn.setMinimumSize(35, 30)
        refresh_btn.setMaximumSize(35, 30)
        refresh_btn.setToolTip("Refresh Addons")
        refresh_btn.clicked.connect(self.refresh_addons)
        control_layout.addWidget(refresh_btn)

        # Close all button
        close_all_btn = QPushButton("❌")
        close_all_btn.setMinimumSize(35, 30)
        close_all_btn.setMaximumSize(35, 30)
        close_all_btn.setToolTip("Close All Addons")
        close_all_btn.clicked.connect(self.close_all_addons)
        control_layout.addWidget(close_all_btn)

        # Add spacer
        control_layout.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        layout.addLayout(control_layout)

    def refresh_addons(self):
        """Refresh the addon list and recreate buttons"""
        # Clear existing buttons
        for i in reversed(range(self.button_layout.count())):
            child = self.button_layout.itemAt(i).widget()
            if child:
                child.setParent(None)

        self.addon_buttons.clear()

        # Load all addons
        results = self.addon_manager.load_all_addons()
        loaded_addons = self.addon_manager.get_loaded_addons()

        if not loaded_addons:
            # Show "no addons" message
            no_addons_label = QLabel("No addons found")
            no_addons_label.setAlignment(Qt.AlignCenter)
            no_addons_label.setStyleSheet("color: #666; font-style: italic;")
            no_addons_label.setWordWrap(True)
            self.button_layout.addWidget(no_addons_label)

            # Show hint
            hint_label = QLabel("Add addons to\n./addons/ folder")
            hint_label.setAlignment(Qt.AlignCenter)
            hint_label.setStyleSheet("color: #888; font-size: 10px;")
            hint_label.setWordWrap(True)
            self.button_layout.addWidget(hint_label)
        else:
            # Create buttons for each loaded addon
            for addon_name in sorted(loaded_addons):
                self.create_addon_button(addon_name)

        # Add stretch to push buttons to top
        self.button_layout.addStretch()

    def create_addon_button(self, addon_name: str):
        """Create a button for an addon"""
        metadata = self.addon_manager.get_addon_metadata(addon_name)

        # Get display name and icon
        display_name = metadata.get('display_name', addon_name)
        icon = metadata.get('icon', '🔧')
        description = metadata.get('description', f'Open {addon_name} addon')

        # Create button
        btn = QPushButton(f"{icon} {display_name}")
        btn.setMinimumHeight(35)
        btn.setFont(QFont(FONT_FAMILY, 9))
        btn.setToolTip(description)
        btn.clicked.connect(lambda checked, name=addon_name: self.open_addon(name))

        # Style button based on whether dialog is open
        self.update_button_style(btn, addon_name)

        self.button_layout.addWidget(btn)
        self.addon_buttons[addon_name] = btn

    def update_button_style(self, button: QPushButton, addon_name: str):
        """Update button style based on addon state"""
        if self.addon_manager.is_addon_dialog_open(addon_name):
            button.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; }")
        else:
            button.setStyleSheet("")

    def open_addon(self, addon_name: str):
        """Open an addon in a popup dialog"""
        self.addon_manager.open_addon_dialog(addon_name, self.parent())

        # Update button style after opening
        if addon_name in self.addon_buttons:
            # Use QTimer to update after dialog is fully opened
            QTimer.singleShot(100, lambda: self.update_button_style(
                self.addon_buttons[addon_name], addon_name
            ))

    def close_all_addons(self):
        """Close all addon dialogs"""
        self.addon_manager.close_all_dialogs()

        # Update all button styles
        for addon_name, button in self.addon_buttons.items():
            self.update_button_style(button, addon_name)

    def update_button_states(self):
        """Update button states based on dialog visibility"""
        for addon_name, button in self.addon_buttons.items():
            self.update_button_style(button, addon_name)


class AddonSidebarFrame(QFrame):
    """Frame wrapper for AddonSidebar to match existing UI style"""

    def __init__(self, addon_manager, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.StyledPanel)
        self.setFixedWidth(200)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.addon_sidebar = AddonSidebar(addon_manager, self)
        layout.addWidget(self.addon_sidebar)

        # Timer to periodically update button states
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.addon_sidebar.update_button_states)
        self.update_timer.start(1000)  # Update every second

    def refresh_addons(self):
        """Refresh addons"""
        self.addon_sidebar.refresh_addons()