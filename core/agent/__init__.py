"""
Agent core functionality - Standalone agent implementation for GGUF Loader
"""

from .simple_agent import SimpleAgent
from .enterprise_agent import EnterpriseAgent

__all__ = ['SimpleAgent', 'EnterpriseAgent']
