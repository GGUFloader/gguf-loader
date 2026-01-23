# Quick Start Guide - Floating Chat Addon

Get started with the Facebook Messenger-style floating chat button in under 2 minutes!

## 🚀 Quick Start

### Step 1: Launch GGUF Loader
```bash
python launch.py
```

### Step 2: Load an AI Model
1. Click "Browse" in the main window
2. Select your GGUF model file
3. Click "Load Model"
4. Wait for model to load (status will show "Model Loaded")

### Step 3: Use Floating Chat
1. Look for the blue floating button on your screen (usually appears at position 100, 100)
2. Click and drag it to your preferred position
3. Click the button to open the chat window
4. Type a message and press Ctrl+Enter or click "Send"

That's it! You're chatting with AI using the floating button.

## 💡 Tips

### Moving the Button
- **Click and drag** the button anywhere on your screen
- Position is **automatically saved** for next time
- Works across **multiple monitors**

### Using the Chat
- **Ctrl+Enter**: Quick send message
- **Clear button**: Clear chat history
- **Close window**: Click X or click floating button again

### Keyboard Shortcuts
- `Ctrl+Enter` - Send message
- `Esc` - Close chat window (when focused)

## 🎨 Visual Guide

```
┌─────────────────────────────────────┐
│  Your Desktop                       │
│                                     │
│                    ┌──────────────┐ │
│                    │ 💬 AI Chat   │ │
│                    ├──────────────┤ │
│                    │ User: Hello  │ │
│                    │ AI: Hi there!│ │
│   ╭───╮            ├──────────────┤ │
│   │ 💬│◄───Click   │ Type here... │ │
│   ╰───╯            │ [Send]       │ │
│  Floating          └──────────────┘ │
│  Button                             │
└─────────────────────────────────────┘
```

## 🔧 Troubleshooting

### Can't find the floating button?
The button might be off-screen. To reset:
1. Close GGUF Loader
2. Delete settings:
   - **Windows**: Delete registry key `HKEY_CURRENT_USER\Software\GGUFLoader\FloatingChat`
   - **Linux**: Delete `~/.config/GGUFLoader/FloatingChat.conf`
   - **macOS**: Delete `~/Library/Preferences/com.GGUFLoader.FloatingChat.plist`
3. Restart GGUF Loader

### Chat says "Model: Not loaded"?
1. Go to main GGUF Loader window
2. Load a model first
3. Green indicator will appear when ready

### Button not draggable on Linux?
If using Wayland, try:
```bash
QT_QPA_PLATFORM=xcb python launch.py
```

## 🎯 Next Steps

- Customize button size and colors (see README.md)
- Integrate with your workflow
- Try different AI models
- Explore other GGUF Loader addons

## 📚 More Information

- Full documentation: `README.md`
- Report issues: GitHub Issues
- Addon API: `docs/gguf-loader-addon-api.md`

---

**Enjoy your floating AI chat! 🎉**
