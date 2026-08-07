"""
GGUF Loader - Advanced GGUF Model Loader with Smart Floating Assistant

A production-ready Python package that provides a robust GGUF model loader
application with the Smart Floating Assistant addon pre-installed.
"""

__version__ = "2.1.2"
__author__ = "Hussain Nazary"
__email__ = "hussainnazary475@gmail.com"
__description__ = "Advanced GGUF Model Loader with Smart Floating Assistant"
__url__ = "https://github.com/GGUFloader/gguf-loader"

# Import main function for programmatic access
from main import main

# Import key classes for programmatic integration
from addon_manager import AddonManager

# Import configuration utilities
from config import ensure_directories

__all__ = [
    "__version__",
    "__author__",
    "__description__",
    "main",
    "AddonManager",
    "ensure_directories",
]
