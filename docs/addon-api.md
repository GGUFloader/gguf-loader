# Addon API Reference

Complete API reference for developing GGUF Loader addons.

## 🏗️ Core API

### Addon Registration

Every addon must implement a `register()` function:

```python
def register(parent=None):
    """
    Register function called by GGUF Loader when loading the addon.
    
    Args:
        parent: The main GGUF Loader application instance
        
    Returns:
        QWidget: The addon's UI widget, or None for background addons
    """
    pass
```

### Main Application Interface

The `parent` parameter provides access to the main GGUF Loader application:

```python
class GGUFLoaderApp:
    """Main GGUF Loader application interface."""
    
    # Properties
    model: Optional[Any]              # Currently loaded GGUF model
    ai_chat: AIChat                   # AI chat interface
    addon_manager: AddonManager       # Addon management system
    
    # Methods
    def get_model_backend(self) -> Optional[Any]:
        """Get the current model backend for addons."""
        
    def is_model_loaded(self) -> bool:
        """Check if a model is currently loaded."""
        
    # Signals
    model_loaded = Signal(object)     # Emitted when model is loaded
    model_unloaded = Signal()         # Emitted when model is unloaded
```

## 🤖 Model API

### Accessing the Model

```python
def get_model(self, gguf_app):
    """Get the currently loaded GGUF model."""
    try:
        # Method 1: Direct access
        if hasattr(gguf_app, 'model') and gguf_app.model:
            return gguf_app.model
            
        # Method 2: Through AI chat
        if hasattr(gguf_app, 'ai_chat') and hasattr(gguf_app.ai_chat, 'model'):
            return gguf_app.ai_chat.model
            
        # Method 3: Backend method
        if hasattr(gguf_app, 'get_model_backend'):
            return gguf_app.get_model_backend()
            
        return None
    except Exception as e:
        logging.error(f"Error getting model: {e}")
        return None
```

### Model Interface

```python
class LlamaModel:
    """GGUF Model interface (llama-cpp-python)."""
    
    def __call__(self, 
                 prompt: str,
                 max_tokens: int = 256,
                 temperature: float = 0.7,
                 top_p: float = 0.9,
                 top_k: int = 40,
                 repeat_penalty: float = 1.1,
                 stop: List[str] = None,
                 stream: bool = False) -> Union[str, Dict, Iterator]:
        """Generate text from the model."""
        pass
    
    def tokenize(self, text: str) -> List[int]:
        """Tokenize text."""
        pass
        
    def detokenize(self, tokens: List[int]) -> str:
        """Detokenize tokens to text."""
        pass
```

### Text Generation

```python
def generate_text(self, model, prompt: str, **kwargs) -> str:
    """Generate text using the model."""
    try:
        response = model(
            prompt,
            max_tokens=kwargs.get('max_tokens', 200),
            temperature=kwargs.get('temperature', 0.7),
            top_p=kwargs.get('top_p', 0.9),
            repeat_penalty=kwargs.get('repeat_penalty', 1.1),
            stop=kwargs.get('stop', ["</s>", "\n\n"]),
            stream=False
        )
        
        return self.extract_response_text(response)
        
    except Exception as e:
        logging.error(f"Text generation failed: {e}")
        return f"Error: {str(e)}"

def extract_response_text(self, response) -> str:
    """Extract text from model response."""
    if isinstance(response, dict) and 'choices' in response:
        return response['choices'][0].get('text', '').strip()
    elif isinstance(response, str):
        return response.strip()
    else:
        return str(response).strip()
```

## 🎨 UI API

### Widget Creation

```python
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PySide6.QtCore import QTimer, Signal

class AddonWidget(QWidget):
    """Base addon widget class."""
    
    # Signals
    text_processed = Signal(str)
    error_occurred = Signal(str)
    
    def __init__(self, addon_instance):
        super().__init__()
        self.addon = addon_instance
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the widget UI."""
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("My Addon")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)
        
        # Content
        self.setup_content(layout)
    
    def setup_content(self, layout):
        """Override this method to add custom content."""
        pass
```

### Common UI Components

```python
# Status indicator
def create_status_indicator(self):
    """Create a status indicator widget."""
    self.status_label = QLabel("Ready")
    self.status_label.setStyleSheet("""
        QLabel {
            padding: 5px;
            border-radius: 3px;
            background-color: #4CAF50;
            color: white;
        }
    """)
    return self.status_label

def update_status(self, message: str, status_type: str = "info"):
    """Update status indicator."""
    colors = {
        "info": "#2196F3",
        "success": "#4CAF50", 
        "warning": "#FF9800",
        "error": "#F44336"
    }
    
    self.status_label.setText(message)
    self.status_label.setStyleSheet(f"""
        QLabel {{
            padding: 5px;
            border-radius: 3px;
            background-color: {colors.get(status_type, colors['info'])};
            color: white;
        }}
    """)

# Progress indicator
def create_progress_indicator(self):
    """Create a progress indicator."""
    from PySide6.QtWidgets import QProgressBar
    
    self.progress_bar = QProgressBar()
    self.progress_bar.setVisible(False)
    return self.progress_bar

def show_progress(self, message: str = "Processing..."):
    """Show progress indicator."""
    self.progress_bar.setVisible(True)
    self.progress_bar.setRange(0, 0)  # Indeterminate
    self.update_status(message, "info")

def hide_progress(self):
    """Hide progress indicator."""
    self.progress_bar.setVisible(False)
```

### Floating UI Components

```python
from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor

class FloatingWidget(QWidget):
    """Create floating widgets like the Smart Assistant."""
    
    def __init__(self):
        super().__init__()
        self.setup_floating_widget()
    
    def setup_floating_widget(self):
        """Setup floating widget properties."""
        self.setWindowFlags(
            Qt.ToolTip | 
            Qt.FramelessWindowHint | 
            Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        
    def show_near_cursor(self, offset_x: int = 10, offset_y: int = -40):
        """Show widget near cursor position."""
        cursor_pos = QCursor.pos()
        self.move(cursor_pos.x() + offset_x, cursor_pos.y() + offset_y)
        self.show()
```

## 🔧 System Integration API

### Text Selection Detection

```python
import pyautogui
import pyperclip
from PySide6.QtCore import QTimer

class TextSelectionMonitor:
    """Monitor for global text selection."""
    
    def __init__(self, callback):
        self.callback = callback
        self.last_clipboard = ""
        self.selected_text = ""
        
        # Timer for checking selection
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_selection)
        self.timer.start(300)  # Check every 300ms
    
    def check_selection(self):
        """Check for text selection."""
        try:
            # Save current clipboard
            original_clipboard = pyperclip.paste()
            
            # Copy selection
            pyautogui.hotkey('ctrl', 'c')
            
            # Process after small delay
            QTimer.singleShot(50, lambda: self.process_selection(original_clipboard))
            
        except Exception as e:
            logging.debug(f"Selection check failed: {e}")
    
    def process_selection(self, original_clipboard):
        """Process the selection."""
        try:
            current_text = pyperclip.paste()
            
            # Check if we got new selected text
            if (current_text != original_clipboard and 
                current_text and 
                len(current_text.strip()) > 3):
                
                self.selected_text = current_text.strip()
                self.callback(self.selected_text)
            
            # Restore clipboard
            pyperclip.copy(original_clipboard)
            
        except Exception as e:
            logging.debug(f"Selection processing failed: {e}")
    
    def stop(self):
        """Stop monitoring."""
        self.timer.stop()
```

### Clipboard Integration

```python
import pyperclip

class ClipboardManager:
    """Manage clipboard operations."""
    
    @staticmethod
    def get_text() -> str:
        """Get text from clipboard."""
        try:
            return pyperclip.paste()
        except Exception as e:
            logging.error(f"Failed to get clipboard text: {e}")
            return ""
    
    @staticmethod
    def set_text(text: str) -> bool:
        """Set text to clipboard."""
        try:
            pyperclip.copy(text)
            return True
        except Exception as e:
            logging.error(f"Failed to set clipboard text: {e}")
            return False
    
    @staticmethod
    def append_text(text: str) -> bool:
        """Append text to clipboard."""
        try:
            current = ClipboardManager.get_text()
            new_text = f"{current}\n{text}" if current else text
            return ClipboardManager.set_text(new_text)
        except Exception as e:
            logging.error(f"Failed to append clipboard text: {e}")
            return False
```

### Hotkey Registration

```python
import keyboard

class HotkeyManager:
    """Manage global hotkeys."""
    
    def __init__(self):
        self.registered_hotkeys = {}
    
    def register_hotkey(self, hotkey: str, callback, description: str = ""):
        """Register a global hotkey."""
        try:
            keyboard.add_hotkey(hotkey, callback)
            self.registered_hotkeys[hotkey] = {
                'callback': callback,
                'description': description
            }
            logging.info(f"Registered hotkey: {hotkey}")
            return True
        except Exception as e:
            logging.error(f"Failed to register hotkey {hotkey}: {e}")
            return False
    
    def unregister_hotkey(self, hotkey: str):
        """Unregister a hotkey."""
        try:
            keyboard.remove_hotkey(hotkey)
            if hotkey in self.registered_hotkeys:
                del self.registered_hotkeys[hotkey]
            logging.info(f"Unregistered hotkey: {hotkey}")
            return True
        except Exception as e:
            logging.error(f"Failed to unregister hotkey {hotkey}: {e}")
            return False
    
    def cleanup(self):
        """Clean up all registered hotkeys."""
        for hotkey in list(self.registered_hotkeys.keys()):
            self.unregister_hotkey(hotkey)
```

## 📁 Configuration API

### Addon Configuration

```python
import json
import os
from pathlib import Path

class AddonConfig:
    """Manage addon configuration."""
    
    def __init__(self, addon_name: str):
        self.addon_name = addon_name
        self.config_dir = Path.home() / ".ggufloader" / "addons" / addon_name
        self.config_file = self.config_dir / "config.json"
        self.config = {}
        self.load_config()
    
    def load_config(self):
        """Load configuration from file."""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
        except Exception as e:
            logging.error(f"Failed to load config: {e}")
            self.config = {}
    
    def save_config(self):
        """Save configuration to file."""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to save config: {e}")
    
    def get(self, key: str, default=None):
        """Get configuration value."""
        return self.config.get(key, default)
    
    def set(self, key: str, value):
        """Set configuration value."""
        self.config[key] = value
        self.save_config()
    
    def update(self, updates: dict):
        """Update multiple configuration values."""
        self.config.update(updates)
        self.save_config()
```

## 🔄 Event System API

### Addon Events

```python
from PySide6.QtCore import QObject, Signal

class AddonEventSystem(QObject):
    """Event system for addon communication."""
    
    # Core events
    addon_loaded = Signal(str)           # addon_name
    addon_unloaded = Signal(str)         # addon_name
    model_changed = Signal(object)       # model
    text_selected = Signal(str)          # selected_text
    text_processed = Signal(str, str)    # original_text, processed_text
    
    def __init__(self):
        super().__init__()
        self.event_handlers = {}
    
    def emit_event(self, event_name: str, *args, **kwargs):
        """Emit a custom event."""
        if hasattr(self, event_name):
            signal = getattr(self, event_name)
            signal.emit(*args, **kwargs)
    
    def connect_event(self, event_name: str, handler):
        """Connect to an event."""
        if hasattr(self, event_name):
            signal = getattr(self, event_name)
            signal.connect(handler)
```

## 🧪 Testing API

### Addon Testing Utilities

```python
import unittest
from unittest.mock import Mock, MagicMock

class AddonTestCase(unittest.TestCase):
    """Base test case for addon testing."""
    
    def setUp(self):
        """Set up test environment."""
        self.mock_gguf_app = Mock()
        self.mock_model = Mock()
        self.mock_gguf_app.model = self.mock_model
        
    def create_mock_model_response(self, text: str):
        """Create a mock model response."""
        return {
            'choices': [{'text': text}]
        }
    
    def assert_model_called_with(self, expected_prompt: str):
        """Assert model was called with expected prompt."""
        self.mock_model.assert_called()
        call_args = self.mock_model.call_args
        self.assertIn(expected_prompt, call_args[0][0])

# Example test
class TestMyAddon(AddonTestCase):
    def test_text_processing(self):
        from addons.my_addon.main import MyAddon
        
        addon = MyAddon(self.mock_gguf_app)
        self.mock_model.return_value = self.create_mock_model_response("Processed text")
        
        result = addon.process_text("input text")
        
        self.assertEqual(result, "Processed text")
        self.assert_model_called_with("input text")
```

## 📊 Logging API

### Addon Logging

```python
import logging
from pathlib import Path

class AddonLogger:
    """Logging utilities for addons."""
    
    @staticmethod
    def setup_logger(addon_name: str, level=logging.INFO):
        """Setup logger for addon."""
        logger = logging.getLogger(f"addon.{addon_name}")
        logger.setLevel(level)
        
        # Create file handler
        log_dir = Path.home() / ".ggufloader" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_dir / f"{addon_name}.log")
        file_handler.setLevel(level)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        
        # Add handler to logger
        logger.addHandler(file_handler)
        
        return logger

# Usage in addon
logger = AddonLogger.setup_logger("my_addon")
logger.info("Addon initialized")
logger.error("Something went wrong")
```

## 🔒 Security API

### Safe Execution

```python
import subprocess
import tempfile
import os

class SafeExecution:
    """Utilities for safe code execution."""
    
    @staticmethod
    def run_command_safely(command: list, timeout: int = 30) -> tuple:
        """Run command safely with timeout."""
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Command timed out"
        except Exception as e:
            return -1, "", str(e)
    
    @staticmethod
    def create_temp_file(content: str, suffix: str = ".tmp") -> str:
        """Create temporary file safely."""
        with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False) as f:
            f.write(content)
            return f.name
    
    @staticmethod
    def cleanup_temp_file(filepath: str):
        """Clean up temporary file."""
        try:
            if os.path.exists(filepath):
                os.unlink(filepath)
        except Exception as e:
            logging.error(f"Failed to cleanup temp file: {e}")
```

## 📚 Additional Resources

- [Smart Floater Example](smart-floater-example.md) - Complete addon example
- [Addon Development Guide](addon-development.md) - Step-by-step development guide
- [Troubleshooting](troubleshooting.md) - Common issues and solutions

---

**Need help with the API? Join our [community discussions](https://github.com/gguf-loader/gguf-loader/discussions) or contact support@ggufloader.com**