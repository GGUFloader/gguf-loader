block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['C:\\Users\\MY-PC\\Desktop\\locald'],  # Set your project root here
    binaries=[],
    datas=[
        ('C:\\Users\\MY-PC\\Desktop\\locald\\.venv\\Lib\\site-packages\\llama_cpp\\lib', 'llama_cpp\\lib'),
        ('icon.ico', '.'),  # Make sure your icon file is named icon.ico here
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
    cipher=block_cipher
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='LLM-Loader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',  # matches the datas above
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='LLM-Loader'
)
