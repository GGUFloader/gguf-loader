# Auto-Update System - Quick Guide

## 🚀 For Users

### How to Update

1. **Start the app** - GGUF Loader checks for updates automatically
2. **See the notification** - Blue banner appears if update available
3. **Click "🚀 Update Now"** - One-click automatic update
4. **Wait** - Progress bar shows download and installation
5. **Done!** - App restarts automatically with new version

### What Gets Updated

✅ **Updated:**
- Application code files
- UI components
- Bug fixes and new features

❌ **Never Touched:**
- Your AI models
- Your chat history
- Your settings and configs
- Your exports

### Benefits

- **Fast**: Only downloads changed files (5-50 MB vs 150-300 MB)
- **Safe**: Creates backup before updating
- **Smart**: Automatic rollback if anything fails
- **Easy**: One click, no manual steps

##  For Developers

### Files Structure

```
updater/
 __init__.py                    # Module init
 update_checker.py              # Check GitHub for updates
├── auto_updater.py                # Download and apply updates
├── test_update_checker.py         # Test script
├── demo_update_notification.py    # UI demo
└── README.md                      # Full documentation
```

### Integration

The update system is already integrated in:
- `main.py` - Basic version
- `gguf_loader_main.py` - Addon version
- `widgets/update_notification.py` - UI banner

### Testing

```bash
# Test update checker
cd updater
python test_update_checker.py

# Test UI
cd updater
python demo_update_notification.py

# Test full app
python main.py
```

### How It Works

1. **Check** - Queries GitHub API for latest release
2. **Download** - Downloads release archive
3. **Compare** - Calculates file hashes, finds changes
4. **Backup** - Backs up files to be updated
5. **Update** - Copies only changed files
6. **Restart** - Restarts app automatically

### Key Features

- **Delta Patching** - Only updates changed files
- **Hash Verification** - MD5 comparison
- **Automatic Backup** - Rollback on failure
- **Thread-Safe** - Background updates
- **Progress Tracking** - Real-time progress bar
- **User Data Protection** - Excludes models, chats, configs

##  Documentation

- **Full Guide**: `updater/README.md`
- **User Docs**: `docs/update-notifications.md`
- **API Docs**: See docstrings in `updater/*.py`

##  Quick Examples

### Check for Updates
```python
from updater.update_checker import UpdateChecker

checker = UpdateChecker()
info = checker.check_for_updates()

if info and info['available']:
    print(f"New version: {info['latest_version']}")
```

### Auto Update
```python
from updater.auto_updater import AutoUpdater

updater = AutoUpdater("2.0.1")
success = updater.download_update("2.1.0")

if success:
    updater.restart_application()
```

##  Safety

-  Backup before update
-  Rollback on failure
-  User data never touched
-  Confirmation dialog
-  Error logging

##  Support

- Full docs: `updater/README.md`
- Issues: GitHub Issues
- Questions: GitHub Discussions
