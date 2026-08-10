"""
GGUF Loader - Advanced GGUF Model Loader with Smart Floating Assistant

Everything ships under this one package (``ggufloader``), so a
``pip install ggufloader`` claims a single top-level name in site-packages.
The app's own modules (``config``, ``utils``, ``ui``, ``core``, ``services``,
``widgets``, ``addons``) live *inside* this package and are imported as
``ggufloader.xxx`` - they can never collide with another package's top-level
modules in a shared/global environment.
"""

from ._version import __version__  # noqa: F401

__author__ = "Hussain Nazary"
__email__ = "hussainnazary475@gmail.com"
__description__ = "Advanced GGUF Model Loader with Smart Floating Assistant"
__url__ = "https://github.com/GGUFloader/gguf-loader"

# Public API re-exports for code written against the older nested layout.
# Kept at the bottom so `__version__` is set before any heavy module loads.
from .main import main  # noqa: E402,F401
from .addon_manager import AddonManager  # noqa: E402,F401
from .config import ensure_directories  # noqa: E402,F401

__all__ = [
    "__version__",
    "__author__",
    "__description__",
    "main",
    "AddonManager",
    "ensure_directories",
]
