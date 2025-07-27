# Smart Floater Addon Example

Learn how to create addons by studying the built-in Smart Floating Assistant addon. This is a complete, real-world example that demonstrates all the key concepts of addon development.

## 📋 Overview

The Smart Floating Assistant is GGUF Loader's flagship addon that provides:

- **Global text selection detection** across all applications
- **Floating button interface** that appears near selected text
- **AI-powered text processing** (summarize and comment)
- **Seamless clipboard integration**
- **Privacy-first local processing**

## 🏗️ Architecture

### File Structure

```
addons/smart_floater/
├── __init__.py              # Addon entry point
├── simple_main.py           # Main addon logic (simplified version)
├── main.py                  # Full-featured version
├── floater_ui.py           # UI components
├── comment_engine.py       # Text processing engine
├── injector.py             # Text injection utilities
├── error_handler.py        # Error handling
├── privacy_security.py    # Privacy and security features
└── performance_optimizer.py # Performance optimization
```

### Key Components

1. **SimpleFloatingAssistant**: Main addon class
2. **SmartFloaterStatusWidget**: Control panel UI
3. **Text Selection Monitor**: Global text detection
4. **AI Processing Engine**: Text summarization and commenting
5. **Clipboard Manager**: Safe clipboard operations

## 🔍 Code Analysis

### Entry Point (`__init__.py`)

```python
"""
Simple Smart Floating Assistant

Shows a button when you select text, processes it with AI. That's it.
"""

# Use the simple version instead of the complex one
from .simple_main import register

__all__ = ["register"]
```

**Key Lessons:**
- Keep the entry point simple
- Export only the `register` function
- Use clear, descriptive docstrings

### Main Logic (`simple_main.py`)

Let's break down the main addon class:

```python
class SimpleFloatingAssistant:
    """Simple floating assistant that shows button on text selection."""
    
    def __init__(self, gguf_app_instance: Any):
        """Initialize the addon with GGUF Loader reference."""
        self.gguf_app = gguf_app_instance
        self._is_running = False
        self._floating_button = None
        self._popup_window = None
        self._selected_text = ""
        self.model = None  # Store model reference directly
        
        # Initialize clipboard tracking
        try:
            self.last_clipboard = pyperclip.paste()
        except:
            self.last_clipboard = ""
        
        # Button persistence tracking
        self.button_show_time = 0
        self.button_should_stay = False
        
        # Connect to model loading signals
        self.connect_to_model_signals()
        
        # Timer to check for text selection
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_selection)
        self.timer.start(300)  # Check every 300ms
```

**Key Lessons:**
- Store reference to main app (`gguf_app`)
- Initialize all state variables
- Connect to model loading signals
- Use QTimer for periodic tasks
- Handle initialization errors gracefully

### Model Integration

```python
def connect_to_model_signals(self):
    """Connect to model loading signals from the main app."""
    try:
        # Connect to the main app's model_loaded signal
        if hasattr(self.gguf_app, 'model_loaded'):
            self.gguf_app.model_loaded.connect(self.on_model_loaded)
            print("✅ Connected to model_loaded signal")
        
        # Also try to connect to ai_chat model_loaded signal
        if hasattr(self.gguf_app, 'ai_chat') and hasattr(self.gguf_app.ai_chat, 'model_loaded'):
            self.gguf_app.ai_chat.model_loaded.connect(self.on_model_loaded)
            print("✅ Connected to ai_chat model_loaded signal")
            
    except Exception as e:
        print(f"❌ Error connecting to model signals: {e}")

def on_model_loaded(self, model):
    """Handle model loaded event."""
    self.model = model
    print(f"✅ Addon received model: {type(model)}")
    print(f"   Model methods: {[m for m in dir(model) if not m.startswith('_')][:10]}")

def get_model(self):
    """Get the loaded model."""
    try:
        # First try our stored model reference
        if self.model:
            print("✅ Using stored model reference")
            return self.model
        
        # Try multiple fallback methods
        if hasattr(self.gguf_app, 'model'):
            if self.gguf_app.model:
                self.model = self.gguf_app.model
                return self.gguf_app.model
        
        # ... more fallback methods
        
        return None
    except Exception as e:
        print(f"❌ Error getting model: {e}")
        return None
```

**Key Lessons:**
- Connect to model loading signals for real-time updates
- Implement multiple fallback methods for model access
- Store model reference locally for performance
- Use defensive programming with try-catch blocks
- Provide helpful debug output

### Text Selection Detection

```python
def check_selection(self):
    """Check if text is currently selected (without copying)."""
    try:
        # Save current clipboard content
        original_clipboard = pyperclip.paste()
        
        # Temporarily copy selection to check if text is selected
        pyautogui.hotkey('ctrl', 'c')
        
        # Small delay to let clipboard update
        QTimer.singleShot(50, lambda: self._process_selection_check(original_clipboard))
        
    except:
        pass

def _process_selection_check(self, original_clipboard):
    """Process the selection check and restore clipboard."""
    try:
        # Get what was copied
        current_selection = pyperclip.paste()
        
        # Check if we got new selected text
        if (current_selection != original_clipboard and 
            current_selection and 
            len(current_selection.strip()) > 3 and
            len(current_selection) < 5000):
            
            # We have selected text!
            if current_selection.strip() != self.selected_text:
                self.selected_text = current_selection.strip()
                self.show_button()
                self.button_show_time = 0  # Reset timer
                self.button_should_stay = True
        else:
            # No text selected - but don't hide immediately
            if self.button_should_stay:
                self.button_show_time += 1
                
                # Hide after 10 checks (about 3 seconds)
                if self.button_show_time > 10:
                    self.hide_button()
                    self.button_should_stay = False
                    self.button_show_time = 0
        
        # Always restore original clipboard immediately
        pyperclip.copy(original_clipboard)
        
    except:
        # Always try to restore clipboard even if there's an error
        try:
            pyperclip.copy(original_clipboard)
        except:
            pass
```

**Key Lessons:**
- Use non-intrusive text selection detection
- Always restore the user's clipboard
- Implement smart button persistence (don't hide immediately)
- Handle edge cases (empty text, very long text)
- Use defensive programming for clipboard operations

### Floating UI

```python
def show_button(self):
    """Show floating button near cursor."""
    if self.button:
        self.button.close()
    
    self.button = QPushButton("✨")
    self.button.setFixedSize(40, 40)
    self.button.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
    self.button.setStyleSheet("""
        QPushButton {
            background-color: #0078d4;
            border: none;
            border-radius: 20px;
            color: white;
            font-size: 16px;
        }
        QPushButton:hover {
            background-color: #106ebe;
        }
    """)
    
    # Position near cursor
    pos = QCursor.pos()
    self.button.move(pos.x() + 10, pos.y() - 50)
    self.button.clicked.connect(self.show_popup)
    self.button.show()
    
    # Reset persistence tracking
    self.button_show_time = 0
    self.button_should_stay = True
```

**Key Lessons:**
- Use appropriate window flags for floating widgets
- Position relative to cursor for better UX
- Apply attractive styling with CSS
- Connect button clicks to actions
- Clean up previous instances before creating new ones

### AI Text Processing

```python
def process_text(self, action):
    """Process text with AI using GGUF Loader's model."""
    try:
        model = self.get_model()
        if not model:
            self.result_area.setText("❌ Error: No AI model loaded in GGUF Loader\n\nPlease load a GGUF model first!")
            return
        
        self.result_area.setText("🤖 Processing with AI...")
        
        # Create appropriate prompt based on action
        if action == "summarize":
            prompt = f"Please provide a clear and concise summary of the following text:\n\n{self.selected_text}\n\nSummary:"
        else:  # comment
            prompt = f"Please write a thoughtful and insightful comment about the following text:\n\n{self.selected_text}\n\nComment:"
        
        # Process with GGUF model using the same interface as AIChat
        try:
            # Use the model the same way as ChatGenerator does
            response = model(
                prompt,
                max_tokens=300,
                stream=False,  # Don't stream for simplicity
                temperature=0.7,
                top_p=0.9,
                repeat_penalty=1.1,
                top_k=40,
                stop=["</s>", "Human:", "User:", "\n\n\n"]
            )
            
            # Extract text from response
            if isinstance(response, dict) and 'choices' in response:
                result_text = response['choices'][0].get('text', '').strip()
            elif isinstance(response, str):
                result_text = response.strip()
            else:
                result_text = str(response).strip()
            
            # Clean up the result
            if result_text:
                # Remove any prompt echoing
                if "Summary:" in result_text:
                    result_text = result_text.split("Summary:")[-1].strip()
                elif "Comment:" in result_text:
                    result_text = result_text.split("Comment:")[-1].strip()
                
                self.result_area.setText(result_text)
                self.copy_btn.setEnabled(True)
            else:
                self.result_area.setText("❌ No response generated. Try again.")
            
        except Exception as e:
            self.result_area.setText(f"❌ Error processing with AI model:\n{str(e)}\n\nMake sure a compatible GGUF model is loaded.")
    
    except Exception as e:
        self.result_area.setText(f"❌ Unexpected error: {str(e)}")
```

**Key Lessons:**
- Check model availability before processing
- Create context-appropriate prompts
- Use consistent model parameters
- Handle different response formats
- Clean up AI responses (remove prompt echoing)
- Provide clear error messages to users

### Status Widget for Addon Panel

```python
class SmartFloaterStatusWidget:
    def __init__(self, addon_instance):
        from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QTextEdit
        
        self.addon = addon_instance
        self.widget = QWidget()
        self.widget.setWindowTitle("Smart Floating Assistant")
        
        layout = QVBoxLayout(self.widget)
        
        # Status info
        layout.addWidget(QLabel("🤖 Smart Floating Assistant"))
        layout.addWidget(QLabel("Status: Running in background"))
        layout.addWidget(QLabel(""))
        layout.addWidget(QLabel("How to use:"))
        layout.addWidget(QLabel("1. Select text anywhere on your screen"))
        layout.addWidget(QLabel("2. Click the ✨ button that appears"))
        layout.addWidget(QLabel("3. Choose Summarize or Comment"))
        layout.addWidget(QLabel(""))
        
        # Test button
        test_btn = QPushButton("🧪 Test Model Connection")
        test_btn.clicked.connect(self.test_model)
        layout.addWidget(test_btn)
        
        # Result area
        self.result_area = QTextEdit()
        self.result_area.setMaximumHeight(100)
        self.result_area.setReadOnly(True)
        layout.addWidget(self.result_area)
        
        # Stop/Start buttons
        button_layout = QHBoxLayout()
        
        stop_btn = QPushButton("⏹️ Stop")
        stop_btn.clicked.connect(self.stop_addon)
        button_layout.addWidget(stop_btn)
        
        start_btn = QPushButton("▶️ Start")
        start_btn.clicked.connect(self.start_addon)
        button_layout.addWidget(start_btn)
        
        layout.addLayout(button_layout)
```

**Key Lessons:**
- Create informative status widgets for addon management
- Provide clear usage instructions
- Include testing and control functionality
- Use emoji and clear labels for better UX
- Separate UI logic from core addon logic

### Registration Function

```python
def register(parent=None):
    """Register the simple floating assistant."""
    try:
        print(f"🔧 Register called with parent: {type(parent)}")
        
        # Stop existing addon if running
        if hasattr(parent, '_simple_floater'):
            parent._simple_floater.stop()
        
        # Create and start simple addon
        addon = SimpleFloatingAssistant(parent)
        parent._simple_floater = addon
        
        print("✅ Simple Floating Assistant started!")
        
        # Return a status widget for the addon panel
        status_widget = SmartFloaterStatusWidget(addon)
        return status_widget.widget
        
    except Exception as e:
        print(f"❌ Failed to start simple addon: {e}")
        return None
```

**Key Lessons:**
- Always handle cleanup of existing instances
- Store addon reference in parent for lifecycle management
- Return appropriate UI widget or None for background addons
- Provide clear success/failure feedback
- Use defensive programming with try-catch

## 🎯 Best Practices Demonstrated

### 1. **Defensive Programming**
- Extensive use of try-catch blocks
- Graceful handling of missing dependencies
- Fallback methods for critical operations

### 2. **User Experience**
- Non-intrusive text selection detection
- Smart button persistence (doesn't disappear immediately)
- Clear status messages and error handling
- Attractive, modern UI design

### 3. **Performance Optimization**
- Efficient timer-based monitoring
- Minimal clipboard interference
- Lazy loading of UI components
- Resource cleanup on shutdown

### 4. **Integration Patterns**
- Signal-based communication with main app
- Multiple fallback methods for model access
- Proper lifecycle management
- Clean separation of concerns

### 5. **Error Handling**
- Comprehensive error messages
- Graceful degradation when model unavailable
- User-friendly error reporting
- Debug information for developers

## 🔧 Customization Examples

### Adding New Processing Actions

```python
def process_text(self, action):
    """Extended processing with more actions."""
    prompts = {
        "summarize": "Please provide a clear and concise summary of: {text}",
        "comment": "Please write a thoughtful comment about: {text}",
        "explain": "Please explain this text in simple terms: {text}",
        "translate": "Please translate this text to English: {text}",
        "improve": "Please improve the writing of this text: {text}"
    }
    
    prompt_template = prompts.get(action, prompts["summarize"])
    prompt = prompt_template.format(text=self.selected_text)
    
    # ... rest of processing logic
```

### Custom Hotkeys

```python
def setup_hotkeys(self):
    """Setup custom hotkeys for the addon."""
    try:
        import keyboard
        
        # Register global hotkey for instant processing
        keyboard.add_hotkey('ctrl+shift+s', self.quick_summarize)
        keyboard.add_hotkey('ctrl+shift+c', self.quick_comment)
        
    except ImportError:
        print("Keyboard library not available for hotkeys")

def quick_summarize(self):
    """Quick summarize selected text without UI."""
    # Get current selection and process immediately
    pass
```

### Configuration Support

```python
def load_config(self):
    """Load addon configuration."""
    config_file = Path.home() / ".ggufloader" / "smart_floater_config.json"
    
    default_config = {
        "check_interval": 300,
        "button_timeout": 3000,
        "max_text_length": 5000,
        "auto_copy_results": True
    }
    
    try:
        if config_file.exists():
            with open(config_file) as f:
                user_config = json.load(f)
                return {**default_config, **user_config}
    except:
        pass
    
    return default_config
```

## 📊 Performance Considerations

### Memory Management
- Clean up UI components properly
- Avoid memory leaks in timer callbacks
- Use weak references where appropriate

### CPU Usage
- Optimize timer intervals
- Avoid blocking operations in main thread
- Use QTimer.singleShot for delayed operations

### System Integration
- Minimize clipboard interference
- Respect user's workflow
- Handle system sleep/wake events

## 🧪 Testing the Smart Floater

### Manual Testing Checklist

1. **Basic Functionality**
   - [ ] Addon loads without errors
   - [ ] Status widget appears in sidebar
   - [ ] Model connection test works

2. **Text Selection**
   - [ ] Button appears when selecting text
   - [ ] Button stays visible for appropriate time
   - [ ] Works across different applications

3. **AI Processing**
   - [ ] Summarize function works correctly
   - [ ] Comment function generates appropriate responses
   - [ ] Error handling when no model loaded

4. **UI/UX**
   - [ ] Floating button positioned correctly
   - [ ] Popup window displays properly
   - [ ] Copy functionality works

### Automated Testing

```python
import unittest
from unittest.mock import Mock, patch

class TestSmartFloater(unittest.TestCase):
    def setUp(self):
        self.mock_gguf_app = Mock()
        self.addon = SimpleFloatingAssistant(self.mock_gguf_app)
    
    def test_model_connection(self):
        """Test model connection and retrieval."""
        mock_model = Mock()
        self.mock_gguf_app.model = mock_model
        
        result = self.addon.get_model()
        self.assertEqual(result, mock_model)
    
    @patch('pyperclip.paste')
    @patch('pyperclip.copy')
    def test_clipboard_operations(self, mock_copy, mock_paste):
        """Test clipboard operations don't interfere."""
        mock_paste.return_value = "original text"
        
        self.addon.check_selection()
        
        # Verify clipboard was restored
        mock_copy.assert_called_with("original text")
```

## 🚀 Next Steps

After studying the Smart Floater example:

1. **Create your own addon** using the patterns shown
2. **Experiment with modifications** to understand the code better
3. **Read the full source code** in `addons/smart_floater/`
4. **Join the community** to share your addon ideas

## 📚 Related Documentation

- [Addon Development Guide](addon-development.md) - Step-by-step development guide
- [Addon API Reference](addon-api.md) - Complete API documentation
- [User Guide](user-guide.md) - How to use the Smart Floater as an end user

---

**The Smart Floater is a great example of what's possible with GGUF Loader addons. Use it as inspiration for your own creations! 🎉**

Need help understanding any part of the code? Join our [community discussions](https://github.com/gguf-loader/gguf-loader/discussions) or contact support@ggufloader.com.