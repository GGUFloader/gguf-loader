# Addon Development Guide

This guide will teach you how to create custom addons for GGUF Loader 2.0.0. Addons extend the functionality of GGUF Loader and can provide new features, UI components, and integrations.

## 🏗️ Addon Architecture

### What is an Addon?

An addon is a Python package that extends GGUF Loader's functionality. Addons can:

- Add new UI components and windows
- Process text and interact with AI models
- Integrate with external services
- Provide new workflows and automation
- Extend the main application's capabilities

### Addon Structure

Every addon must follow this basic structure:

```
addons/
└── your_addon_name/
    ├── __init__.py          # Addon entry point
    ├── main.py              # Main addon logic
    ├── ui.py                # UI components (optional)
    ├── config.py            # Configuration (optional)
    └── README.md            # Addon documentation
```

## 🚀 Creating Your First Addon

### Step 1: Create the Addon Directory

```bash
mkdir -p addons/my_awesome_addon
cd addons/my_awesome_addon
```

### Step 2: Create the Entry Point (`__init__.py`)

```python
"""
My Awesome Addon - A sample addon for GGUF Loader

This addon demonstrates the basic structure and capabilities
of the GGUF Loader addon system.
"""

__version__ = "1.0.0"
__author__ = "Your Name"
__description__ = "A sample addon that demonstrates basic functionality"

# Import the register function
from .main import register

# Export the register function
__all__ = ["register"]
```

### Step 3: Create the Main Logic (`main.py`)

```python
"""
Main logic for My Awesome Addon
"""

import logging
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QTextEdit
from PySide6.QtCore import QTimer

class MyAwesomeAddon:
    """Main addon class that handles the addon functionality."""
    
    def __init__(self, gguf_app):
        """Initialize the addon with reference to the main GGUF app."""
        self.gguf_app = gguf_app
        self.logger = logging.getLogger(__name__)
        self.is_running = False
        
        # Initialize your addon components here
        self.setup_addon()
    
    def setup_addon(self):
        """Setup the addon components."""
        self.logger.info("Setting up My Awesome Addon")
        # Add your initialization logic here
    
    def get_model(self):
        """Get the currently loaded GGUF model."""
        try:
            if hasattr(self.gguf_app, 'model') and self.gguf_app.model:
                return self.gguf_app.model
            elif hasattr(self.gguf_app, 'ai_chat') and hasattr(self.gguf_app.ai_chat, 'model'):
                return self.gguf_app.ai_chat.model
            return None
        except Exception as e:
            self.logger.error(f"Error getting model: {e}")
            return None
    
    def process_text_with_ai(self, text, prompt_template="Process this text: {text}"):
        """Process text using the loaded AI model."""
        model = self.get_model()
        if not model:
            return "Error: No AI model loaded"
        
        try:
            prompt = prompt_template.format(text=text)
            response = model(
                prompt,
                max_tokens=200,
                temperature=0.7,
                stop=["</s>", "\n\n"]
            )
            
            # Extract text from response
            if isinstance(response, dict) and 'choices' in response:
                return response['choices'][0].get('text', '').strip()
            elif isinstance(response, str):
                return response.strip()
            else:
                return str(response).strip()
                
        except Exception as e:
            self.logger.error(f"Error processing text: {e}")
            return f"Error: {str(e)}"
    
    def start(self):
        """Start the addon."""
        self.is_running = True
        self.logger.info("My Awesome Addon started")
    
    def stop(self):
        """Stop the addon."""
        self.is_running = False
        self.logger.info("My Awesome Addon stopped")


class MyAwesomeAddonWidget(QWidget):
    """UI widget for the addon."""
    
    def __init__(self, addon_instance):
        super().__init__()
        self.addon = addon_instance
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the addon UI."""
        self.setWindowTitle("My Awesome Addon")
        self.setMinimumSize(400, 300)
        
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("🚀 My Awesome Addon")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)
        
        # Description
        description = QLabel("This is a sample addon that demonstrates basic functionality.")
        description.setWordWrap(True)
        layout.addWidget(description)
        
        # Input area
        layout.addWidget(QLabel("Enter text to process:"))
        self.input_text = QTextEdit()
        self.input_text.setMaximumHeight(100)
        self.input_text.setPlaceholderText("Type some text here...")
        layout.addWidget(self.input_text)
        
        # Process button
        self.process_btn = QPushButton("🤖 Process with AI")
        self.process_btn.clicked.connect(self.process_text)
        layout.addWidget(self.process_btn)
        
        # Output area
        layout.addWidget(QLabel("AI Response:"))
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        layout.addWidget(self.output_text)
        
        # Status
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: green;")
        layout.addWidget(self.status_label)
    
    def process_text(self):
        """Process the input text with AI."""
        input_text = self.input_text.toPlainText().strip()
        if not input_text:
            self.output_text.setText("Please enter some text to process.")
            return
        
        self.status_label.setText("Processing...")
        self.status_label.setStyleSheet("color: orange;")
        self.process_btn.setEnabled(False)
        
        # Process with AI (using QTimer to avoid blocking UI)
        QTimer.singleShot(100, lambda: self._do_processing(input_text))
    
    def _do_processing(self, text):
        """Actually process the text."""
        try:
            result = self.addon.process_text_with_ai(
                text, 
                "Please provide a helpful and insightful response to: {text}"
            )
            self.output_text.setText(result)
            self.status_label.setText("Complete!")
            self.status_label.setStyleSheet("color: green;")
        except Exception as e:
            self.output_text.setText(f"Error: {str(e)}")
            self.status_label.setText("Error occurred")
            self.status_label.setStyleSheet("color: red;")
        finally:
            self.process_btn.setEnabled(True)


def register(parent=None):
    """
    Register function called by GGUF Loader when loading the addon.
    
    Args:
        parent: The main GGUF Loader application instance
        
    Returns:
        QWidget: The addon's UI widget, or None for background addons
    """
    try:
        # Create the addon instance
        addon = MyAwesomeAddon(parent)
        addon.start()
        
        # Store addon reference in parent for lifecycle management
        if not hasattr(parent, '_addons'):
            parent._addons = {}
        parent._addons['my_awesome_addon'] = addon
        
        # Create and return the UI widget
        widget = MyAwesomeAddonWidget(addon)
        return widget
        
    except Exception as e:
        logging.error(f"Failed to register My Awesome Addon: {e}")
        return None
```

### Step 4: Test Your Addon

1. **Place your addon** in the `addons/` directory
2. **Launch GGUF Loader**: `ggufloader`
3. **Load a GGUF model** in the main application
4. **Click your addon** in the addon sidebar
5. **Test the functionality**

## 🎨 Advanced Addon Features

### Background Addons

Some addons don't need a UI and run in the background:

```python
def register(parent=None):
    """Register a background addon."""
    try:
        addon = MyBackgroundAddon(parent)
        addon.start()
        
        # Store reference but return None (no UI)
        parent._my_background_addon = addon
        return None
        
    except Exception as e:
        logging.error(f"Failed to register background addon: {e}")
        return None
```

### Global Hotkeys and Text Selection

Learn from the Smart Floating Assistant addon:

```python
from PySide6.QtCore import QTimer
import pyautogui
import pyperclip

class TextSelectionAddon:
    def __init__(self, gguf_app):
        self.gguf_app = gguf_app
        self.selected_text = ""
        
        # Timer for checking text selection
        self.selection_timer = QTimer()
        self.selection_timer.timeout.connect(self.check_selection)
        self.selection_timer.start(500)  # Check every 500ms
    
    def check_selection(self):
        """Check for text selection."""
        try:
            # Save current clipboard
            original_clipboard = pyperclip.paste()
            
            # Copy selection
            pyautogui.hotkey('ctrl', 'c')
            
            # Check if we got new text
            QTimer.singleShot(50, lambda: self.process_selection(original_clipboard))
            
        except:
            pass
    
    def process_selection(self, original_clipboard):
        """Process the selected text."""
        try:
            current_text = pyperclip.paste()
            
            if current_text != original_clipboard and len(current_text.strip()) > 3:
                self.selected_text = current_text.strip()
                self.on_text_selected(self.selected_text)
            
            # Restore clipboard
            pyperclip.copy(original_clipboard)
            
        except:
            pass
    
    def on_text_selected(self, text):
        """Handle text selection event."""
        # Your custom logic here
        print(f"Text selected: {text[:50]}...")
```

### Model Integration

Access and use the loaded GGUF model:

```python
def use_model_for_processing(self, text):
    """Use the GGUF model for text processing."""
    model = self.get_model()
    if not model:
        return "No model loaded"
    
    try:
        # Different processing modes
        response = model(
            f"Analyze this text: {text}",
            max_tokens=300,
            temperature=0.7,
            top_p=0.9,
            repeat_penalty=1.1,
            stop=["</s>", "Human:", "User:"]
        )
        
        return self.extract_response_text(response)
        
    except Exception as e:
        return f"Error: {str(e)}"

def extract_response_text(self, response):
    """Extract text from model response."""
    if isinstance(response, dict) and 'choices' in response:
        return response['choices'][0].get('text', '').strip()
    elif isinstance(response, str):
        return response.strip()
    else:
        return str(response).strip()
```

## 📋 Addon Best Practices

### 1. Error Handling

Always wrap your code in try-catch blocks:

```python
def safe_operation(self):
    try:
        # Your code here
        pass
    except Exception as e:
        self.logger.error(f"Operation failed: {e}")
        return None
```

### 2. Resource Cleanup

Implement proper cleanup:

```python
def stop(self):
    """Clean up addon resources."""
    if hasattr(self, 'timer'):
        self.timer.stop()
    
    if hasattr(self, 'ui_components'):
        for component in self.ui_components:
            component.close()
    
    self.logger.info("Addon stopped and cleaned up")
```

### 3. Configuration

Support user configuration:

```python
import json
import os

class AddonConfig:
    def __init__(self, addon_name):
        self.config_file = f"config/{addon_name}_config.json"
        self.default_config = {
            "enabled": True,
            "hotkey": "Ctrl+Shift+A",
            "auto_process": False
        }
        self.config = self.load_config()
    
    def load_config(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    return {**self.default_config, **json.load(f)}
        except:
            pass
        return self.default_config.copy()
    
    def save_config(self):
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
```

### 4. Logging

Use proper logging:

```python
import logging

class MyAddon:
    def __init__(self, gguf_app):
        self.logger = logging.getLogger(f"addon.{self.__class__.__name__}")
        self.logger.setLevel(logging.INFO)
        
        # Log addon initialization
        self.logger.info("Addon initialized")
    
    def process_data(self, data):
        self.logger.debug(f"Processing data: {len(data)} items")
        try:
            # Process data
            result = self.do_processing(data)
            self.logger.info("Data processed successfully")
            return result
        except Exception as e:
            self.logger.error(f"Processing failed: {e}")
            raise
```

## 🔧 Testing Your Addon

### Unit Testing

Create tests for your addon:

```python
# test_my_addon.py
import unittest
from unittest.mock import Mock, MagicMock
from addons.my_awesome_addon.main import MyAwesomeAddon

class TestMyAwesomeAddon(unittest.TestCase):
    def setUp(self):
        self.mock_gguf_app = Mock()
        self.addon = MyAwesomeAddon(self.mock_gguf_app)
    
    def test_addon_initialization(self):
        self.assertIsNotNone(self.addon)
        self.assertEqual(self.addon.gguf_app, self.mock_gguf_app)
    
    def test_text_processing(self):
        # Mock the model
        mock_model = Mock()
        mock_model.return_value = "Processed text"
        self.mock_gguf_app.model = mock_model
        
        result = self.addon.process_text_with_ai("test text")
        self.assertEqual(result, "Processed text")

if __name__ == '__main__':
    unittest.main()
```

### Integration Testing

Test with the actual GGUF Loader:

```python
# test_integration.py
def test_addon_with_gguf_loader():
    """Test addon integration with GGUF Loader."""
    # This would be run with actual GGUF Loader instance
    pass
```

## 📦 Distributing Your Addon

### 1. Create Documentation

Create a `README.md` for your addon:

```markdown
# My Awesome Addon

A powerful addon for GGUF Loader that provides [functionality].

## Features

- Feature 1
- Feature 2
- Feature 3

## Installation

1. Copy the addon to `addons/my_awesome_addon/`
2. Restart GGUF Loader
3. Click on the addon in the sidebar

## Configuration

[Configuration instructions]

## Usage

[Usage instructions]
```

### 2. Version Your Addon

Use semantic versioning in `__init__.py`:

```python
__version__ = "1.0.0"  # Major.Minor.Patch
```

### 3. Share with Community

- Create a GitHub repository
- Add installation instructions
- Include screenshots and examples
- Submit to the community addon registry

## 🤝 Contributing to Core

Want to contribute to GGUF Loader itself? Check out our [Contributing Guide](contributing.md).

## 📚 Additional Resources

- [Addon API Reference](addon-api.md) - Complete API documentation
- [Smart Floater Example](smart-floater-example.md) - Learn from the built-in addon
- [Troubleshooting](troubleshooting.md) - Common issues and solutions

---

**Happy addon development! 🎉**

Need help? Join our [community discussions](https://github.com/gguf-loader/gguf-loader/discussions) or contact us at support@ggufloader.com.
