#!/usr/bin/env python3
"""Capture screenshots of the React UI for documentation.

Prerequisites:
    pip install playwright
    playwright install chromium

Usage:
    1. Start the app: launch.bat (or python -m uvicorn ggufloader.api.app:create_app --factory --port 8000)
    2. Run this script: python scripts/capture_react_screenshots.py
    3. Screenshots are saved to the project root.
"""
import time
import sys

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Install playwright first: pip install playwright && playwright install chromium")
    sys.exit(1)

URL = "http://localhost:8000"
ROOT = __file__.rsplit("/", 2)[0] if "/" in __file__ else "."


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        # Desktop viewport (wide enough for 3-panel layout)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        # 1. Welcome screen
        page.goto(URL)
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        page.screenshot(path=f"{ROOT}/screen.png")
        print(f"Saved {ROOT}/screen.png")

        # 2. Type a message and wait for response
        page.fill('textarea, [contenteditable], input[type="text"]', "What is GGUF Loader?")
        page.press('textarea, [contenteditable], input[type="text"]', "Enter")
        time.sleep(15)  # Wait for agent to finish
        page.screenshot(path=f"{ROOT}/screen_chat.png")
        print(f"Saved {ROOT}/screen_chat.png")

        browser.close()
        print("Done! Review the screenshots and pick the best one for README.md")


if __name__ == "__main__":
    main()
