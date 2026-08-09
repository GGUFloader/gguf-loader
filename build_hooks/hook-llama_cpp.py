"""
PyInstaller hook for llama_cpp package
Ensures all DLLs and library files are included (CPU-only, excludes CUDA)
"""
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs
import os

# Collect all llama_cpp files
datas, binaries, hiddenimports = collect_all('llama_cpp')

# Explicitly collect dynamic libraries
binaries += collect_dynamic_libs('llama_cpp')

# collect_all/collect_dynamic_libs pull EVERYTHING including the ~900MB CUDA
# runtime. This bundle is CPU-only, so drop any CUDA entry (binary or data).
# Match both 'cuda' and 'cublas' - the cublas runtime dlls don't say 'cuda'.
def _cuda_entry(entry):
    # Entries are (source_path, dest, [type]) tuples - the source path is the
    # first element; check both leading elements to stay shape-agnostic.
    return any(('cuda' in str(part).lower() or 'cublas' in str(part).lower())
               for part in entry[:2])

binaries = [b for b in binaries if not _cuda_entry(b)]
datas = [d for d in datas if not _cuda_entry(d)]
print(f"[Hook] CUDA-filtered: {len(binaries)} binaries, {len(datas)} datas")

# Add the lib directory explicitly (CPU-only, exclude CUDA)
try:
    import llama_cpp
    llama_cpp_dir = os.path.dirname(llama_cpp.__file__)
    lib_dir = os.path.join(llama_cpp_dir, 'lib')
    
    if os.path.exists(lib_dir):
        # Add only CPU files, skip CUDA to reduce size
        for file in os.listdir(lib_dir):
            # Skip CUDA files (they're huge - 400-500MB). Match 'cublas' too.
            if 'cuda' in file.lower() or 'cublas' in file.lower():
                print(f"[Hook] Skipped CUDA file (size reduction): {file}")
                continue
                
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
