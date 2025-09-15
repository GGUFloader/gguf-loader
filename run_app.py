#!/usr/bin/env python3
"""
Simple launcher script for GGUF Loader
"""
import sys
import os

# Ensure current directory is in Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

if __name__ == "__main__":
    from gguf_loader_main import main
    main()