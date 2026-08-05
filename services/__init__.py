"""
services - Qt application layer bridging the UI to the pure core layer.

- ModelService: background model loading/unloading.
- ChatService: streaming chat generation.
- AgentService: background agent turns.
"""

from .model_service import ModelService
from .chat_service import ChatService
from .agent_service import AgentService

__all__ = ["ModelService", "ChatService", "AgentService"]
