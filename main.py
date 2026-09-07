#!/usr/bin/env python3
"""GGUF Loader - development launcher shim.

The real entry point lives at ``ggufloader/main.py``; this file only exists
so the repo can keep the familiar ``python main.py`` dev workflow (and the
PyInstaller spec entry). It is NOT shipped in the pip wheel.
"""

import os
import sys

# In a windowed (console=False) PyInstaller exe launched by double-click,
# sys.stdout and sys.stderr are both None. This must happen BEFORE any
# other import: logging.basicConfig() calls sys.stderr.isatty(), uvicorn's
# log formatter calls sys.stdout.isatty(), and plain print() writes to
# sys.stdout - all crash on a None stream (the app would appear to "do
# nothing" when double-clicked). Route both to devnull.
if getattr(sys, 'frozen', False):
    for _stream in ('stdout', 'stderr'):
        if getattr(sys, _stream, None) is None:
            setattr(sys, _stream, open(os.devnull, 'w', encoding='utf-8'))

from ggufloader.main import run

if __name__ == "__main__":
    # run() wraps main() so a fatal startup error becomes a visible dialog
    # instead of a silent exit in the windowed (console-less) frozen exe.
    sys.exit(run())
