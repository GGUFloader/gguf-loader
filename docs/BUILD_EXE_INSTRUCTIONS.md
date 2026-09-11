# Building GGUF Loader Executable (Historical)

> **📜 Historical document** — describes the build process from an earlier version.
> The current build (v2.3.0) uses `scripts/build_exe.bat` and
> `build_exe.spec`. See [AGENTS.md](../AGENTS.md) for current build commands.

This guide explains how to create a standalone Windows executable (.exe) for the GGUF Loader application.

## Prerequisites

1. **Python 3.10+** installed on your system
2. **Virtual environment** with all dependencies installed
3. **PyInstaller** (will be installed automatically by the build script)

## Build Structure

The build system uses PyInstaller hooks located in the `build_hooks/` folder:
- `hook-*.py` - Module collection hooks for each package
- `runtime_hook_llama.py` - Runtime DLL path setup for llama.cpp

## Quick Start

### Option 1: Using the Build Script (Recommended)

Simply run the provided batch file:

```cmd
scripts/build_exe.bat
```

This will:
- Activate your virtual environment
- Install PyInstaller
- Clean previous builds
- Build the executable
- Show you where the final .exe is located

### Option 2: Manual Build

If you prefer to build manually:

1. **Activate your virtual environment:**
   ```cmd
   venv\Scripts\activate
   ```

2. **Install PyInstaller:**
   ```cmd
   pip install pyinstaller
   ```

3. **Build the executable:**
   ```cmd
   pyinstaller build_exe.spec
   ```

## Output Location

After a successful build, you'll find a **single self-contained file**:

```
dist/
└── GGUFLoader_WithAddons.exe   <- Your executable (Windows)
dist/
└── GGUFLoader_WithAddons       <- Your executable (Linux, no extension)
```

> Onefile binaries are **not cross-platform**: a Windows `.exe` must be built on
> Windows, and a Linux binary must be built on Linux. See below for the
> automated approach.

## Building on Linux

The same spec file works on Linux (the Windows-only flags are ignored there):

```bash
scripts/build_linux.sh
```

The output is `dist/GGUFLoader_WithAddons`. Rename it before publishing, e.g.:

```bash
mv dist/GGUFLoader_WithAddons dist/GGUFLoader_Linux_x86_64
```

## Automated Releases (Windows + Linux via GitHub Actions)

PyInstaller cannot cross-compile, so the easiest way to ship both installers is
the included workflow (`.github/workflows/build-release.yml`):

1. Bump the version in `__init__.py` and `CHANGELOG.md`
2. Commit and push:
   ```bash
   git add -A && git commit -m "Release v2.1.2"
   git push origin main
   git tag v2.1.2 && git push origin v2.1.2
   ```
3. The workflow builds `GGUFLoader_v2.1.2_win64.exe` (windows-latest) and
   `GGUFLoader_v2.1.2_linux_x86_64` (ubuntu-latest) and attaches both to a
   new GitHub Release with auto-generated notes.

You can also run the workflow manually from the **Actions** tab (it will just
upload artifacts, not create a release).

## Distribution

To distribute your application:

1. **Zip the entire folder:** `dist/GGUFLoader/`
2. **Share the zip file** with users
3. Users simply extract and run `GGUFLoader.exe`

## Customization

### Change Application Name

Edit `build_exe.spec` and modify the `name` parameter:

```python
exe = EXE(
    ...
    name='YourAppName',  # Change this
    ...
)
```

### Include Additional Files

Add files to the `datas` list in `build_exe.spec`:

```python
datas = [
    ('icon.ico', '.'),
    ('your_file.txt', '.'),  # Add your files here
    ('your_folder', 'your_folder'),
]
```

### Show Console Window (for debugging)

Change `console=False` to `console=True` in `build_exe.spec`:

```python
exe = EXE(
    ...
    console=True,  # Shows console for debugging
    ...
)
```

## Troubleshooting

### Build Fails with Import Errors

Add missing modules to `hiddenimports` in `build_exe.spec`:

```python
hiddenimports = [
    'your_missing_module',
]
```

### Executable is Too Large

1. Remove unused dependencies from `requirements.txt`
2. Use `upx=True` in the spec file (already enabled)
3. Build CPU-only if GPU is not needed (drops ~800 MB)

### Missing DLL Errors

If users report missing DLL errors:

1. Install Visual C++ Redistributable
2. Add DLLs to `binaries` in `build_exe.spec`:

```python
binaries = [
    ('path/to/your.dll', '.'),
]
```

### Icon Not Showing

Ensure `icon.ico` exists in the root directory and is a valid .ico file.

## Advanced: One-File Executable

To create a single .exe file (slower startup but easier distribution):

Edit `build_exe.spec` and change:

```python
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,      # Add these
    a.zipfiles,      # Add these
    a.datas,         # Add these
    [],
    name='GGUFLoader',
    ...
)

# Remove or comment out the COLLECT section
```

Then rebuild with `pyinstaller build_exe.spec`

## Testing the Executable

Before distribution:

1. **Test on a clean Windows machine** (without Python installed)
2. **Check all features work** (model loading, addons, UI)
3. **Verify icon displays correctly**
4. **Test with different Windows versions** (if possible)

## File Size Optimization

Typical executable size: 145-930 MB (CPU build ~145 MB, GPU build ~930 MB with CUDA runtime)

To reduce size:
- Use lighter AI model libraries
- Exclude documentation from build
- Use CPU-only llama-cpp-python (no CUDA runtime)

## Support

If you encounter issues:
1. Check the console output for error messages
2. Try building with `console=True` for debugging
3. Verify all dependencies are installed in your venv
4. Check PyInstaller documentation: https://pyinstaller.org

## Notes

- The executable includes all Python dependencies
- Users don't need Python installed
- First run may be slower (unpacking)
- Antivirus software may flag the .exe (false positive)
- Consider code signing for production distribution
