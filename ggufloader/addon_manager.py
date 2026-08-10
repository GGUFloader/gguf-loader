"""
Addon Manager - Handles loading and managing addons for GGUF Loader
"""
import sys
import importlib
import importlib.util
from pathlib import Path
from typing import Dict, Optional, Callable, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QDialog, QMessageBox
)
from ggufloader.resource_manager import find_addons_dir


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
                f"ggufloader.addons.{addon_name}",
                addon_path
            )

            if spec is None or spec.loader is None:
                return False

            # Load the module. The addons live inside the ggufloader package
            # (both in dev and when pip-installed), so register under the real
            # package name - that keeps relative imports inside the addon
            # (e.g. `from .chat_window import ...`) resolvable.
            module = importlib.util.module_from_spec(spec)
            sys.modules[f"ggufloader.addons.{addon_name}"] = module
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

