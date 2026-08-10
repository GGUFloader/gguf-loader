#!/usr/bin/env python3
"""
Capture screenshots of the current GGUF Loader UI.

Renders the real widgets (not mockups), so the images always reflect the
actual theme, bubbles, and layout. IMPORTANT: run WITHOUT
QT_QPA_PLATFORM=offscreen - the offscreen platform renders a sparse,
near-blank window (text/bubbles don't paint), so captures must happen on a
real display. Writes:

  screen.png                     - main window, light theme (tracked, README - the app default)
  ui_preview_light.png           - main window, light theme (local preview)
  ui_preview_dark.png            - main window, dark theme  (local preview)
  ui_preview_floating_dark.png   - floating chat, dark      (local preview)
  ui_preview_floating_light.png  - floating chat, light     (local preview)
  _bubble_dark.png / _bubble_light.png - bubble close-ups   (local preview)

Usage:
    python scripts/capture_screenshots.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget  # noqa: E402

from ggufloader.ui.theme import DARK_TOKENS, LIGHT_TOKENS  # noqa: E402

SAMPLE_USER = "What local models work best for writing Python code?"
SAMPLE_AI = (
    "For local code generation, Mistral-7B-Instruct and LLaMA 3 8B are great "
    "starting points. Load any GGUF file from the sidebar, then enable Agent "
    "Mode so the model can read, edit, and organize files in your workspace."
)


def pump(msec: int = 500) -> None:
    """Run the event loop briefly so layout, fonts, and threads settle."""
    for _ in range(30):
        QApplication.processEvents()
    loop = QEventLoop()
    QTimer.singleShot(msec, loop.quit)
    loop.exec()


def populate_main_window(window) -> None:
    """Fill the main chat with a realistic conversation + loaded-model state."""
    p = window.chat_panel
    p.add_system_message("🤖 AI Assistant loaded and ready to help!")
    p.add_user_message(SAMPLE_USER)
    p.add_ai_message(SAMPLE_AI)
    p.add_user_message("Can it use my project files?")
    p.add_ai_message(
        "Yes! Turn on Agent Mode and pick a workspace folder. The agent can "
        "read files, search the codebase, write new modules, and organize "
        "directories - all with your privacy intact."
    )
    window._set_model_chip("ok", "● mistral-7b-instruct-v0.1.Q4_K_M.gguf")
    window.sidebar.set_model_info("✅ Loaded: mistral-7b-instruct-v0.1.Q4_K_M.gguf")
    window.sidebar.set_status("Model ready! Start chatting...")


def populate_floating_chat(chat) -> None:
    """Fill the floating chat window with the same sample conversation."""
    chat.set_model_status(True)
    chat._add_system_message("🤖 AI Assistant loaded and ready to help!")
    chat._add_user_message(SAMPLE_USER)
    chat._create_streaming_ai_message()
    chat._on_token_received(SAMPLE_AI)


def bubble_stage(is_dark: bool) -> QWidget:
    """A small themed stage holding one user + one assistant bubble."""
    tokens = DARK_TOKENS if is_dark else LIGHT_TOKENS
    stage = QWidget()
    stage.setObjectName("bubbleStage")
    stage.resize(540, 320)
    stage.setStyleSheet(
        f"QWidget#bubbleStage {{ background-color: {tokens['bg']}; }}"
    )

    from ggufloader.widgets.chat_bubble import ChatBubble
    layout = QVBoxLayout(stage)
    layout.setContentsMargins(24, 24, 24, 24)
    layout.setSpacing(14)
    user = ChatBubble(SAMPLE_USER, is_user=True)
    ai = ChatBubble(SAMPLE_AI, is_user=False)
    user.update_style(is_dark)
    ai.update_style(is_dark)
    layout.addWidget(user)
    layout.addWidget(ai)
    layout.addStretch(1)
    stage.show()
    pump(350)
    return stage


def hd_grab(widget) -> "QPixmap":
    """Crisp 2x capture: paint the widget into a device-pixel-ratio-2 pixmap.

    ``widget.grab()`` rasterizes at 1x logical pixels, which looks soft when
    browsers upscale it. Rendering into a 2x-DPR pixmap doubles the output
    resolution (e.g. 1440x900 window -> 2880x1800 image) for sharp text.
    """
    from PySide6.QtGui import QPixmap
    size = widget.size()
    pm = QPixmap(size.width() * 2, size.height() * 2)
    pm.setDevicePixelRatio(2.0)
    widget.render(pm)
    return pm


def save(pixmap, name: str) -> None:
    target = ROOT / name
    ok = pixmap.save(str(target))
    print(f"  {'OK ' if ok else 'FAIL'} {name}  ({pixmap.width()}x{pixmap.height()})")


def main() -> int:
    app = QApplication(sys.argv)

    from ggufloader.ui.main_window import MainWindow

    print("Rendering main window (light - the app default)...")
    window = MainWindow()
    window.resize(1440, 900)  # a bit wider than default for the hero screenshot
    window.show()
    pump(800)
    populate_main_window(window)
    pump(700)

    # screen.png is the README/site hero image - capture it at 2x (HD).
    save(hd_grab(window), "screen.png")
    save(window.grab(), "ui_preview_light.png")

    # ---- dark theme ----
    print("Rendering main window (dark)...")
    window._on_dark_mode_toggled(True)
    pump(500)
    save(window.grab(), "ui_preview_dark.png")

    # ---- floating chat (starts light; the addon follows the main theme) ----
    addon = window._floating_chat_addon
    if addon is not None:
        print("Rendering floating chat...")
        addon._show_chat_window()
        chat = addon._chat_window
        pump(400)
        populate_floating_chat(chat)
        pump(500)
        save(chat.grab(), "ui_preview_floating_light.png")

        window._on_dark_mode_toggled(True)
        pump(500)
        save(chat.grab(), "ui_preview_floating_dark.png")
    else:
        print("  (floating chat addon not loaded - skipping)")

    # ---- bubble close-ups ----
    print("Rendering bubble close-ups...")
    stage_light = bubble_stage(is_dark=False)
    save(stage_light.grab(), "_bubble_light.png")
    stage_light.close()

    stage_dark = bubble_stage(is_dark=True)
    save(stage_dark.grab(), "_bubble_dark.png")
    stage_dark.close()

    window.close()
    pump(300)
    app.processEvents()
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
