"""Single source of truth for the GGUF Loader version.

Kept in its own module so ``ggufloader/__init__.py`` and the entry point can
import it without pulling in PySide6 or the rest of the app (no import cycles).
"""

__version__ = "2.3.0"
