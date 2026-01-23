"""
PyInstaller hook for llama_cpp package
Ensures all DLLs and library files are included
"""
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs
import os

# Collect all llama_cpp files
datas, binaries, hiddenimports = collect_all('llama_cpp')

# Explicitly collect dynamic libraries
binaries += collect_dynamic_libs('llama_cpp')

# Add the lib directory explicitly
try:
    import llama_cpp
    llama_cpp_dir = os.path.dirname(llama_cpp.__file__)
    lib_dir = os.path.join(llama_cpp_dir, 'lib')
    
    if os.path.exists(lib_dir):
        # Add all files from lib directory
        for file in os.listdir(lib_dir):
            file_path = os.path.join(lib_dir, file)
            if os.path.isfile(file_path):
                datas.append((file_path, 'llama_cpp/lib'))
                print(f"[Hook] Added llama_cpp file: {file}")
except Exception as e:
    print(f"[Hook] Warning: Could not collect llama_cpp lib files: {e}")

# Ensure all submodules are imported
hiddenimports += [
    'llama_cpp.llama',
    'llama_cpp.llama_cpp',
    'llama_cpp._ctypes_extensions',
]
