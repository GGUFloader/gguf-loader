"""
Simple Smart Floating Assistant

Shows a button when you select text, processes it with AI. That's it.
"""

# Use the simple version instead of the complex one
import sys
import os
addon_dir = os.path.dirname(os.path.abspath(__file__))
if addon_dir not in sys.path:
    sys.path.insert(0, addon_dir)

from simple_main import register

__all__ = ["register"]