#!/usr/bin/env python3
"""GGUF Loader - development launcher shim.

The real entry point lives at ``ggufloader/main.py``; this file only exists
so the repo can keep the familiar ``python main.py`` dev workflow (and the
PyInstaller spec entry). It is NOT shipped in the pip wheel.
"""

import sys

from ggufloader.main import main

if __name__ == "__main__":
    sys.exit(main())
