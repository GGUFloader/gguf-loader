# Quick Update Notification Guide

## 🎯 What It Does

Automatically notifies users when a new version of GGUF Loader is available on GitHub.

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Test It Works
```bash
python test_update_checker.py
```

### 3. Run Your App
```bash
python main.py
# or
python gguf_loader_main.py
```

That's it! The update notification will appear automatically if a new version is available.

## 📸 What Users See

When an update is available, a blue banner appears at the top:

```
🎉 New version available! v2.0.1 → v2.1.0  [Download] [Notes] [✕]
```

## 🎨 Customization

### Change Check Delay

In `main.py` or `gguf_loader_main.py`, find:
```python
QTimer.singleShot(2000, check_updates)  # 2 seconds
```

Change to:
```python
QTimer.singleShot(5000, check_updates)  # 5 seconds
QTimer.singleShot(60000, check_updates)  # 1 minute
```

### Disable Update Checks

Comment out the line:
```python
# QTimer.singleShot(2000, check_updates)
```

### Change Banner Colors

Edit `widgets/update_notification.py`:
```python
# Find the setStyleSheet section and modify colors
background-color: #dbeafe;  # Light blue
border: 2px solid #3b82f6;  # Blue border
```

## 🧪 Testing

### Test Update Checker
```bash
python test_update_checker.py
```

Shows:
- Current version
- Latest version
- Download URL
- Release notes

### Test UI Banner
```bash
python demo_update_notification.py
```

Shows:
- Visual demo of the notification banner
- Interactive buttons

## 📁 Key Files

- `update_checker.py` - Core logic
- `widgets/update_notification.py` - UI banner
- `main.py` - Integration (basic version)
- `gguf_loader_main.py` - Integration (addon version)

## 🔧 How It Works

1. App starts
2. After 2 seconds, checks GitHub API
3. Compares current version with latest release
4. If newer version exists, shows banner
5. User clicks "Download" → Opens browser
6. User clicks "Release Notes" → Opens GitHub
7. User clicks ✕ → Dismisses banner

## 🌐 Network

- **Checks**: GitHub API once per app launch
- **Timeout**: 5 seconds
- **Privacy**: No personal data sent
- **Offline**: Fails silently (no errors)

## ✅ Verification Checklist

- [ ] `pip install packaging` completed
- [ ] `python test_update_checker.py` shows version info
- [ ] `python demo_update_notification.py` shows banner
- [ ] `python main.py` starts without errors
- [ ] Banner appears if update available (or check logs)

## 📚 Full Documentation

- **User Guide**: `docs/update-notifications.md`
- **Developer Guide**: `UPDATE_SYSTEM_README.md`
- **Implementation**: `IMPLEMENTATION_SUMMARY.md`

## 🎉 Done!

Your app now has professional update notifications! Users will always know when new versions are available.
