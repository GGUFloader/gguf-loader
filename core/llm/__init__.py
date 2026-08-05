"""
core.llm - Pure model backend layer (no Qt dependencies).

Provides the ModelBackend wrapper around llama-cpp-python and prompt
formatting utilities used by both the chat and agent pipelines.
"""

from .model_backend import ModelBackend, LLAMA_AVAILABLE
from .prompt_builder import PromptBuilder

__all__ = ["ModelBackend", "LLAMA_AVAILABLE", "PromptBuilder"]
