#!/usr/bin/env python3
"""
GGUF Loader Application - Main entry point with addon support

This is the proper GGUF Loader application that the Smart Floating Assistant
addon is designed to work with.
"""

import os
import sys
import platform
import logging
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
# Handle imports for both module and standalone execution
try:
    from .resource_manager import find_icon, get_dll_path
    from .models.model_loader import ModelLoader
    from .addon_manager import AddonManager, AddonSidebarFrame
    from .ui.ai_chat_window import AIChat
except ImportError:
    # Fallback for standalone execution
    from resource_manager import find_icon, get_dll_path
    from models.model_loader import ModelLoader
    from addon_manager import AddonManager, AddonSidebarFrame
    from ui.ai_chat_window import AIChat

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_dll_folder():
    """Add DLL/library directory for llama.cpp when needed (cross-platform)."""
    try:
        # Import here to avoid circular imports
        from resource_manager import get_dll_path
        
        dll_path = get_dll_path()
        if not dll_path or not os.path.exists(dll_path):
            logger.debug("No valid DLL path found")
            return
            
        system_name = platform.system()
        logger.debug(f"Setting up library path for {system_name}")
        
        if system_name == "Windows":
            # Windows-specific DLL directory handling
            if hasattr(os, 'add_dll_directory'):
                os.add_dll_directory(dll_path)
                logger.info(f"✅ Added Windows DLL directory: {dll_path}")
            else:
                logger.warning("os.add_dll_directory not available on this Python version")
                
        elif system_name == "Linux":
            # Linux: use LD_LIBRARY_PATH
            env_var = "LD_LIBRARY_PATH"
            current_path = os.environ.get(env_var, "")
            path_components = current_path.split(os.pathsep) if current_path else []
            
            if dll_path not in path_components:
                path_components.insert(0, dll_path)  # Add at beginning for priority
                os.environ[env_var] = os.pathsep.join(path_components)
                logger.info(f"✅ Added to {env_var}: {dll_path}")
            else:
                logger.debug(f"Path already in {env_var}: {dll_path}")
                
        elif system_name == "Darwin":
            # macOS: use DYLD_LIBRARY_PATH
            env_var = "DYLD_LIBRARY_PATH"
            current_path = os.environ.get(env_var, "")
            path_components = current_path.split(os.pathsep) if current_path else []
            
            if dll_path not in path_components:
                path_components.insert(0, dll_path)
                os.environ[env_var] = os.pathsep.join(path_components)
                logger.info(f"✅ Added to {env_var}: {dll_path}")
            else:
                logger.debug(f"Path already in {env_var}: {dll_path}")
                
        else:
            logger.warning(f"Unsupported platform for automatic library setup: {system_name}")
            
    except ImportError as e:
        logger.warning(f"Could not import get_dll_path: {e}")
    except Exception as e:
        logger.warning(f"Could not setup library path: {e}")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GGUFLoaderApp(QMainWindow):
    """
    Main GGUF Loader application with addon support.
    
    This application provides:
    - GGUF model loading and management
    - Addon system for extensions
    - Model backend access for addons
    """
    
    # Signals for addon integration
    model_loaded = Signal(object)
    model_unloaded = Signal()
    
    def __init__(self):
        super().__init__()
        
        # Initialize application properties
        self.setWindowTitle("GGUF Loader with Addons")
        self.setMinimumSize(1200, 800)
        
        # Set window icon (application icon should already be set)
        icon_path = find_icon("icon.ico")
        if os.path.exists(icon_path):
            window_icon = QIcon(icon_path)
            self.setWindowIcon(window_icon)
            logger.info(f"Window icon set from: {icon_path}")
        else:
            logger.warning(f"Icon not found at: {icon_path}")
        
        # Initialize model-related attributes
        self.model = None
        self.model_loader = None
        
        # Initialize addon system
        self.addon_manager = AddonManager()
        
        # Setup UI
        self._setup_ui()
        
        # Load addons after UI is ready
        self._load_addons()
        
        logger.info("GGUF Loader application initialized")
    

    
    def _setup_ui(self):
        """Setup the main user interface."""
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create splitter for layout
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # Add addon sidebar
        self.addon_sidebar = AddonSidebarFrame(self.addon_manager, self)
        splitter.addWidget(self.addon_sidebar)
        
        # Add main AI chat interface
        self.ai_chat = AIChat()
        
        # Connect model signals
        self.ai_chat.model_loaded.connect(self._on_model_loaded)
        
        # Create a container for the AI chat
        chat_container = QWidget()
        chat_layout = QVBoxLayout(chat_container)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        
        # Remove the AI chat from its parent and add to our container
        self.ai_chat.setParent(None)
        chat_layout.addWidget(self.ai_chat)
        
        splitter.addWidget(chat_container)
        
        # Set splitter proportions (addon sidebar, main content)
        splitter.setSizes([200, 1000])
        
        logger.info("UI setup completed")
    
    def _load_addons(self):
        """Load all available addons."""
        try:
            results = self.addon_manager.load_all_addons()
            loaded_addons = self.addon_manager.get_loaded_addons()
            
            logger.info(f"Addon loading results: {results}")
            logger.info(f"Successfully loaded addons: {loaded_addons}")
            
            # Initialize loaded addons by calling their register functions
            for addon_name in loaded_addons:
                try:
                    # Call the addon's register function with this app as parent
                    widget = self.addon_manager.get_addon_widget(addon_name, self)
                    logger.info(f"Initialized addon '{addon_name}': {widget}")
                except Exception as e:
                    logger.error(f"Failed to initialize addon '{addon_name}': {e}")
                    
        except Exception as e:
            logger.error(f"Error loading addons: {e}")
    
    def _on_model_loaded(self, model):
        """Handle model loaded event from AI chat."""
        self.model = model
        logger.info(f"Model loaded: {type(model)}")
        
        # Emit signal for addons
        self.model_loaded.emit(model)
        
        # Notify any running addons about the model
        if hasattr(self, '_simple_floater'):
            try:
                self._simple_floater.on_model_loaded(model)
            except Exception as e:
                logger.error(f"Error notifying smart floater addon about model: {e}")
    
    def _on_model_unloaded(self):
        """Handle model unloaded event."""
        self.model = None
        logger.info("Model unloaded")
        
        # Emit signal for addons
        self.model_unloaded.emit()
        
        # Notify any running addons about model unloading
        if hasattr(self, '_simple_floater'):
            try:
                self._simple_floater.model = None
                logger.info("Notified addon about model unloading")
            except Exception as e:
                logger.error(f"Error notifying smart floater addon about model unloading: {e}")
    
    def get_model_backend(self):
        """Get the current model backend for addons."""
        return self.model
    
    def is_model_loaded(self) -> bool:
        """Check if a model is currently loaded."""
        return self.model is not None
    
    def closeEvent(self, event):
        """Handle application close event."""
        try:
            # Stop any running addons
            if hasattr(self, '_simple_floater'):
                try:
                    self._simple_floater.stop()
                    logger.info("Smart Floater addon stopped")
                except Exception as e:
                    logger.error(f"Error stopping smart floater addon: {e}")
            
            # Close AI chat component
            if hasattr(self, 'ai_chat'):
                self.ai_chat.close()
            
            logger.info("GGUF Loader application closing")
            event.accept()
            
        except Exception as e:
            logger.error(f"Error during application close: {e}")
            event.accept()


def main():
    """Main entry point for GGUF Loader application."""
    # Handle command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] in ['--version', '-v']:
            from __init__ import __version__
            print(f"GGUF Loader version {__version__}")
            return
        elif sys.argv[1] in ['--help', '-h']:
            print("GGUF Loader - Advanced GGUF Model Loader with Smart Floating Assistant")
            print("\nUsage: ggufloader [options]")
            print("\nOptions:")
            print("  --version, -v    Show version information")
            print("  --help, -h       Show this help message")
            return
    
    # Add DLL folder for llama.cpp
    add_dll_folder()
    
    # Create QApplication
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("GGUF Loader")
    app.setApplicationVersion("2.0.1")
    app.setOrganizationName("GGUF Loader Team")
    
    # Set application icon early
    icon_path = find_icon("icon.ico")
    if os.path.exists(icon_path):
        app_icon = QIcon(icon_path)
        app.setWindowIcon(app_icon)
        logger.info(f"Application icon set from: {icon_path}")
    
    try:
        # Create and show main window
        window = GGUFLoaderApp()
        window.show()
        
        # Run application
        sys.exit(app.exec())
        
    except Exception as e:
        logger.error(f"Failed to start GGUF Loader application: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
