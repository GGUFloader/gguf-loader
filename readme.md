# 🧠 GGUF Loader - Offline LLM Launcher
 
**GGUF Loader** is a lightweight, GUI-based desktop application for loading **GGUF-format language models** locally — with zero cloud or API dependency. Designed with simplicity in mind, it's a perfect fit for AI beginners, students, and educational use.
> ✅ 100% offline  
> ✅ GGUF model support (e.g., Mistral, LLaMA, Qwen)  
> ✅ Clean user interface (no terminal needed)  
> ✅ Ready to be extended with PDF Q&A, translation, and more

---

## 💡 Features

- 🔍 **Load any LLM `.gguf` model** via GUI
- 🖱️ Just select your model path and launch
- 💻 No command-line required — beginner-friendly!
- ⚙️ Built with Python + PySide6, bundled as `.exe` for Windows
- 🌐 Future-ready: built to support multilingual PDF Q&A

---

## 🚀 Getting Started

### 📦 Download the App

> For Code to Inspire use: just run the provided `LLM-Loader.exe`  
> No Python or setup required!

### 🔧 For Developers

1. Clone the repo
2. (Optional) Create and activate a virtual environment
3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Run the app:

```bash
python main.py
```

---

## 🛠️ Building the App (for advanced users)

To compile to a standalone `.exe`:

```bash
pyinstaller main.spec
```

Make sure to:

- Keep `icon.ico` in the project root
- Include GGUF models externally or in runtime instructions
- Verify DLLs and icons are bundled properly (see `main.spec`)

---

## 📁 Folder Structure

```
locald/
├── assets/
├── models/
├── llama_cpp/
├── main.py
├── main.spec
├── requirements.txt
├── ico=.ico
└── dist/
    └── LLM-Loader.exe
```

---

## 🙌 Credits

- Powered by: `llama-cpp-python`, `PySide6`, and open-source AI models

---

## 📚 License

MIT License — you are free to use, modify, and contribute. If you use this in your own teaching projects, a mention would be appreciated!

---

> _"Real innovation happens when we give tools to those who never had access before."_  
> — Hussain
