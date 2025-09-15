# Quick Start Guide

Get up and running with GGUF Loader 2.0.0 in just a few minutes!

## 🚀 Installation

```bash
pip install ggufloader
```

## 🎯 Launch GGUF Loader

```bash
ggufloader
```

This opens GGUF Loader with the Smart Floating Assistant addon already loaded.

## 📥 Load Your First Model

### Step 1: Get a GGUF Model

Download a GGUF model from one of these sources:

#### Popular Model Sources:
- **Hugging Face**: [https://huggingface.co/models?library=gguf](https://huggingface.co/models?library=gguf)
- **TheBloke's Models**: Search for "TheBloke" on Hugging Face
- **Local Models**: Convert your own models to GGUF format

#### Recommended Starter Models:
- **Small (2-4GB)**: `llama-2-7b-chat.Q4_K_M.gguf`
- **Medium (4-8GB)**: `mistral-7b-instruct-v0.1.Q5_K_M.gguf`
- **Large (8GB+)**: `llama-2-13b-chat.Q4_K_M.gguf`

### Step 2: Load the Model

1. **Click "Select GGUF Model"** in the main window
2. **Browse and select** your downloaded `.gguf` file
3. **Wait for loading** (this may take 1-5 minutes depending on model size)
4. **Look for "Model ready!"** message

## 💬 Test Basic Chat

### Try Your First Chat

1. **Type a message** in the chat input box
2. **Press Enter** or click "Send"
3. **Watch the AI respond** in real-time
4. **Continue the conversation!**

#### Example Conversations:
```
You: Hello! How are you today?
AI: Hello! I'm doing well, thank you for asking. I'm here and ready to help you with any questions or tasks you might have. How can I assist you today?

You: Can you explain what GGUF models are?
AI: GGUF (GPT-Generated Unified Format) is a file format designed for storing large language models...
```

## ✨ Use the Smart Floating Assistant

The Smart Floating Assistant is GGUF Loader's killer feature - it works across ALL applications!

### Step 1: Select Text Anywhere

1. **Open any application** (browser, Word, Notepad, etc.)
2. **Select some text** by highlighting it with your mouse
3. **Look for the ✨ floating button** that appears near your cursor

### Step 2: Process the Text

1. **Click the ✨ button**
2. **Choose an action**:
   - **Summarize**: Get a concise summary
   - **Comment**: Generate an insightful comment
3. **Wait for AI processing**
4. **Copy the result** and use it anywhere!

#### Example Workflow:
```
1. Reading a long article in your browser
2. Select a complex paragraph
3. Click ✨ → "Summarize"
4. Get: "This paragraph explains that..."
5. Copy and paste the summary into your notes
```

## 🎛️ Basic Settings

### Model Settings

- **Temperature**: Controls creativity (0.1 = focused, 1.0 = creative)
- **Max Tokens**: Maximum response length
- **Context Size**: How much conversation history to remember

### Smart Assistant Settings

- **Enable/Disable**: Toggle the floating assistant
- **Response Speed**: Adjust processing speed vs quality
- **Auto-copy**: Automatically copy results to clipboard

## 🔧 Common Tasks

### Task 1: Summarize Articles

1. **Open an article** in your browser
2. **Select the main content**
3. **Click ✨ → "Summarize"**
4. **Get a concise summary**

### Task 2: Generate Comments

1. **Select a social media post** or forum discussion
2. **Click ✨ → "Comment"**
3. **Get a thoughtful response**
4. **Edit and post** your AI-assisted comment

### Task 3: Process Code

1. **Select code** in your IDE or GitHub
2. **Click ✨ → "Comment"**
3. **Get code explanation** or suggestions

### Task 4: Email Assistance

1. **Select email content**
2. **Click ✨ → "Summarize"** for long emails
3. **Click ✨ → "Comment"** to draft responses

## 🎨 Customization

### Addon Management

1. **Click the addon sidebar** (left panel)
2. **View loaded addons**
3. **Click addon names** to open their interfaces
4. **Manage addon settings**

### Themes and UI

- **Dark/Light Mode**: Available in settings
- **Font Size**: Adjustable for better readability
- **Window Layout**: Resizable panels

## 🐛 Quick Troubleshooting

### Model Won't Load
- **Check file format**: Must be `.gguf`
- **Check file size**: Ensure enough RAM
- **Try smaller model**: Start with 4GB or less

### Floating Assistant Not Working
- **Check model**: Must have a model loaded first
- **Try different text**: Select at least 5+ characters
- **Restart application**: Sometimes helps with initialization

### Performance Issues
- **Close other apps**: Free up RAM
- **Use smaller model**: Try Q4 quantization
- **Enable GPU**: If you have compatible hardware

## 📚 Next Steps

### Learn More
- **[User Guide](user-guide.md)**: Complete feature documentation
- **[Addon Development](addon-development.md)**: Create custom addons
- **[Configuration](configuration.md)**: Advanced settings

### Get Involved
- **[GitHub](https://github.com/gguf-loader/gguf-loader)**: Source code and issues
- **[Discussions](https://github.com/gguf-loader/gguf-loader/discussions)**: Community support
- **[Contributing](contributing.md)**: Help improve GGUF Loader

## 💡 Pro Tips

### Efficiency Tips
1. **Use keyboard shortcuts**: Learn the hotkeys for faster workflow
2. **Bookmark good models**: Keep a list of your favorite GGUF models
3. **Organize your workflow**: Use the floating assistant for specific tasks
4. **Experiment with prompts**: Different phrasings get different results

### Model Selection Tips
1. **Start small**: Begin with 7B parameter models
2. **Match your hardware**: Don't exceed your RAM capacity
3. **Try different quantizations**: Q4_K_M is a good balance
4. **Read model cards**: Check Hugging Face for model details

### Smart Assistant Tips
1. **Select quality text**: Better input = better output
2. **Use specific actions**: "Summarize" vs "Comment" give different results
3. **Edit the results**: AI output is a starting point, not final copy
4. **Practice regularly**: The more you use it, the more useful it becomes

## 🎉 You're Ready!

Congratulations! You now know the basics of GGUF Loader 2.0.0. The Smart Floating Assistant will transform how you work with text across all your applications.

### What You've Learned:
- ✅ How to install and launch GGUF Loader
- ✅ How to load and use GGUF models
- ✅ How to use the Smart Floating Assistant
- ✅ Basic troubleshooting and customization

### Ready for More?
- 📖 Dive deeper with the [User Guide](user-guide.md)
- 🛠️ Create addons with the [Development Guide](addon-development.md)
- 🤝 Join our [community discussions](https://github.com/gguf-loader/gguf-loader/discussions)

---

**Happy AI-powered text processing! 🚀**

Need help? Contact us at support@ggufloader.com or visit our [support page](troubleshooting.md).