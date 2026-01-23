# Changelog - Floating Chat Addon

All notable changes to the Floating Chat addon will be documented in this file.

## [1.0.2] - 2024-01-23

### Changed
- **Icon Display**: Floating button now uses `icon.ico` from project root instead of custom-drawn chat icon
- Enhanced icon loading with fallback to resource_manager
- Improved icon rendering with smooth scaling and anti-aliasing
- Icon is displayed at 70% of button size for proper padding

### Technical Details
- Added `_load_icon()` method to load icon.ico
- Added `_draw_icon()` method for icon rendering
- Falls back to `_draw_chat_icon()` if icon not found
- Uses `QPixmap` with `SmoothTransformation` for high-quality scaling

## [1.0.1] - 2024-01-23

### Fixed
- **Missing Import**: Added `QRect` to imports in `floating_button.py`
- **Property Animation**: Changed from Python property to Qt Property for proper animation support
- **Register Function**: Updated `__init__.py` to properly expose register function

## [1.0.0] - 2024-01-23

### 🎉 Initial Release

#### Added
- **Floating Button Widget**
  - Always-on-top draggable button
  - Facebook Messenger-style design
  - Smooth hover and click animations
  - Custom gradient rendering with chat icon
  - Position persistence across sessions
  - Cross-platform window flags (Windows, Linux, macOS)

- **Chat Window Interface**
  - Clean, modern chat UI
  - Message history display with HTML formatting
  - User and AI message bubbles with distinct styling
  - Model status indicator
  - Multi-line input field
  - Send button and Ctrl+Enter shortcut
  - Clear chat functionality
  - Auto-scroll to latest message

- **GGUF Loader Integration**
  - Direct connection to main app
  - Automatic model detection
  - Chat generator integration
  - Signal-based event system
  - Error handling and recovery

- **Addon System Integration**
  - Register function for addon manager
  - Status widget for sidebar
  - Lifecycle management (start/stop)
  - Settings persistence with QSettings

- **Documentation**
  - README.md - Complete user guide
  - QUICK_START.md - 2-minute getting started guide
  - FEATURES.md - Comprehensive feature list
  - CHANGELOG.md - This file

- **Testing**
  - test_floating_button.py - Standalone test script
  - Cross-platform testing on Windows, Linux, macOS

#### Technical Details
- Built with PySide6 (Qt6)
- Python 3.8+ compatible
- ~1000 lines of well-documented code
- MVC architecture pattern
- Event-driven with Qt signals/slots
- Hardware-accelerated rendering

#### Platform Support
- ✅ Windows 10/11
- ✅ Linux (X11 and Wayland)
- ✅ macOS 10.15+

#### Known Limitations
- Chat history not persisted between sessions
- Single chat window instance only
- Requires AI model to be loaded in main app

---

## Future Versions

### [1.1.0] - Planned
- [ ] Chat history persistence
- [ ] Export conversations to file
- [ ] Custom themes and colors
- [ ] Global hotkey support
- [ ] Notification sounds

### [1.2.0] - Planned
- [ ] Multiple chat windows
- [ ] Markdown rendering in messages
- [ ] Code syntax highlighting
- [ ] Voice input support
- [ ] Image attachments

### [2.0.0] - Future
- [ ] Plugin system for chat commands
- [ ] Custom AI personalities
- [ ] Advanced positioning (snap-to-edge, auto-hide)
- [ ] Transparency and size customization UI
- [ ] Multi-language interface

---

## Version History Format

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

### Types of Changes
- **Added** - New features
- **Changed** - Changes in existing functionality
- **Deprecated** - Soon-to-be removed features
- **Removed** - Removed features
- **Fixed** - Bug fixes
- **Security** - Vulnerability fixes

---

**Note**: This is the initial release. Future updates will be documented here.
