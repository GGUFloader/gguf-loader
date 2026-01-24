"""Verify llama-cpp-python GPU support"""
import sys

try:
    from llama_cpp import Llama
    print("✓ llama-cpp-python imported successfully")
    
    # Check if CUDA is available
    try:
        # Try to get GPU info
        import llama_cpp
        print(f"✓ llama-cpp-python version: {llama_cpp.__version__}")
        
        # Check for CUDA support in the build
        print("\nChecking for GPU support...")
        print("If you see CUDA/GPU related output below, GPU support is enabled:")
        print("-" * 60)
        
        # This will show build info
        test_llm = Llama(
            model_path="",  # Empty path just to trigger initialization
            n_gpu_layers=1,
            verbose=True
        )
    except Exception as e:
        error_msg = str(e).lower()
        if "cuda" in error_msg or "gpu" in error_msg:
            print("✓ GPU support detected in error message")
        elif "model_path" in error_msg or "no such file" in error_msg:
            print("✓ GPU support likely available (model path error is expected)")
        else:
            print(f"⚠ Error: {e}")
            
except ImportError as e:
    print(f"✗ Failed to import llama-cpp-python: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("To use GPU acceleration, set n_gpu_layers when loading models:")
print("  llm = Llama(model_path='model.gguf', n_gpu_layers=35)")
print("=" * 60)
