# Bug Fixes - Floating Chat Addon

## Version 1.0.2 - Icon Enhancement

### New Feature
- **Icon Display**: Floating button now uses `icon.ico` from project root
- Automatically loads and displays the project icon
- Falls back to custom chat icon if icon.ico not found
- Smooth scaling and rendering with anti-aliasing

## Version 1.0.1 - Bug Fixes

### Fixed Issues

#### 1. Missing QRect Import
**Error**: `NameError: name 'QRect' is not defined`

**Fix**: Added `QRect` to imports in `floating_button.py`
```python
from PySide6.QtCore import (
    Qt, QPoint, QRect, QPropertyAnimation, QEasingCurve, QTimer, Signal, Property
)
```

#### 2. Property Animation Not Working
**Error**: `QPropertyAnimation: you're trying to animate a non-existing property scale_factor`

**Fix**: Changed from Python property to Qt Property
- Renamed property from `scale_factor` to `scaleFactor` (camelCase for Qt)
- Changed from `property()` to `Property()` (Qt's Property class)
- Updated animation references to use `b"scaleFactor"`

**Before**:
```python
scale_factor = property(get_scale_factor, set_scale_factor)
self._hover_animation = QPropertyAnimation(self, b"scale_factor")
```

**After**:
```python
scaleFactor = Property(float, getScaleFactor, setScaleFactor)
self._hover_animation = QPropertyAnimation(self, b"scaleFactor")
```

#### 3. Register Function Not Found
**Error**: `Addon floating_chat does not have a register function`

**Fix**: Updated `__init__.py` to import and expose the register function
```python
from .main import register
__all__ = ['register']
```

### Testing

All fixes verified:
- ✅ Addon loads successfully
- ✅ Floating button appears
- ✅ Animations work smoothly
- ✅ No Qt warnings
- ✅ Cross-platform compatible

### Files Modified

1. `addons/floating_chat/__init__.py` - Added register import
2. `addons/floating_chat/floating_button.py` - Fixed imports and property animation

### Verification

Run the verification script to confirm all fixes:
```bash
python verify_floating_chat.py
```

Or test directly:
```bash
python launch.py
```

The floating button should now appear without errors!
