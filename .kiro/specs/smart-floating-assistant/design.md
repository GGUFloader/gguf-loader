# Design Document

## Overview

The Smart Floating Assistant is a PySide6-based addon that provides global text selection detection and AI-powered text processing capabilities. The system operates as an independent floating interface that integrates with the GGUF Loader application's model backend while maintaining complete UI separation. The architecture emphasizes modularity, privacy, and seamless user experience across all applications.

## Architecture

The addon follows a modular architecture with clear separation of concerns:

```
addons/smart_floater/
├── main.py              # Entry point and lifecycle management
├── floater_ui.py        # Floating UI components (button + popup)
├── comment_engine.py    # AI text processing logic
├── injector.py          # Text insertion and clipboard operations
└── __init__.py          # Package initialization
```

### System Flow
1. **Detection Phase**: Global text selection monitoring
2. **UI Phase**: Floating button display and popup interaction
3. **Processing Phase**: AI-powered text analysis using GGUF backend
4. **Output Phase**: Result display and optional text insertion

## Components and Interfaces

### Main Controller (`main.py`)
**Purpose**: Addon lifecycle management and integration with GGUF Loader

**Key Responsibilities**:
- Initialize addon when GGUF Loader starts
- Coordinate between UI and processing components
- Handle addon shutdown and cleanup

**Interface**:
```python
class SmartFloaterAddon:
    def __init__(self, gguf_app_instance)
    def start()
    def stop()
    def get_model_backend()
```

### Floating UI System (`floater_ui.py`)
**Purpose**: Manage floating button and popup window interface

**Key Components**:

1. **Text Selection Monitor**
   - Global text selection detection using system hooks
   - Cross-platform clipboard monitoring
   - Cursor position tracking

2. **Floating Button**
   - Transparent, always-on-top widget
   - Positioned near cursor (within 50px)
   - Auto-hide after 5 seconds of no selection
   - Smooth fade-in/fade-out animations

3. **Popup Window**
   - Modal dialog with selected text display
   - Action buttons (Summarize, Comment)
   - Results area with scrollable text
   - Loading indicators during processing

**Interface**:
```python
class FloatingButton(QWidget):
    def show_at_cursor(position)
    def hide_with_delay(delay_seconds=5)

class TextProcessorPopup(QDialog):
    def set_selected_text(text)
    def show_loading()
    def display_result(result, result_type)
    def add_paste_button()
```

### AI Processing Engine (`comment_engine.py`)
**Purpose**: Handle AI text processing using GGUF backend

**Key Responsibilities**:
- Interface with GGUF Loader's model backend
- Execute summarization and comment generation
- Handle processing errors and timeouts
- Format prompts for optimal results

**Processing Templates**:
- Summarization: `"Summarize this clearly: {text}"`
- Comment Generation: `"Write a friendly and insightful comment about: {text}"`

**Interface**:
```python
class CommentEngine:
    def __init__(self, model_backend)
    def summarize_text(text) -> str
    def generate_comment(text) -> str
    def is_model_available() -> bool
```

### Text Injection System (`injector.py`)
**Purpose**: Handle text insertion and clipboard operations

**Key Responsibilities**:
- Insert generated text at cursor position
- Fallback to clipboard copy when insertion fails
- Cross-platform text injection using pyautogui
- User feedback for successful/failed operations

**Interface**:
```python
class TextInjector:
    def paste_at_cursor(text) -> bool
    def copy_to_clipboard(text)
    def show_feedback(success, message)
```

## Data Models

### Text Selection Data
```python
@dataclass
class TextSelection:
    content: str
    cursor_position: Tuple[int, int]
    timestamp: datetime
    source_app: str
```

### Processing Result
```python
@dataclass
class ProcessingResult:
    original_text: str
    processed_text: str
    processing_type: str  # 'summary' or 'comment'
    success: bool
    error_message: Optional[str]
    processing_time: float
```

### UI State
```python
@dataclass
class UIState:
    is_button_visible: bool
    is_popup_open: bool
    current_selection: Optional[TextSelection]
    last_result: Optional[ProcessingResult]
```

## Error Handling

### Model Backend Errors
- **No Model Loaded**: Display user-friendly message suggesting to load a model in GGUF Loader
- **Model Processing Failure**: Show error in popup with retry option
- **Backend Unavailable**: Graceful degradation with informative error messages

### Text Selection Errors
- **No Text Selected**: Hide floating button, no error display
- **Selection Too Large**: Truncate text with warning (limit: 10,000 characters)
- **Invalid Characters**: Clean text before processing, log warnings

### Text Injection Errors
- **No Active Input Field**: Fallback to clipboard copy with notification
- **Injection Failure**: Display error message and offer clipboard copy
- **Permission Denied**: Show system permission guidance

### UI Errors
- **Window Focus Issues**: Implement robust window management
- **Cross-Platform Compatibility**: Handle OS-specific UI behaviors
- **Memory Leaks**: Proper widget cleanup and event handler removal

## Testing Strategy

### Unit Testing
- **Component Isolation**: Test each module independently
- **Mock Dependencies**: Mock GGUF backend for consistent testing
- **Edge Cases**: Test with various text lengths, special characters, and error conditions

### Integration Testing
- **End-to-End Workflows**: Test complete user journeys from selection to insertion
- **Backend Integration**: Test with actual GGUF models when available
- **Cross-Application Testing**: Verify text selection works across different applications

### UI Testing
- **Widget Behavior**: Test floating button positioning and popup interactions
- **Responsive Design**: Test with different screen resolutions and DPI settings
- **Accessibility**: Ensure keyboard navigation and screen reader compatibility

### Performance Testing
- **Memory Usage**: Monitor for memory leaks during extended use
- **Processing Speed**: Measure AI processing times and optimize where needed
- **UI Responsiveness**: Ensure UI remains responsive during processing

### Platform Testing
- **Windows Compatibility**: Primary target platform testing
- **Cross-Platform**: Verify basic functionality on macOS and Linux if applicable
- **System Integration**: Test global text selection across various applications

## Security and Privacy

### Local Processing
- All text processing occurs locally using GGUF models
- No network requests for AI processing
- Selected text never transmitted externally

### Data Handling
- Temporary text storage in memory only
- No persistent storage of user text
- Automatic cleanup of processed text

### System Permissions
- Minimal required permissions for global text selection
- Transparent permission requests with clear explanations
- Graceful degradation when permissions are denied