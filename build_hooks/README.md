# PyInstaller Build Hooks

This folder contains PyInstaller hooks used when building the GGUF Loader executable.

## What Are These Files?

PyInstaller hooks tell the build system how to properly package Python modules and their dependencies into a standalone executable.

## Hook Files

### Module Collection Hooks
These hooks ensure all necessary files from each package are included:

- **hook-core.py** - Collects the `core/` package (LLM backend + agent engine)
- **hook-llama_cpp.py** - Collects llama.cpp library and DLL files (critical for AI functionality)

The legacy PySide6 hooks (hook-PySide6.py, hook-ui.py, hook-widgets.py,
hook-services.py, hook-addons.py) were removed: the desktop UI is the
React app running in Electron, so no Qt code ships in the installer.
`build_exe.spec` excludes PySide6 and the Qt-era `ggufloader` packages
(ui/widgets/services/addons) outright.

### Runtime Hook
- **runtime_hook_llama.py** - Sets up DLL search paths when the executable runs

## How They're Used

The `build_exe.spec` file references this folder:

```python
hookspath=[os.path.join(current_dir, 'build_hooks')],
runtime_hooks=[os.path.join(current_dir, 'build_hooks', 'runtime_hook_llama.py')],
```

## When Are They Needed?

- **Building executables**: Required when running `scripts/build_exe.bat` or `pyinstaller build_exe.spec`
- **Running from source**: Not used during normal Python execution (`python main.py`)

## Modifying Hooks

If you add new packages or need to include additional files in the executable:

1. Create a new hook file: `hook-yourpackage.py`
2. Use the template:
```python
"""
PyInstaller hook for yourpackage
"""
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = collect_all('yourpackage')
```

3. The hook will be automatically discovered by PyInstaller

## Documentation

For more information about PyInstaller hooks:
- [PyInstaller Hook Documentation](https://pyinstaller.org/en/stable/hooks.html)
- [Writing Hooks](https://pyinstaller.org/en/stable/hooks.html#writing-hooks)
