# Floating Chat Addon

A Facebook Messenger-style floating chat button for GGUF Loader that works across all operating systems (Windows, Linux, macOS).

## Features

✨ **Cross-Platform Compatibility**
- Works seamlessly on Windows, Linux, and macOS
- Native Qt6 implementation for consistent behavior

🎯 **Floating Button**
- Always stays on top of all windows
- Draggable to any position on screen
- Remembers position between sessions
- Smooth animations and hover effects
- Uses your project's icon.ico as the button icon
- Modern gradient background design

💬 **Chat Window**
- Clean, modern chat interface
- Connected to GGUF Loader AI model
- Message history display
- Real-time AI responses
- Keyboard shortcuts (Ctrl+Enter to send)

## Installation

The addon is already included in GGUF Loader. Simply:

1. Launch GGUF Loader
2. The addon will automatically load
3. Look for the floating blue chat button on your screen

## Usage

### Opening Chat
- Click the floating button to open the chat window
- The window will appear next to the button

### Sending Messages
- Type your message in the input field
- Click "Send" or press Ctrl+Enter
- Wait for AI response

### Moving the Button
- Click and drag the floating button anywhere on screen
- Position is automatically saved

### Closing Chat
- Click the X button on the chat window
- Or click the floating button again to toggle

## Requirements

- PySide6 (Qt6)
- GGUF Loader with loaded AI model
- Python 3.8+

## Technical Details

### Components

1. **FloatingChatButton** (`floating_button.py`)
   - Frameless, always-on-top window
   - Custom paint event for gradient design
   - Drag and drop functionality
   - Hover and click animations

2. **FloatingChatWindow** (`chat_window.py`)
   - Chat interface with message history
   - Connected to GGUF Loader model
   - HTML-formatted messages
   - Auto-scroll to latest message

3. **FloatingChatAddon** (`main.py`)
   - Main addon controller
   - Manages button and window lifecycle
   - Handles model integration
   - Persists settings

### Cross-Platform Compatibility

The addon uses Qt6's cross-platform features:

- **Window Flags**: `WindowStaysOnTopHint`, `FramelessWindowHint`, `Tool`
- **Linux Support**: `X11BypassWindowManagerHint` for proper floating behavior
- **macOS Support**: Native Qt6 window management
- **Windows Support**: Full transparency and always-on-top

### Settings Persistence

Button position is saved using QSettings:
- Windows: Registry
- Linux: ~/.config/GGUFLoader/FloatingChat.conf
- macOS: ~/Library/Preferences/com.GGUFLoader.FloatingChat.plist

## Customization

### Button Size
Edit `floating_button.py`:
```python
self._button_size = 60  # Change to desired size
```

### Button Colors
Edit the gradient colors in `paintEvent()` method:
```python
gradient.setColorAt(0.0, QColor(0, 120, 215, 220))  # Center color
gradient.setColorAt(1.0, QColor(0, 80, 170, 180))   # Edge color
```

### Chat Window Size
Edit `chat_window.py`:
```python
self.resize(400, 600)  # Width, Height
```

## Troubleshooting

### Button not visible
- Check if it's off-screen (restart addon to reset position)
- Ensure GGUF Loader is running
- Check addon is loaded in addon sidebar

### Chat not responding
- Ensure AI model is loaded in main GGUF Loader window
- Check model status indicator in chat window
- Look for errors in GGUF Loader logs

### Button not draggable on Linux
- Ensure X11 is being used (not Wayland)
- Or use Wayland compatibility mode in Qt6

## License

Same as GGUF Loader main project.
