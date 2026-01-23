# User Guide

Complete guide to using GGUF Loader.

## Getting Started

### 1. Launch the Application

Choose your method:
- **Windows Executable:** Double-click `GGUFLoader.exe`
- **Installed via pip:** Run `ggufloader` in terminal
- **From source:** Run `launch.bat` (Windows) or `./launch.sh` (Linux/macOS)

### 2. Load a Model

1. Click the **Load Model** button
2. Browse to your `.gguf` model file
3. Wait for the model to load (progress shown in status bar)
4. Once loaded, you're ready to chat!

### 3. Start Chatting

1. Type your message in the input box
2. Press Enter or click **Send**
3. The AI will respond based on the loaded model

## Features

### System Prompts

Pre-configured prompts for different use cases:

- **Bilingual Assistant** - Responds in your language
- **Creative Writer** - For creative writing tasks
- **Code Expert** - Programming assistance
- **Professional Translator** - Translation between languages

Select from the dropdown menu before chatting.

### Generation Settings

Customize AI behavior:

- **Temperature** (0.1-1.0) - Controls creativity
  - Lower = More focused and deterministic
  - Higher = More creative and varied
- **Max Tokens** - Maximum response length
- **Top P** - Nucleus sampling parameter
- **Top K** - Top-k sampling parameter

### Themes

Switch between visual themes:
- Light (default)
- Dark
- Persian Classic

### Chat Management

- **Clear Chat** - Remove all messages
- **Export Chat** - Save conversation to file
- **Copy Messages** - Copy individual messages

## Smart Floating Assistant

The Smart Floating Assistant works globally across all applications.

### How to Use

1. Select any text in any application
2. A floating ✨ button appears near your cursor
3. Click the button
4. Choose an action:
   - **Summarize** - Get a concise summary
   - **Comment** - Get AI commentary
5. View results in the popup window

### Requirements

- A model must be loaded in the main application
- The addon must be enabled (check addon sidebar)

## Addon System

### Managing Addons

1. View available addons in the left sidebar
2. Click addon names to open their interfaces
3. Use **🔄 Refresh** to reload addons

### Installing Addons

Place addon folders in the `addons/` directory. Each addon should have:
```
addons/
└── your_addon/
    ├── __init__.py
    └── main.py
```

See [Addon Development Guide](addon-development.md) for details.

## Keyboard Shortcuts

- **Enter** - Send message
- **Shift+Enter** - New line in input
- **Ctrl+L** - Clear chat
- **Ctrl+K** - Load model

## Tips & Best Practices

### Model Selection

- **4GB RAM:** Use Q4_0 quantized models (4-5GB)
- **8GB RAM:** Use Q6_K quantized models (6-7GB)
- **16GB+ RAM:** Use Q8_0 or larger models

### Performance

- Close other memory-intensive applications
- Use smaller models for faster responses
- Adjust max_tokens for shorter responses

### Privacy

- All processing happens locally
- No data sent to external servers
- Models and chats stored on your machine

## Troubleshooting

### Model Won't Load

- Verify the file is a valid `.gguf` format
- Check available RAM
- Try a smaller/quantized model

### Slow Responses

- Use a smaller model
- Reduce max_tokens setting
- Close other applications

### Application Crashes

- Check logs in `logs/` directory
- Ensure sufficient RAM available
- Try the basic version without addons

### Smart Floater Not Working

- Verify a model is loaded
- Check addon is enabled
- Restart the application

## Getting Help

- Check the [FAQ](faq.md)
- Report issues on [GitHub](https://github.com/GGUFloader/gguf-loader/issues)
- Email: hossainnazary475@gmail.com
