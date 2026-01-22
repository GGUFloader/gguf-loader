"""
Addon Manager - Handles loading and managing addons for GGUF Loader
"""
import os
import sys
import importlib
import importlib.util
from pathlib import Path
from typing import Dict, Optional, Callable, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QDialog, QFrame, QScrollArea, QMessageBox
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont
from resource_manager import find_addons_dir

try:
    from config import FONT_FAMILY
except ImportError:
    FONT_FAMILY = "Arial"  # Fallback if config not found


class AddonManager:
    """Manages loading and registration of addons"""

    def __init__(self, addons_dir: str = None):
        if addons_dir is None:
            # Use the resource manager to find addons directory
            self.addons_dir = Path(find_addons_dir())
        else:
            self.addons_dir = Path(addons_dir)
        self.loaded_addons: Dict[str, Any] = {}
        self.addon_widgets: Dict[str, Callable] = {}
        self.addon_dialogs: Dict[str, QDialog] = {}

    def scan_addons(self) -> Dict[str, str]:
        """Scan the addons directory and return available addons"""
        addons = {}

        if not self.addons_dir.exists():
            self.addons_dir.mkdir(parents=True, exist_ok=True)
            return addons

        for addon_path in self.addons_dir.iterdir():
            if addon_path.is_dir():
                init_file = addon_path / "__init__.py"
                if init_file.exists():
                    addons[addon_path.name] = str(init_file)

        return addons

    def load_addon(self, addon_name: str, addon_path: str) -> bool:
        """Load a single addon module"""
        # Check if already loaded
        if addon_name in self.loaded_addons:
            return True
            
        try:
            # Create module spec
            spec = importlib.util.spec_from_file_location(
                f"addons.{addon_name}",
                addon_path
            )

            if spec is None or spec.loader is None:
                return False

            # Load the module
            module = importlib.util.module_from_spec(spec)
            sys.modules[f"addons.{addon_name}"] = module
            spec.loader.exec_module(module)

            # Check if register function exists
            if hasattr(module, 'register'):
                self.loaded_addons[addon_name] = module
                self.addon_widgets[addon_name] = module.register
                print(f"Successfully loaded addon {addon_name}")
                return True
            else:
                print(f"Addon {addon_name} does not have a register function")
                return False

        except Exception as e:
            print(f"Failed to load addon {addon_name}: {e}")
            import traceback
            traceback.print_exc()
            return False

        return False

    def load_all_addons(self) -> Dict[str, bool]:
        """Load all available addons"""
        results = {}
        addons = self.scan_addons()

        for addon_name, addon_path in addons.items():
            results[addon_name] = self.load_addon(addon_name, addon_path)

        return results

    def get_addon_widget(self, addon_name: str, parent=None) -> Optional[QWidget]:
        """Get widget from addon's register function"""
        if addon_name in self.addon_widgets:
            try:
                return self.addon_widgets[addon_name](parent)
            except Exception as e:
                print(f"Error getting widget from addon {addon_name}: {e}")
                return None
        return None

    def open_addon_dialog(self, addon_name: str, parent=None):
        """Open addon in a dialog popup"""
        # Reuse existing dialog if open
        if addon_name in self.addon_dialogs:
            dialog = self.addon_dialogs[addon_name]
            if dialog.isVisible():
                dialog.raise_()
                dialog.activateWindow()
                return
            else:
                # Dialog was closed, remove from cache
                del self.addon_dialogs[addon_name]

        # Create new dialog
        widget = self.get_addon_widget(addon_name, parent)
        if widget is None:
            QMessageBox.warning(
                parent,
                "Addon Error",
                f"Failed to load addon '{addon_name}'"
            )
            return

        dialog = QDialog(parent)
        dialog.setWindowTitle(f"Addon: {addon_name}")
        dialog.setModal(False)  # Non-modal so main window stays accessible
        dialog.resize(600, 400)

        # Setup dialog layout
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widget)

        # Store dialog reference
        self.addon_dialogs[addon_name] = dialog

        # Clean up when dialog is closed
        def cleanup():
            if addon_name in self.addon_dialogs:
                del self.addon_dialogs[addon_name]

        dialog.finished.connect(cleanup)

        # Show dialog
        dialog.show()

    def get_loaded_addons(self) -> list:
        """Get list of successfully loaded addon names"""
        return list(self.loaded_addons.keys())


class AddonSidebar(QWidget):
    """Sidebar widget for addon launcher buttons"""

    def __init__(self, addon_manager: AddonManager, parent=None):
        super().__init__(parent)
        self.addon_manager = addon_manager
        self.setup_ui()
        self.refresh_addons()  # Just refresh UI, don't reload addons

    def setup_ui(self):
        """Setup the sidebar UI"""
        self.setFixedWidth(200)
        # Note: QWidget doesn't have setFrameStyle, only QFrame does

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

        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setMinimumHeight(30)
        refresh_btn.clicked.connect(self.reload_addons)
        layout.addWidget(refresh_btn)

    def refresh_addons(self):
        """Refresh the addon list and recreate buttons"""
        # Clear existing buttons
        for i in reversed(range(self.button_layout.count())):
            child = self.button_layout.itemAt(i).widget()
            if child:
                child.setParent(None)

        # Get already loaded addons (don't reload them)
        loaded_addons = self.addon_manager.get_loaded_addons()

        if not loaded_addons:
            # Show "no addons" message
            no_addons_label = QLabel("No addons found")
            no_addons_label.setAlignment(Qt.AlignCenter)
            no_addons_label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
            no_addons_label.setStyleSheet("color: #666; font-style: italic;")
            self.button_layout.addWidget(no_addons_label)
        else:
            # Create buttons for each loaded addon
            for addon_name in sorted(loaded_addons):
                btn = QPushButton(addon_name)
                btn.setMinimumHeight(35)
                btn.setFont(QFont(FONT_FAMILY, 10))
                btn.clicked.connect(lambda checked, name=addon_name: self.open_addon(name))
                self.button_layout.addWidget(btn)

        # Add stretch to push buttons to top
        self.button_layout.addStretch()

    def reload_addons(self):
        """Reload all addons and refresh the UI"""
        # Actually reload addons
        results = self.addon_manager.load_all_addons()
        # Then refresh the UI
        self.refresh_addons()

    def open_addon(self, addon_name: str):
        """Open an addon in a popup dialog"""
        self.addon_manager.open_addon_dialog(addon_name, self.parent())


# Frame wrapper to match existing UI style
class AddonSidebarFrame(QFrame):
    """Frame wrapper for AddonSidebar to match existing UI style"""

    def __init__(self, addon_manager: AddonManager, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.StyledPanel)
        self.setFixedWidth(200)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.addon_sidebar = AddonSidebar(addon_manager, self)
        layout.addWidget(self.addon_sidebar)