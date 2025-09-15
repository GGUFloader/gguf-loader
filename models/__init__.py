"""
Models package - Contains all model-related functionality

This package provides model loading, chat generation, and addon integration
for GGUF models.
"""

from .model_loader import ModelLoader
from .chat_generator import ChatGenerator
# AddonManager moved to root - import from there if needed

__all__ = [
    'ModelLoader',
    'ChatGenerator'
]
