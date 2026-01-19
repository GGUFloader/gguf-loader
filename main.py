#!/usr/bin/env python3
"""
Main entry point for the Advanced Local AI Chat Application
"""
import os
import sys
import platform
import logging
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from models.model_loader import ModelLoader
from utils import load_fonts
from ui.ai_chat_window import AIChat
from resource_manager import find_icon, get_dll_path

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
def main():
    # Handle command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] in ['--version', '-v']:
            from __init__ import __version__
            print(f"GGUF Loader Basic version {__version__}")
            return
        elif sys.argv[1] in ['--help', '-h']:
            print("GGUF Loader Basic - Simple GGUF Model Loader")
            print("\nUsage: ggufloader-basic [options]")
            print("\nOptions:")
            print("  --version, -v    Show version information")
            print("  --help, -h       Show this help message")
            return

    add_dll_folder()

    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("GGUF Loader Basic")
    app.setApplicationVersion("2.0.1")
    app.setOrganizationName("GGUF Loader Team")

    # Set application icon for taskbar & alt-tab
    icon_path = find_icon("icon.ico")
    print(f"[DEBUG] Loading icon from: {icon_path}")
    print(f"[DEBUG] Icon file exists: {os.path.exists(icon_path)}")
    if os.path.exists(icon_path):
        icon = QIcon(icon_path)
        print(f"[DEBUG] Icon loaded successfully: {not icon.isNull()}")
        print(f"[DEBUG] Icon available sizes: {icon.availableSizes()}")
        
        # Set icon for both application and future windows
        app.setWindowIcon(icon)
        
        # Force icon refresh by setting it multiple times with different methods
        if not icon.isNull():
            # Try setting with different sizes to ensure compatibility
            for size in [16, 32, 48, 64]:
                pixmap = icon.pixmap(size, size)
                if not pixmap.isNull():
                    sized_icon = QIcon(pixmap)
                    app.setWindowIcon(sized_icon)
                    break
    else:
        print(f"[WARNING] Icon not found at: {icon_path}")
        # Try to create a fallback icon
        try:
            from PySide6.QtGui import QPixmap, QPainter, QBrush, QColor
            from PySide6.QtCore import Qt
            
            pixmap = QPixmap(32, 32)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setBrush(QBrush(QColor(70, 130, 180)))
            painter.drawRoundedRect(4, 4, 24, 24, 4, 4)
            painter.end()
            
            fallback_icon = QIcon(pixmap)
            app.setWindowIcon(fallback_icon)
            print("[INFO] Using fallback icon")
        except Exception as e:
            print(f"[WARNING] Could not create fallback icon: {e}")

    # Load fonts
    load_fonts()

    # Create and show main window
    window = AIChat()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
