# Building GGUF Loader Executable

This guide explains how to create a standalone Windows executable (.exe) for the GGUF Loader application.

## Prerequisites

1. **Python 3.8+** installed on your system
2. **Virtual environment** with all dependencies installed
3. **PyInstaller** (will be installed automatically by the build script)

## Quick Start

### Option 1: Using the Build Script (Recommended)

Simply run the provided batch file:

```cmd
build_exe.bat
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

After a successful build, you'll find:

```
dist/
└── GGUFLoader/
    ├── GGUFLoader.exe    <- Your executable
    ├── icon.ico
    ├── addons/           <- Addon system
    ├── docs/             <- Documentation
    └── [other dependencies]
```

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
3. Consider using `--onefile` mode (creates single .exe but slower startup)

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

Typical executable size: 100-300 MB (includes PySide6 and llama-cpp-python)

To reduce size:
- Remove unused Qt modules
- Use lighter AI model libraries
- Exclude documentation from build

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
