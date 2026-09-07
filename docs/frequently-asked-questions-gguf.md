# Frequently Asked Questions (FAQ) About GGUF Loader

This FAQ answers common questions about GGUF Loader and how to get the best
experience with the current build.

## What is GGUF Loader?

GGUF Loader is a privacy-first desktop app that runs **one large language
model fully locally** - Google **Gemma 4 12B Instruct (Q4_K_M)**. It pairs a
streaming chat with an **agent mode** that plans and executes multi-step file
tasks (reading, searching, writing, editing, running commands, git) inside a
workspace folder you choose. Nothing leaves your computer.

## Which model do I need?

The app is pinned to the Gemma 4 12B Instruct **Q4_K_M** GGUF
(`gemma-4-12B-it-Q4_K_M.gguf`, roughly 8 GB). Other GGUF files are rejected at
load time - this build is deliberately tuned for that one model.

## How do I load the model?

You usually do not need to do anything. The app **auto-loads** the pinned
model on startup by scanning its `models/` folder (plus the folder you last
used). If the file is not on disk, the **model chip in the header** downloads
it with live progress and loads it when done.

## Can I chat and ask the agent to do things?

Yes. Plain chat answers questions directly. Switch to **Agent Mode**
(Ctrl/Cmd + Shift + A) to give the agent a workspace folder - it will plan the
task, run the steps with sandboxed tools, and show the whole process inline
before giving you a clean final answer. Commands, code execution, and git
writes ask for your **Allow/Deny** approval first.

## How much RAM do I need?

About 8-10 GB of free RAM for the 12B model to run smoothly. GPU acceleration
(NVIDIA CUDA or Apple Metal) is optional and available under Settings >
Hardware.

## Can I extend GGUF Loader with addons?

The right-hand panel is plugin-based. Developers can extend it - see the
[Addon API](gguf-loader-addon-api.md) and
[Creating Addons](creating-addons-in-gguf-loader.md) guides.

## Where can I get help or report issues?

Open an issue or discussion on the [GGUF Loader GitHub repository](https://github.com/GGUFloader/gguf-loader), or read the full [FAQ](faq.md) and [User Guide](user-guide.md).
