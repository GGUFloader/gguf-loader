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
from .config import ensure_directories  # noqa: E402,F401

__all__ = [
    "__version__",
    "__author__",
    "__description__",
    "main",
    "AddonManager",
    "ensure_directories",
]


def __getattr__(name: str):
    """Lazily resolve legacy re-exports.

    ``AddonManager`` belongs to the legacy PySide6 UI layer. It is resolved
    on demand (PEP 562) so importing the ``ggufloader`` package - and with
    it the FastAPI backend, the PyInstaller bundle, and the pip wheel -
    never requires PySide6 to be installed. Only code that actually touches
    the Qt UI imports it.
    """
    if name == "AddonManager":
        from .addon_manager import AddonManager
        return AddonManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
