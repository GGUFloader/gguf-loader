# Icon Usage - Floating Chat Addon

## Overview

The floating chat button now displays your project's `icon.ico` file instead of a custom-drawn chat icon. This provides better branding and visual consistency with your application.

## How It Works

### Automatic Icon Loading

The button automatically loads `icon.ico` from your project root:

```
project-root/
├── icon.ico          ← Loaded automatically
├── addons/
│   └── floating_chat/
│       └── floating_button.py
```

### Loading Process

1. **Primary Method**: Looks for `icon.ico` in project root (2 levels up from addon)
2. **Fallback Method**: Uses `resource_manager.find_icon()` if available
3. **Final Fallback**: Uses custom-drawn chat bubble icon if icon.ico not found

### Icon Display

- Icon is scaled to **70% of button size** (42x42 pixels for 60px button)
- Uses **smooth transformation** for high-quality scaling
- Rendered with **95% opacity** for better blending with gradient background
- Maintains **aspect ratio** during scaling

## Customization

### Change Button Size

Edit `floating_button.py`:
```python
self._button_size = 60  # Change to desired size (e.g., 80)
```

Icon will automatically scale proportionally.

### Change Icon Size Ratio

Edit the `_draw_icon()` method:
```python
icon_size = int(button_rect.width() * 0.7)  # Change 0.7 to desired ratio
```

- `0.5` = 50% of button (smaller icon, more padding)
- `0.7` = 70% of button (default, balanced)
- `0.9` = 90% of button (larger icon, less padding)

### Use Different Icon File

Edit the `_load_icon()` method to point to a different file:
```python
icon_path = project_root / "my_custom_icon.png"  # Change filename
```

Supported formats: `.ico`, `.png`, `.jpg`, `.svg`, `.bmp`

## Icon Requirements

### Recommended Specifications

- **Format**: ICO, PNG, or SVG
- **Size**: 16x16 to 256x256 pixels
- **Transparency**: Supported (recommended for better appearance)
- **Color Depth**: 32-bit with alpha channel

### Current Icon

Your current `icon.ico`:
- Size: 69,916 bytes
- Dimensions: 16x16 pixels (will be scaled up smoothly)
- Format: ICO

### Optimization Tips

For best results:
1. Use a **square icon** (1:1 aspect ratio)
2. Use **transparent background** for better blending
3. Use **high resolution** (128x128 or higher) for sharp scaling
4. Use **simple, clear design** that works at small sizes

## Visual Examples

### With Icon (Current)
```
┌─────────┐
│  ╭───╮  │
│  │🖼️ │  │  ← Your icon.ico displayed
│  ╰───╯  │
└─────────┘
```

### Without Icon (Fallback)
```
┌─────────┐
│  ╭───╮  │
│  │💬 │  │  ← Custom chat bubble icon
│  ╰───╯  │
└─────────┘
```

## Testing

### Verify Icon Loading

Run the test script:
```bash
python test_icon_loading.py
```

Expected output:
```
✓ icon.ico found at: E:\gguf-loader\icon.ico
  Size: 69916 bytes
✓ Icon loaded successfully
  Dimensions: 16x16
✓ FloatingChatButton loaded icon successfully
  Icon dimensions: 16x16
```

### Visual Test

1. Launch GGUF Loader: `python launch.py`
2. Look for the floating button
3. Verify your icon is displayed
4. Hover over button to see animation
5. Drag button to test functionality

## Troubleshooting

### Icon Not Displaying

**Problem**: Button shows chat bubble instead of icon

**Solutions**:
1. Verify `icon.ico` exists in project root
2. Check file permissions (must be readable)
3. Try different icon format (PNG instead of ICO)
4. Check console for error messages

### Icon Looks Blurry

**Problem**: Icon appears pixelated or blurry

**Solutions**:
1. Use higher resolution icon (128x128 or larger)
2. Use vector format (SVG) for perfect scaling
3. Ensure icon has transparent background
4. Check icon quality in image editor

### Icon Too Large/Small

**Problem**: Icon doesn't fit well in button

**Solutions**:
1. Adjust icon size ratio in `_draw_icon()` method
2. Change button size in `__init__()` method
3. Use icon with more/less padding in the image itself

### Icon Not Loading on Linux

**Problem**: Icon loads on Windows but not Linux

**Solutions**:
1. Check file path case sensitivity
2. Verify file permissions: `chmod 644 icon.ico`
3. Try absolute path instead of relative
4. Check if Qt6 supports the icon format on your system

## Advanced Usage

### Dynamic Icon Changing

You can change the icon at runtime:

```python
# Get button reference
button = addon._floating_button

# Load new icon
new_pixmap = QPixmap("path/to/new_icon.png")
button._icon_pixmap = new_pixmap

# Trigger repaint
button.update()
```

### Icon Based on State

Change icon based on chat state:

```python
def update_icon_for_state(button, is_chatting):
    if is_chatting:
        button._icon_pixmap = QPixmap("icon_active.png")
    else:
        button._icon_pixmap = QPixmap("icon_idle.png")
    button.update()
```

### Animated Icon

For animated icons, use QMovie:

```python
from PySide6.QtGui import QMovie

# In __init__
self._icon_movie = QMovie("animated_icon.gif")
self._icon_movie.frameChanged.connect(self.update)
self._icon_movie.start()

# In paintEvent
current_pixmap = self._icon_movie.currentPixmap()
```

## Technical Details

### Code Location

Icon loading: `addons/floating_chat/floating_button.py`
- Method: `_load_icon()` (lines ~30-65)
- Rendering: `_draw_icon()` (lines ~120-140)

### Dependencies

- `PySide6.QtGui.QPixmap` - Image loading and rendering
- `PySide6.QtCore.Qt` - Scaling and transformation modes
- `pathlib.Path` - Cross-platform path handling

### Performance

- Icon loaded once at initialization
- Cached in memory (`self._icon_pixmap`)
- Scaled on each paint event (negligible overhead)
- No disk I/O during runtime

---

**Enjoy your branded floating button! 🎨**
