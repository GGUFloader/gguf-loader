# Update Notifications

GGUF Loader automatically checks for new versions and notifies you when updates are available.

## How It Works

1. **Automatic Check**: When you start GGUF Loader, it checks GitHub for new releases after 2 seconds
2. **Non-Intrusive**: The check happens in the background and won't slow down your app
3. **Smart Notification**: Only shows a banner if a newer version is available
4. **Easy Update**: Click "Download Update" to go directly to the latest release

## Update Banner

When a new version is available, you'll see a blue banner at the top of the window:

```
🎉 New version available! v2.0.1 → v2.1.0  [Download Update] [Release Notes] [✕]
```

### Banner Actions

- **Download Update**: Opens your browser to download the latest version
- **Release Notes**: View what's new in the latest version
- **✕ (Close)**: Dismiss the notification (you can update later)

## Manual Update Check

To manually check for updates, you can run:

```bash
python test_update_checker.py
```

This will show:
- Your current version
- Latest available version
- Download link
- Release notes

## Update Process

### For Windows .exe Users

1. Click "Download Update" in the notification banner
2. Download the new `.exe` file
3. Close GGUF Loader
4. Run the new `.exe` file
5. Your settings and chats are preserved!

### For Python Users

1. Update via pip:
   ```bash
   pip install --upgrade ggufloader
   ```

2. Or update from source:
   ```bash
   git pull origin main
   pip install -r requirements.txt
   ```

## Privacy & Network

- **What's Sent**: Only a version check request to GitHub's public API
- **What's NOT Sent**: No personal data, usage statistics, or model information
- **Offline Mode**: If you're offline, the check silently fails (no errors shown)
- **Frequency**: Only checks once per app launch

## Disabling Update Checks

If you want to disable automatic update checks, you can modify `main.py` or `gguf_loader_main.py`:

```python
# Comment out or remove these lines:
# QTimer.singleShot(2000, check_updates)
```

Or set a longer delay (e.g., check after 1 hour):

```python
QTimer.singleShot(3600000, check_updates)  # 1 hour in milliseconds
```

## Troubleshooting

### "No update notification appears"

This is normal if:
- You're already on the latest version
- You're offline or GitHub is unreachable
- The check is still in progress (wait 5-10 seconds)

### "Update check fails"

Possible causes:
- No internet connection
- GitHub API rate limit (rare, resets hourly)
- Firewall blocking GitHub access

To diagnose, run:
```bash
python test_update_checker.py
```

### "Downloaded update but still shows old version"

Make sure you:
1. Closed the old version completely
2. Are running the newly downloaded file
3. Didn't just copy over the old file

## Technical Details

### Version Comparison

GGUF Loader uses semantic versioning (e.g., `2.0.1`):
- **Major** version (2.x.x): Breaking changes
- **Minor** version (x.0.x): New features
- **Patch** version (x.x.1): Bug fixes

The update checker uses the `packaging` library to properly compare versions.

### GitHub API

- **Endpoint**: `https://api.github.com/repos/GGUFloader/gguf-loader/releases/latest`
- **Rate Limit**: 60 requests/hour (unauthenticated)
- **Timeout**: 5 seconds
- **User Agent**: `GGUF-Loader/{version}`

### Files Involved

- `update_checker.py`: Core update checking logic
- `widgets/update_notification.py`: UI notification banner
- `main.py`: Integration for basic version
- `gguf_loader_main.py`: Integration for addon version
- `test_update_checker.py`: Manual testing tool

## Future Enhancements

Planned features:
- [ ] Auto-download updates (optional)
- [ ] In-app changelog viewer
- [ ] Update preferences in settings
- [ ] Beta/stable channel selection
- [ ] Notification frequency settings

## Support

If you have issues with updates:
- Check [GitHub Releases](https://github.com/GGUFloader/gguf-loader/releases)
- Report bugs in [Issues](https://github.com/GGUFloader/gguf-loader/issues)
- Ask questions in [Discussions](https://github.com/GGUFloader/gguf-loader/discussions)
