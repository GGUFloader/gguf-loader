# Frequently Asked Questions

Common questions about GGUF Loader, answered for the current build (a
single-model, plan-driven agent app with a React frontend on a FastAPI
backend).

---

## General

### What is GGUF Loader?

A privacy-first desktop application that runs one large language model -
Google **Gemma 4 12B Instruct (Q4_K_M)** - fully locally. It combines a
streaming chat with an **agent mode** that plans and executes multi-step file
tasks (read, search, write, edit, run commands, git) inside a workspace folder
you choose. Everything runs on your machine.

### Does GGUF Loader need the internet?

No. Inference is 100% local. The only online step is the one-time **download of
the model file** (the app can do it for you). Optional API providers, GPU
packages, and update checks use the network only if you enable them.

### Which model does this build run?

Exactly one: **Gemma 4 12B Instruct, Q4_K_M** (`gemma-4-12B-it-Q4_K_M.gguf`).
The app is deliberately optimized for that model - prompts, sampling, and
context settings are tuned for it. Other GGUF files are rejected at load time
with a clear message.

### What happened to the old multi-model version?

Earlier versions loaded any GGUF. This build intentionally dropped that in
favor of a single, well-tuned model so everything "just works" - no model
family detection, no per-model prompt headaches. Older multi-model docs are
kept for reference and marked as historical.

---

## The Model

### How do I get the model loaded?

You usually do not have to do anything:

1. Drop the file `gemma-4-12B-it-Q4_K_M.gguf` into the app's `models/` folder
   (or any folder you point the picker at), then start the app - it
   **auto-loads the model in the background**.
2. If the file is missing, the **model chip in the header** offers a
   **Download** action with live progress, and loads the model automatically
   once the download finishes.

There is no manual "Load Model" step anymore.

### Where can I download the model manually?

Search Hugging Face for Gemma 4 12B Instruct GGUF (Q4_K_M) - the app's pinned
file is `gemma-4-12B-it-Q4_K_M.gguf`. Place it in the `models/` folder (or a
folder you choose via the model picker) and restart, or just use the in-app
Download button.

### How much RAM / disk do I need?

- The model file is about **8 GB** on disk.
- Plan for **8-10 GB of free RAM** while running; close other heavy apps if it
  is sluggish. GPU offloading lowers CPU/RAM pressure.

### Can I use a different or larger model?

No - not in this build. It is pinned to Gemma 4 12B Q4_K_M by design. If you
need another model, use the multi-model (Qt-era) releases or fork the code;
the current codebase intentionally hard-codes one model.

### Do I need a GPU?

No, it runs on CPU. An NVIDIA GPU (CUDA) or Apple Silicon (Metal) speeds things
up considerably: open **Settings > Hardware** and install GPU support, then
restart.

---

## Using the App

### What is the difference between Chat and Agent Mode?

- **Chat mode** - the model answers your questions directly.
- **Agent Mode** (toggle with **Ctrl/Cmd + Shift + A**) - a planner analyzes
  your prompt. For tool-free questions it answers directly too; for tasks it
  writes a step-by-step plan, executes the steps with sandboxed tools, and
  produces a final answer. You watch the whole process inline.

### Which tools does the agent have?

Listing/reading files, writing, editing, moving, searching file content, running
shell commands, executing code, and git. Commands, code execution, and git
**writes** pause for an **Allow / Deny** approval card; everything is sandboxed
to the workspace folder you grant.

### Can I save and resume chats?

Yes. Every conversation is a session (left panel) and agent runs are
checkpointed to SQLite, so they survive restarts. The right-hand panel also has
export/import tools for sessions.

### How do I steer the assistant's behavior?

In **Settings > Agent** pick a preset (Research, Code Review, Refactor, Debug,
Full Stack, Quick Fix, ...), which sets the system prompt and sampling profile.

### Answers occasionally show raw tool output or JSON - is that normal?

It should not happen. A run's final answer is meant to be clean markdown; if a
reply ever arrives as raw JSON or repeated fragments, press **Esc**, ask again,
or restart the app. If it keeps happening, report it with the server log - it
is treated as a bug.

### Where is the old Smart Floating Assistant / floating chat?

It belonged to the previous PySide6-era build. The current React app does not
include a global floating chat; agent runs instead show their process **inline
in the chat column**. Docs that describe the floating assistant are marked as
historical.

### Can I extend the UI with panels?

The right-hand panel is plugin-based (built-in and third-party panels are
listed in Settings > Plugins). Developers: see the
[Addon API](gguf-loader-addon-api.md) and
[Creating Addons](creating-addons-in-gguf-loader.md) guides.

---

## Troubleshooting

### The model never loads - the header chip says "No model"

The pinned GGUF is not in a folder the app scans. Click the chip to download
it, or place `gemma-4-12B-it-Q4_K_M.gguf` into the `models/` folder and
restart. Verify the filename matches exactly (the app only loads that file).

### Responses are slow

Enable GPU in **Settings > Hardware** and restart; close other RAM-heavy
applications; keep the context/generation settings at their defaults.

### The app won't start (from source)

Check the launcher's error: you need **Python 3.10+**, `python3-venv` on
Debian/Ubuntu, and a working network for first-time dependency installs. Delete
the `.venv` / `frontend/node_modules` folders and re-run the launcher to start
clean.

### Where can I get help?

- [GitHub Issues](https://github.com/GGUFloader/gguf-loader/issues) - bug
  reports
- [GitHub Discussions](https://github.com/GGUFloader/gguf-loader/discussions) -
  questions and ideas
- The [User Guide](user-guide.md) and [Quick Reference](../QUICK_REFERENCE.md)
