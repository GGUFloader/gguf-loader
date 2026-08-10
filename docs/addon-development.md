# Addon Development Guide

Learn how to create custom addons for GGUF Loader.

## What is an Addon?

Addons extend GGUF Loader's functionality with custom features. They can:
- Add new UI components
- Process text in custom ways
- Integrate with external services
- Create specialized workflows

## Addon Structure

### Basic Structure

```
addons/
└── your_addon/
    ├── __init__.py          # Required: Makes it a Python package
    ├── main.py              # Required: Entry point
    ├── README.md            # Optional: Documentation
    └── requirements.txt     # Optional: Dependencies
```

### Minimal Example

**`addons/hello_world/__init__.py`:**
```python
# Empty file or package initialization
```

**`addons/hello_world/main.py`:**
```python
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton

class HelloWorldAddon(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        label = QLabel("Hello from addon!")
        button = QPushButton("Click Me")
        button.clicked.connect(self.on_click)
        
        layout.addWidget(label)
        layout.addWidget(button)
    
    def on_click(self):
        print("Button clicked!")

# Required: Entry point function
def create_addon(parent=None):
    return HelloWorldAddon(parent)
```

## Addon API

### Required Functions

Every addon must implement:

```python
def create_addon(parent=None):
    """
    Entry point for the addon.
    
    Args:
        parent: Parent widget (usually the main window)
    
    Returns:
        QWidget: Your addon's main widget
    """
    return YourAddonWidget(parent)
```

### Accessing Main Application

Get reference to the main application:

```python
def create_addon(parent=None):
    addon = YourAddon(parent)
    
    # Access main window
    main_window = parent
    
    # Access chat generator
    if hasattr(main_window, 'chat_generator'):
        chat_gen = main_window.chat_generator
    
    return addon
```

### Using the Chat Generator

Process text with the loaded model:

```python
class YourAddon(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
    
    def process_text(self, text):
        if not hasattr(self.main_window, 'chat_generator'):
            return "No model loaded"
        
        chat_gen = self.main_window.chat_generator
        
        # Generate response
        response = chat_gen.generate_response(
            prompt=text,
            system_prompt="You are a helpful assistant.",
            temperature=0.7,
            max_tokens=500
        )
        
        return response
```

## Advanced Features

### Global Hotkeys

Register system-wide keyboard shortcuts:

```python
from pynput import keyboard

class HotkeyAddon(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_hotkey()
    
    def setup_hotkey(self):
        def on_activate():
            print("Hotkey pressed!")
        
        hotkey = keyboard.GlobalHotKeys({
            '<ctrl>+<shift>+a': on_activate
        })
        hotkey.start()
```

### Clipboard Monitoring

Monitor clipboard for changes:

```python
from PySide6.QtWidgets import QApplication

class ClipboardAddon(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.clipboard = QApplication.clipboard()
        self.clipboard.dataChanged.connect(self.on_clipboard_change)
    
    def on_clipboard_change(self):
        text = self.clipboard.text()
        print(f"Clipboard changed: {text}")
```

### Text Selection Detection

Detect when user selects text:

```python
import pyperclip
from pynput import mouse

class SelectionAddon(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_mouse_listener()
    
    def setup_mouse_listener(self):
        def on_click(x, y, button, pressed):
            if not pressed and button == mouse.Button.left:
                # Small delay to let selection complete
                QTimer.singleShot(100, self.check_selection)
        
        listener = mouse.Listener(on_click=on_click)
        listener.start()
    
    def check_selection(self):
        # Get selected text via clipboard
        selected = pyperclip.paste()
        if selected:
            print(f"Selected: {selected}")
```

## UI Components

### Using PySide6 Widgets

```python
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit,
    QTextEdit, QComboBox, QCheckBox
)

class UIAddon(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        
        # Text input
        self.input = QLineEdit()
        self.input.setPlaceholderText("Enter text...")
        
        # Button
        btn = QPushButton("Process")
        btn.clicked.connect(self.on_process)
        
        # Text output
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        
        layout.addWidget(self.input)
        layout.addWidget(btn)
        layout.addWidget(self.output)
    
    def on_process(self):
        text = self.input.text()
        self.output.setText(f"Processed: {text}")
```

### Styling

Apply custom styles:

```python
class StyledAddon(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QWidget {
                background-color: #f0f0f0;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
```

## Configuration

### Saving Settings

```python
import json
import os

class ConfigurableAddon(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_file = "addons/your_addon/config.json"
        self.load_config()
    
    def load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
        else:
            self.config = {"setting1": "value1"}
    
    def save_config(self):
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
```

## Testing Your Addon

### 1. Place in Addons Folder

```bash
addons/
└── your_addon/
    ├── __init__.py
    └── main.py
```

### 2. Restart Application

The addon will be automatically detected.

### 3. Check Addon Sidebar

Your addon should appear in the left sidebar.

### 4. Debug Output

Use print statements or logging:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class DebugAddon(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        logger.debug("Addon initialized")
```

## Best Practices

### Error Handling

Always handle errors gracefully:

```python
def process_text(self, text):
    try:
        result = self.do_processing(text)
        return result
    except Exception as e:
        logger.error(f"Error processing text: {e}")
        return f"Error: {str(e)}"
```

### Resource Cleanup

Clean up resources when addon is closed:

```python
class ResourceAddon(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.listener = self.start_listener()
    
    def closeEvent(self, event):
        # Clean up
        if self.listener:
            self.listener.stop()
        super().closeEvent(event)
```

### Performance

- Use threading for long operations
- Cache results when possible
- Minimize UI updates

```python
from PySide6.QtCore import QThread, Signal

class Worker(QThread):
    finished = Signal(str)
    
    def __init__(self, text):
        super().__init__()
        self.text = text
    
    def run(self):
        result = self.process(self.text)
        self.finished.emit(result)

class ThreadedAddon(QWidget):
    def process_async(self, text):
        worker = Worker(text)
        worker.finished.connect(self.on_finished)
        worker.start()
    
    def on_finished(self, result):
        print(f"Result: {result}")
```

## Example: Smart Floater

See the built-in Smart Floating Assistant for a complete example:

```
addons/floating_chat/
├── __init__.py
├── main.py              # Entry point
├── floating_button.py   # Floating button widget
├── chat_window.py       # Popup window
└── README.md           # Documentation
```

Study this addon to learn:
- Global text selection detection
- Floating UI elements
- Integration with chat generator
- Cross-platform compatibility

## Publishing Your Addon

### 1. Create README

Document your addon:
- What it does
- How to use it
- Configuration options
- Dependencies

### 2. Add Requirements

If your addon needs extra packages:

```
# addons/your_addon/requirements.txt
requests==2.28.0
beautifulsoup4==4.11.0
```

### 3. Share

- Create a GitHub repository
- Share on GGUF Loader discussions
- Submit to addon directory (coming soon)

## Getting Help

- Check existing addons for examples
- Ask in [GitHub Discussions](https://github.com/GGUFloader/gguf-loader/discussions)
- Report issues on [GitHub](https://github.com/GGUFloader/gguf-loader/issues)
