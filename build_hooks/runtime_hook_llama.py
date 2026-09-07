"""
Runtime hook for llama_cpp to set up DLL paths correctly in frozen application
"""
import os
import sys


def _log(msg: str) -> None:
    """Print safely: in a windowed frozen app sys.stdout/sys.stderr are None,
    and a bare print() would crash the process before main.py even runs."""
    stream = sys.stderr if sys.stderr is not None else sys.stdout
    if stream is None:
        return
    try:
        print(msg, file=stream)
    except Exception:  # noqa: BLE001 - logging must never crash startup
        pass


# When frozen by PyInstaller, set up the DLL path
if getattr(sys, 'frozen', False):
    # We're running in a PyInstaller bundle
    bundle_dir = sys._MEIPASS

    # Add llama_cpp/lib to DLL search path
    llama_lib_path = os.path.join(bundle_dir, 'llama_cpp', 'lib')

    if os.path.exists(llama_lib_path):
        # Add to DLL directory for Windows
        if hasattr(os, 'add_dll_directory'):
            try:
                os.add_dll_directory(llama_lib_path)
                _log(f"[Runtime Hook] Added DLL directory: {llama_lib_path}")
            except Exception as e:
                _log(f"[Runtime Hook] Failed to add DLL directory: {e}")

        # Also add to PATH as fallback
        os.environ['PATH'] = llama_lib_path + os.pathsep + os.environ.get('PATH', '')
        _log(f"[Runtime Hook] Added to PATH: {llama_lib_path}")
    else:
        _log(f"[Runtime Hook] Warning: llama_cpp/lib not found at {llama_lib_path}")
