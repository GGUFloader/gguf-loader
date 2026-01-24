"""Test GPU inference to verify model is using GPU"""
import sys
import time

try:
    from llama_cpp import Llama
    print("✓ llama-cpp-python imported successfully\n")
except ImportError as e:
    print(f"✗ Failed to import llama-cpp-python: {e}")
    sys.exit(1)

# Ask for model path
model_path = input("Enter path to your GGUF model file: ").strip()

if not model_path:
    print("No model path provided")
    sys.exit(1)

print("\n" + "="*60)
print("Loading model with GPU acceleration...")
print("="*60 + "\n")

try:
    # Load with GPU
    start_time = time.time()
    llm = Llama(
        model_path=model_path,
        n_ctx=2048,
        n_gpu_layers=35,  # Offload 35 layers to GPU
        verbose=True  # This will show GPU usage info
    )
    load_time = time.time() - start_time
    
    print(f"\n✓ Model loaded in {load_time:.2f} seconds")
    print("\nIf you see 'CUDA' or 'GPU' messages above, GPU is being used!")
    
    # Test inference
    print("\n" + "="*60)
    print("Testing inference...")
    print("="*60 + "\n")
    
    prompt = "Hello, how are you?"
    print(f"Prompt: {prompt}\n")
    print("Response: ", end="", flush=True)
    
    start_time = time.time()
    token_count = 0
    
    for output in llm(prompt, max_tokens=50, stream=True):
        token = output['choices'][0]['text']
        print(token, end="", flush=True)
        token_count += 1
    
    inference_time = time.time() - start_time
    tokens_per_sec = token_count / inference_time if inference_time > 0 else 0
    
    print(f"\n\n✓ Generated {token_count} tokens in {inference_time:.2f} seconds")
    print(f"✓ Speed: {tokens_per_sec:.2f} tokens/second")
    
    if tokens_per_sec > 20:
        print("\n🚀 GPU acceleration is working! (Fast speed)")
    elif tokens_per_sec > 5:
        print("\n⚠ Speed is moderate - GPU may be partially used")
    else:
        print("\n⚠ Speed is slow - GPU may not be working properly")
    
except Exception as e:
    print(f"\n✗ Error: {e}")
    sys.exit(1)

print("\n" + "="*60)
print("Test complete!")
print("="*60)
