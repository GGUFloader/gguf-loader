"""
Addon Mixin - Integrates addon system into existing UI following project structure
"""
from PySide6.QtWidgets import QSplitter
from PySide6.QtCore import Qt

from addon_manager import AddonManager
from widgets.addon_sidebar import AddonSidebarFrame


class AddonMixin:
    """Mixin to integrate addon system into existing UI"""

    def __init__(self):
        # Initialize addon manager
        self.addon_manager = AddonManager()
        super().__init__()

    def setup_main_layout(self):
        """Override to include addon sidebar in main layout"""
        # Call parent setup first
        super().setup_main_layout()

        # Find the existing splitter
        central_widget = self.centralWidget()
        main_layout = central_widget.layout()

        # Get the existing splitter (should be the only widget in main_layout)
        existing_splitter = main_layout.itemAt(0).widget()

        # Create new horizontal splitter to hold addon sidebar and existing content
        new_splitter = QSplitter(Qt.Horizontal)

        # Remove existing splitter from main layout
        main_layout.removeWidget(existing_splitter)

        # Add addon sidebar to new splitter
        self.addon_sidebar_frame = AddonSidebarFrame(self.addon_manager, self)
        new_splitter.addWidget(self.addon_sidebar_frame)

        # Add existing splitter to new splitter
        new_splitter.addWidget(existing_splitter)

        # Add new splitter to main layout
        main_layout.addWidget(new_splitter)

        # Set splitter proportions: addon sidebar (200px) | existing content
        new_splitter.setSizes([200, 1100])

        # Make addon sidebar non-resizable
        new_splitter.setStretchFactor(0, 0)  # Addon sidebar doesn't stretch
        new_splitter.setStretchFactor(1, 1)  # Existing content stretches

        # Connect to existing methods if they exist
        if hasattr(self, 'setup_addon_connections'):
            self.setup_addon_connections()

    def setup_addon_connections(self):
        """Override this method to setup connections between addons and main app"""
        pass

    def refresh_addons(self):
        """Refresh the addon list"""
        if hasattr(self, 'addon_sidebar_frame'):
            self.addon_sidebar_frame.addon_sidebar.refresh_addons()

    def get_addon_manager(self):
        """Get the addon manager instance"""
        return self.addon_manager

    def get_loaded_addons(self):
        """Get list of loaded addon names"""
        return self.addon_manager.get_loaded_addons()

    def open_addon(self, addon_name):
        """Open a specific addon by name"""
        self.addon_manager.open_addon_dialog(addon_name, self)

    def close_addon(self, addon_name):
        """Close a specific addon dialog"""
        if addon_name in self.addon_manager.addon_dialogs:
            dialog = self.addon_manager.addon_dialogs[addon_name]
            dialog.close()

    def close_all_addons(self):
        """Close all addon dialogs"""
        for dialog in list(self.addon_manager.addon_dialogs.values()):
            dialog.close()

    def get_addon_dialog(self, addon_name):
        """Get addon dialog if it exists and is open"""
        return self.addon_manager.addon_dialogs.get(addon_name)