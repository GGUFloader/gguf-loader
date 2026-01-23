# Frequently Asked Questions

## General

### What is GGUF Loader?

GGUF Loader is a desktop application that lets you run large language models (LLMs) locally on your computer. It supports GGUF format models and provides a user-friendly interface for chatting with AI.

### Is it free?

Yes, GGUF Loader is completely free and open source under the MIT License.

### Does it work offline?

Yes! Once you've downloaded a model, everything runs locally on your machine with no internet connection required.

### What platforms are supported?

- Windows 10/11
- Linux (most distributions)
- macOS

## Installation

### Do I need Python installed?

- **Windows Executable:** No, Python is bundled
- **pip install:** Yes, Python 3.7+ required
- **From source:** Yes, Python 3.7+ required

### How much disk space do I need?

- Application: ~500MB
- Models: 4-20GB each (depending on model size)
- Recommended: 10GB+ free space

### Can I install it on a USB drive?

Yes, the portable executable can run from a USB drive. Just copy the entire folder.

## Models

### Where do I get models?

Download GGUF models from:
- [Hugging Face](https://huggingface.co/models?library=gguf)
- [TheBloke's Collection](https://local-ai-zone.github.io)
- Model links in our [README](../README.md)

### What model size should I use?

Based on your RAM:
- **4GB RAM:** Q4_0 models (4-5GB)
- **8GB RAM:** Q6_K models (6-7GB)
- **16GB+ RAM:** Q8_0 or larger models

### What does Q4_0, Q6_K mean?

These are quantization levels:
- **Q4_0:** 4-bit quantization (smaller, faster, less accurate)
- **Q6_K:** 6-bit quantization (balanced)
- **Q8_0:** 8-bit quantization (larger, slower, more accurate)

### Can I use multiple models?

Yes, but only one model can be loaded at a time. You can switch models by loading a different file.

### Do I need a GPU?

No, GGUF Loader works on CPU. GPU acceleration is optional and can improve performance.

## Usage

### How do I load a model?

1. Click the "Load Model" button
2. Browse to your `.gguf` file
3. Wait for it to load
4. Start chatting!

### Why are responses slow?

- **Large model:** Try a smaller/quantized model
- **Low RAM:** Close other applications
- **CPU-bound:** Consider GPU acceleration
- **High max_tokens:** Reduce in settings

### Can I save my chats?

Yes, use the "Export Chat" feature to save conversations to a file.

### How do I change the AI's personality?

Use the System Prompts dropdown to select different personalities (Creative Writer, Code Expert, etc.) or create custom prompts.

## Smart Floating Assistant

### What is the Smart Floating Assistant?

An addon that lets you select text anywhere on your system and process it with AI (summarize, comment, etc.).

### How do I enable it?

It's enabled by default. Check the addon sidebar to verify it's active.

### Why isn't the floating button appearing?

- Ensure a model is loaded
- Check the addon is enabled
- Try restarting the application
- Verify clipboard permissions

### Does it work in all applications?

Yes, it works globally across all applications on your system.

## Addons

### What are addons?

Addons are extensions that add new features to GGUF Loader. They can add UI components, process text in custom ways, or integrate with external services.

### How do I install an addon?

1. Download the addon folder
2. Place it in the `addons/` directory
3. Restart GGUF Loader
4. The addon will appear in the sidebar

### Can I create my own addon?

Yes! See the [Addon Development Guide](addon-development.md) for instructions.

### Where can I find more addons?

Check:
- GitHub discussions
- Community forums
- Addon marketplace (coming soon)

## Troubleshooting

### Application won't start

- Verify Python 3.7+ is installed (if running from source)
- Try deleting the `venv` folder and re-running launch script
- Check antivirus isn't blocking the application
- Look for error messages in `logs/` directory

### Model won't load

- Verify the file is a valid `.gguf` format
- Check you have enough RAM available
- Try a smaller model
- Ensure the file isn't corrupted (re-download if needed)

### "Out of memory" error

- Close other applications
- Use a smaller/more quantized model
- Reduce max_tokens setting
- Restart your computer to free up RAM

### Application crashes

- Check logs in `logs/` directory
- Try the basic version without addons
- Verify your system meets minimum requirements
- Report the issue on GitHub with log files

### Responses are gibberish

- Model may be corrupted (re-download)
- Try adjusting temperature setting
- Use a different model
- Check system prompt is appropriate

## Privacy & Security

### Is my data sent anywhere?

No, all processing happens locally on your machine. No data is sent to external servers.

### Where are my chats stored?

Chats are stored locally in the `chats/` directory on your computer.

### Can others see my conversations?

No, unless they have physical access to your computer and the `chats/` directory.

### Is it safe to use?

Yes, GGUF Loader is open source and you can review the code. All processing is local and private.

## Performance

### How can I make it faster?

- Use smaller/quantized models (Q4_0)
- Reduce max_tokens setting
- Close other applications
- Enable GPU acceleration (if available)
- Upgrade RAM

### Does it support GPU acceleration?

Yes, if you have a compatible GPU and the necessary drivers installed. GPU support depends on the llama-cpp-python library.

### How much RAM do I need?

- **Minimum:** 4GB (for small models)
- **Recommended:** 8GB
- **Optimal:** 16GB+

## Contributing

### How can I contribute?

See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines on:
- Reporting bugs
- Suggesting features
- Submitting code
- Improving documentation

### I found a bug, what should I do?

1. Check if it's already reported on [GitHub Issues](https://github.com/GGUFloader/gguf-loader/issues)
2. If not, create a new issue with:
   - Description of the bug
   - Steps to reproduce
   - Your system info
   - Log files (if applicable)

### Can I request features?

Yes! Open a feature request on [GitHub Issues](https://github.com/GGUFloader/gguf-loader/issues) or discuss in [GitHub Discussions](https://github.com/GGUFloader/gguf-loader/discussions).

## Still Have Questions?

- 📧 Email: hossainnazary475@gmail.com
- 💬 [GitHub Discussions](https://github.com/GGUFloader/gguf-loader/discussions)
- 🐛 [Report Issues](https://github.com/GGUFloader/gguf-loader/issues)
