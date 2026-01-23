# Example Usage - Floating Chat Addon

## Basic Usage Example

### Starting the Addon

The addon automatically starts when GGUF Loader launches. You'll see:

1. **Floating Button** appears at position (100, 100)
2. **Blue circular button** with chat icon
3. **Addon status** in the sidebar shows "🟢 Active"

### Example Conversation

```
User: Hello! Can you help me with Python?
AI: Of course! I'd be happy to help you with Python. What would you like to know?

User: How do I read a file?
AI: Here's how to read a file in Python:

with open('filename.txt', 'r') as file:
    content = file.read()
    print(content)

This opens the file, reads its contents, and prints them.
```

## Use Cases

### 1. Quick Code Questions

**Scenario**: You're coding and need quick help

```
1. Click floating button (no need to switch windows)
2. Type: "How do I sort a list in Python?"
3. Get instant answer
4. Continue coding
```

### 2. Multi-Monitor Setup

**Scenario**: You have multiple monitors

```
1. Drag button to secondary monitor
2. Position in corner for easy access
3. Keep main monitor for code
4. Chat on secondary monitor
```

### 3. Learning While Working

**Scenario**: Following a tutorial

```
1. Tutorial on main screen
2. Floating chat on side
3. Ask questions as you learn
4. Get explanations without leaving tutorial
```

### 4. Code Review Assistant

**Scenario**: Reviewing code

```
User: Can you explain what this code does?
[paste code snippet]

AI: This code implements a binary search algorithm...
```

## Integration Examples

### With GGUF Loader Main Window

```python
# The addon automatically connects to:
- self.gguf_app.model          # Loaded AI model
- self.gguf_app.chat_generator # Chat generation system
- self.gguf_app.model_loaded   # Signal when model loads
```

### Programmatic Control

```python
# Access addon from main app
addon = parent._floating_chat_addon

# Check if running
if addon.is_running():
    print("Addon is active")

# Get button position
pos = addon.get_button_position()
print(f"Button at: {pos.x()}, {pos.y()}")

# Set button position
from PySide6.QtCore import QPoint
addon.set_button_position(QPoint(200, 200))

# Check chat window visibility
if addon.is_chat_window_visible():
    print("Chat window is open")
```

## Workflow Examples

### Morning Routine

```
1. Launch GGUF Loader
2. Load your preferred model
3. Floating button appears automatically
4. Position it in your preferred spot
5. Start your work
6. Click when you need AI assistance
```

### During Development

```
1. Writing code in your IDE
2. Question arises
3. Click floating button (stays on top)
4. Ask question
5. Get answer
6. Close chat or leave it open
7. Continue coding
```

### Research Session

```
1. Reading documentation
2. Floating chat open on side
3. Ask clarifying questions
4. Get explanations
5. Take notes
6. Export conversation (future feature)
```

## Tips & Tricks

### Keyboard Efficiency

```
1. Click floating button
2. Type message
3. Press Ctrl+Enter (quick send)
4. Read response
5. Press Esc to close (when focused)
```

### Multi-Tasking

```
1. Keep chat window open
2. Floating button minimized to corner
3. Switch between apps
4. Chat stays on top
5. Always accessible
```

### Position Presets

```
# Top-right corner
Button position: (screen_width - 70, 10)

# Bottom-right corner
Button position: (screen_width - 70, screen_height - 70)

# Center-right edge
Button position: (screen_width - 70, screen_height / 2)
```

## Real-World Scenarios

### Scenario 1: Bug Fixing

```
Developer: "I'm getting a TypeError in Python. How do I debug it?"
AI: "Here are steps to debug a TypeError:
1. Read the error message carefully
2. Check the line number
3. Verify variable types
4. Use print() or debugger
Would you like me to explain any of these steps?"
```

### Scenario 2: Learning New Library

```
Developer: "How do I use pandas to read a CSV file?"
AI: "Here's how to read a CSV with pandas:

import pandas as pd
df = pd.read_csv('file.csv')
print(df.head())

This imports pandas, reads the CSV, and shows first 5 rows."
```

### Scenario 3: Code Review

```
Developer: "Is this code efficient?"
[pastes code]
AI: "Let me analyze this code for efficiency:
1. Time complexity: O(n²) - could be improved
2. Space complexity: O(n) - acceptable
3. Suggestion: Use a hash map to reduce to O(n)
Would you like me to show the optimized version?"
```

## Advanced Usage

### Custom Positioning Script

```python
# Save this as position_button.py
from PySide6.QtCore import QPoint

def position_button_top_right(addon, screen):
    """Position button in top-right corner"""
    screen_rect = screen.geometry()
    x = screen_rect.width() - 70
    y = 10
    addon.set_button_position(QPoint(x, y))

def position_button_center_left(addon, screen):
    """Position button in center-left"""
    screen_rect = screen.geometry()
    x = 10
    y = screen_rect.height() // 2
    addon.set_button_position(QPoint(x, y))
```

### Integration with Other Addons

```python
# Example: Trigger floating chat from another addon
def my_addon_function(parent):
    # Get floating chat addon
    if hasattr(parent, '_floating_chat_addon'):
        chat_addon = parent._floating_chat_addon
        
        # Show chat window
        chat_addon._show_chat_window()
        
        # Send a message programmatically
        chat_addon.chat_message_sent.emit("Hello from another addon!")
```

## Troubleshooting Examples

### Problem: Button disappeared

```
Solution:
1. Close GGUF Loader
2. Delete settings file:
   - Windows: Registry Editor → HKEY_CURRENT_USER\Software\GGUFLoader
   - Linux: rm ~/.config/GGUFLoader/FloatingChat.conf
   - macOS: rm ~/Library/Preferences/com.GGUFLoader.FloatingChat.plist
3. Restart GGUF Loader
4. Button appears at default position (100, 100)
```

### Problem: Chat not responding

```
Solution:
1. Check main window: Is model loaded?
2. Look at status indicator: Should be green
3. Check logs: Look for error messages
4. Try reloading model
5. Restart addon from sidebar
```

### Problem: Button not draggable on Linux

```
Solution:
1. Check if using Wayland:
   echo $XDG_SESSION_TYPE

2. If Wayland, use X11 compatibility:
   QT_QPA_PLATFORM=xcb python launch.py

3. Or install X11 support:
   sudo apt install xwayland
```

## Performance Tips

### For Low-End Systems

```
1. Close chat window when not in use
2. Use smaller models for faster responses
3. Reduce animation effects (future feature)
4. Limit conversation history length
```

### For High-End Systems

```
1. Keep chat window always open
2. Use larger, more capable models
3. Enable all visual effects
4. Multiple chat sessions (future feature)
```

---

**Happy chatting! 🎉**
