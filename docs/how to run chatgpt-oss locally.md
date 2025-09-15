# Running ChatGPT-OSS Locally: Complete Setup Guide

## Overview

**GPT-OSS** is OpenAI's first open-weight model release under the Apache 2.0 license. This guide covers how to run these models locally on your hardware.

### Available Models

- **GPT-OSS-20B**: ~21B parameters, activates ~3.6B per token
- **GPT-OSS-120B**: ~117B parameters, activates ~5.1B per token

Both models use mixture-of-experts (MoE) architecture with long-context support up to 128K tokens.

## Prerequisites

### Understanding GGUF Format

**GGUF** (Generic GPT Unified Format) is a quantized model format optimized for efficient loading and inference on consumer hardware. It enables running large language models on standard CPUs and GPUs with reduced memory requirements.

### Hardware Requirements

| Model | Memory Required | Recommended Hardware | Performance |
|-------|----------------|---------------------|-------------|
| GPT-OSS-20B | ~16 GB | RTX 3090, RTX 4080, RX 9070 XT | ~6 tokens/sec |
| GPT-OSS-120B | ~60-80 GB | A100 80GB, H100 80GB, Multi-GPU setup | ~30-45 tokens/sec |

#### Additional Options
- **Apple Silicon**: M1/M2 Macs with Metal acceleration (via LM Studio)
- **CPU-only**: Functional but extremely slow (multi-second per token)
- **Consumer AI**: AMD Ryzen AI Max+ 395 (128 GB unified memory)

## Installation Methods

### Method 1: GGUF Loader (Recommended for Beginners)

GGUF Loader is a lightweight, cross-platform GUI application that simplifies model loading and interaction.

#### Features
- Simple file browser interface for selecting `.gguf` files
- No Python or CLI knowledge required
- Built-in floating assistant overlay
- Cross-platform support (Windows/macOS/Linux)

#### Setup Steps

1. **Download GGUF Loader**
   - Get version 2.0.1 or later from the official repository

2. **Download Model Files**
   - **GPT-OSS-20B (Dense)**: [Download Q4_K (7.34 GB)](https://huggingface.co/lmstudio-community/gpt-oss-20b-GGUF/resolve/main/gpt-oss-20b-MXFP4.gguf)
   - **GPT-OSS-120B (Dense)**: [Download Q4_K (46.2 GB)](https://huggingface.co/lmstudio-community/gpt-oss-120b-GGUF/resolve/main/gpt-oss-120b-MXFP4-00001-of-00002.gguf)

3. **Launch and Load**
   - Open GGUF Loader
   - Click the navigation/browse button to select your downloaded `.gguf` file from your directory
   - Click **Start**
   - Use the floating assistant for offline interactions

### Method 2: llama.cpp (Advanced Users)

For users who need more control over inference parameters and GPU offloading.

#### Build llama.cpp

```bash
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp
cmake -B build -DGGML_CUDA=ON -DLLAMA_CURL=ON
cmake --build build --target llama-cli -j
```

#### Download Models

**Option 1: Direct Download**
- **GPT-OSS-20B**: [Download Q4_K (7.34 GB)](https://huggingface.co/lmstudio-community/gpt-oss-20b-GGUF/resolve/main/gpt-oss-20b-MXFP4.gguf)
- **GPT-OSS-120B**: [Download Q4_K (46.2 GB)](https://huggingface.co/lmstudio-community/gpt-oss-120b-GGUF/resolve/main/gpt-oss-120b-MXFP4-00001-of-00002.gguf)

**Option 2: Using Hugging Face Hub**
```python
from huggingface_hub import snapshot_download
# For 20B model
snapshot_download("lmstudio-community/gpt-oss-20b-GGUF", allow_patterns=["*MXFP4*"])
# For 120B model  
snapshot_download("lmstudio-community/gpt-oss-120b-GGUF", allow_patterns=["*MXFP4*"])
```

#### Run Inference

**For GPT-OSS-20B:**
```bash
./llama-cli -m gpt-oss-20b-MXFP4.gguf \
  --ctx-size 16384 --threads -1 --temp 1.0 --top-p 1.0 --top-k 0
```

**For GPT-OSS-120B (with GPU offload):**
```bash
./llama-cli -m gpt-oss-120b-MXFP4-00001-of-00002.gguf \
  --threads -1 --ctx-size 16384 --n-gpu-layers 99 \
  --temp 1.0 --top-p 1.0 --top-k 0
```

*Note: Adjust `--n-gpu-layers` if your GPU runs out of memory*

## Configuration

### Recommended Inference Settings

```
temperature: 1.0
top_p: 1.0
top_k: 0
context_length: 16,384 (up to 131,072)
reasoning_effort: low/medium/high
```

**Performance Notes:**
- Lower reasoning effort increases response speed
- Medium to high reasoning effort improves chain-of-thought quality
- Context length can be extended up to 131,072 tokens for long documents

## Technical Architecture

### GPT-OSS-20B Specifications
- **Parameters**: ~21B total, ~3.6B active per token
- **Architecture**: 32 total experts, 4 active per layer, 24 layers
- **Memory**: ~16 GB required

### GPT-OSS-120B Specifications
- **Parameters**: ~117B total, ~5.1B active per token
- **Architecture**: 128 experts per layer, 4 active, 36 layers
- **Memory**: ~60-80 GB required

The mixture-of-experts architecture enables efficient inference by activating only a subset of parameters for each token, maintaining high performance while reducing computational requirements.

## Troubleshooting

### Common Issues

1. **Out of Memory Errors**
   - Reduce `--n-gpu-layers` parameter
   - Use CPU offloading for some layers
   - Consider using a smaller model variant

2. **Slow Performance**
   - Ensure GPU acceleration is enabled
   - Check CUDA installation for NVIDIA GPUs
   - Verify sufficient VRAM availability

3. **Model Loading Failures**
   - Verify file integrity after download
   - Check available disk space
   - Ensure compatible GGUF Loader version

## Use Cases and Applications

### Development and Testing
- Local AI assistant for coding tasks
- Prototype development without API dependencies
- Privacy-focused applications requiring offline inference

### Research and Education
- Model architecture experimentation
- Performance benchmarking across hardware configurations
- Educational demonstrations of large language models

### Production Deployment
- On-premises AI solutions
- Edge computing applications
- Custom fine-tuning and specialization

## Next Steps

1. **Local Demo Setup**
   - Test the model with sample prompts
   - Capture performance benchmarks for your hardware
   - Document optimal settings for your use case

2. **Integration Options**
   - Embed in applications via API endpoints
   - Create custom interfaces using the model
   - Develop automated workflows

3. **Community Engagement**
   - Share benchmarks and optimizations
   - Contribute to model fine-tuning efforts
   - Participate in open-source development

## Summary

GPT-OSS provides powerful open-source language models suitable for various hardware configurations. The 20B model offers excellent performance for consumer setups, while the 120B model delivers enterprise-grade capabilities for high-end hardware. Choose GGUF Loader for simplicity or llama.cpp for advanced control over inference parameters.

## Additional Resources

- **Official Documentation**: OpenAI GPT-OSS documentation
- **Community Forums**: Discussion and troubleshooting support
- **Model Repositories**: Hugging Face model downloads
- **Performance Benchmarks**: Community-contributed performance data