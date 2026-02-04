"""
Context Manager - Manages conversation history and memory tracking

This component handles:
- Sliding window context management and memory tracking
- Conversation state persistence and recovery
- Token budget management and context optimization
"""

import json
import logging
import pickle
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QObject, Signal


@dataclass
class ConversationMessage:
    """Represents a single message in the conversation."""
    role: str  # 'user', 'assistant', 'tool'
    content: str
    timestamp: datetime
    metadata: Dict[str, Any]
    token_count: int = 0


@dataclass
class ConversationContext:
    """Represents the current conversation context."""
    session_id: str
    messages: List[ConversationMessage]
    total_tokens: int
    created_at: datetime
    last_updated: datetime
    workspace_path: str
    metadata: Dict[str, Any]


class ContextManager(QObject):
    """
    Manages conversation history with sliding window context management.
    
    This component:
    - Maintains conversation history with token tracking
    - Implements sliding window for context management
    - Provides conversation state persistence and recovery
    - Optimizes context for token budget constraints
    """
    
    # Signals
    context_updated = Signal(str)           # session_id
    context_saved = Signal(str)             # session_id
    context_loaded = Signal(str)            # session_id
    memory_threshold_reached = Signal(str)  # session_id
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the context manager.
        
        Args:
            config: Configuration dictionary for context management
        """
        super().__init__()
        
        self.config = config
        self._logger = logging.getLogger(__name__)
        
        # Context management settings
        self.max_context_tokens = config.get("max_context_tokens", 4096)
        self.context_window_size = config.get("context_window_size", 10)  # messages
        self.memory_retention_hours = config.get("memory_retention_hours", 24)
        self.auto_save_interval = config.get("auto_save_interval", 300)  # seconds
        
        # Storage settings
        self.persistence_enabled = config.get("enable_persistence", True)
        self.storage_path = Path(config.get("storage_path", "./agent_workspace/.context"))
        
        # Active contexts
        self._active_contexts: Dict[str, ConversationContext] = {}
        self._token_estimator = TokenEstimator()
        
        # Initialize storage
        if self.persistence_enabled:
            self._init_storage()
    
    def _init_storage(self):
        """Initialize storage directory for context persistence."""
        try:
            self.storage_path.mkdir(parents=True, exist_ok=True)
            self._logger.info(f"Context storage initialized at {self.storage_path}")
        except Exception as e:
            self._logger.error(f"Failed to initialize context storage: {e}")
            self.persistence_enabled = False
    
    def create_context(self, session_id: str, workspace_path: str, metadata: Optional[Dict[str, Any]] = None) -> ConversationContext:
        """
        Create a new conversation context for a session.
        
        Args:
            session_id: Unique session identifier
            workspace_path: Path to the workspace directory
            metadata: Optional metadata for the context
            
        Returns:
            ConversationContext: New conversation context
        """
        try:
            context = ConversationContext(
                session_id=session_id,
                messages=[],
                total_tokens=0,
                created_at=datetime.now(),
                last_updated=datetime.now(),
                workspace_path=workspace_path,
                metadata=metadata or {}
            )
            
            self._active_contexts[session_id] = context
            
            self._logger.info(f"Created conversation context for session {session_id}")
            self.context_updated.emit(session_id)
            
            return context
            
        except Exception as e:
            self._logger.error(f"Failed to create context for session {session_id}: {e}")
            raise
    
    def get_context(self, session_id: str) -> Optional[ConversationContext]:
        """
        Get conversation context for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Optional[ConversationContext]: Context if found, None otherwise
        """
        return self._active_contexts.get(session_id)
    
    def add_message(self, session_id: str, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Add a message to the conversation context.
        
        Args:
            session_id: Session identifier
            role: Message role ('user', 'assistant', 'tool')
            content: Message content
            metadata: Optional message metadata
            
        Returns:
            bool: True if message added successfully, False otherwise
        """
        try:
            context = self._active_contexts.get(session_id)
            if not context:
                self._logger.warning(f"Context not found for session {session_id}")
                return False
            
            # Estimate token count for the message
            token_count = self._token_estimator.estimate_tokens(content)
            
            # Create message
            message = ConversationMessage(
                role=role,
                content=content,
                timestamp=datetime.now(),
                metadata=metadata or {},
                token_count=token_count
            )
            
            # Add message to context
            context.messages.append(message)
            context.total_tokens += token_count
            context.last_updated = datetime.now()
            
            # Check if context window management is needed
            self._manage_context_window(context)
            
            self._logger.debug(f"Added {role} message to session {session_id} ({token_count} tokens)")
            self.context_updated.emit(session_id)
            
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to add message to session {session_id}: {e}")
            return False
    
    def _manage_context_window(self, context: ConversationContext):
        """
        Manage context window size and token budget.
        
        Args:
            context: Conversation context to manage
        """
        try:
            # Check token limit
            if context.total_tokens > self.max_context_tokens:
                self._logger.info(f"Context token limit exceeded for session {context.session_id}")
                self.memory_threshold_reached.emit(context.session_id)
                self._apply_sliding_window(context)
            
            # Check message count limit
            if len(context.messages) > self.context_window_size:
                self._logger.info(f"Context window size exceeded for session {context.session_id}")
                self._apply_sliding_window(context)
                
        except Exception as e:
            self._logger.error(f"Error managing context window: {e}")
    
    def _apply_sliding_window(self, context: ConversationContext):
        """
        Apply sliding window to reduce context size.
        
        Args:
            context: Context to apply sliding window to
        """
        try:
            original_count = len(context.messages)
            original_tokens = context.total_tokens
            
            # Keep system messages and recent messages
            system_messages = [msg for msg in context.messages if msg.role == 'system']
            recent_messages = context.messages[-self.context_window_size:]
            
            # Combine and deduplicate
            kept_messages = system_messages + [msg for msg in recent_messages if msg not in system_messages]
            
            # Update context
            context.messages = kept_messages
            context.total_tokens = sum(msg.token_count for msg in kept_messages)
            
            removed_count = original_count - len(kept_messages)
            removed_tokens = original_tokens - context.total_tokens
            
            self._logger.info(f"Applied sliding window to session {context.session_id}: "
                            f"removed {removed_count} messages ({removed_tokens} tokens)")
            
        except Exception as e:
            self._logger.error(f"Error applying sliding window: {e}")
    
    def get_context_for_generation(self, session_id: str, max_tokens: Optional[int] = None) -> str:
        """
        Get formatted context string for response generation.
        
        Args:
            session_id: Session identifier
            max_tokens: Optional token limit for context
            
        Returns:
            str: Formatted context string
        """
        try:
            context = self._active_contexts.get(session_id)
            if not context:
                return ""
            
            # Use provided limit or default
            token_limit = max_tokens or self.max_context_tokens
            
            # Build context string
            context_parts = []
            current_tokens = 0
            
            # Add messages in reverse order (most recent first) until token limit
            for message in reversed(context.messages):
                if current_tokens + message.token_count > token_limit:
                    break
                
                # Format message based on role
                if message.role == 'user':
                    context_parts.append(f"User: {message.content}")
                elif message.role == 'assistant':
                    context_parts.append(f"Assistant: {message.content}")
                elif message.role == 'tool':
                    context_parts.append(f"Tool Result: {message.content}")
                
                current_tokens += message.token_count
            
            # Reverse to get chronological order
            context_parts.reverse()
            
            return "\n\n".join(context_parts)
            
        except Exception as e:
            self._logger.error(f"Error building context for generation: {e}")
            return ""
    
    def save_context(self, session_id: str) -> bool:
        """
        Save conversation context to persistent storage.
        
        Args:
            session_id: Session identifier
            
        Returns:
            bool: True if saved successfully, False otherwise
        """
        if not self.persistence_enabled:
            return False
        
        try:
            context = self._active_contexts.get(session_id)
            if not context:
                self._logger.warning(f"Context not found for session {session_id}")
                return False
            
            # Prepare data for serialization
            context_data = {
                "session_id": context.session_id,
                "messages": [
                    {
                        "role": msg.role,
                        "content": msg.content,
                        "timestamp": msg.timestamp.isoformat(),
                        "metadata": msg.metadata,
                        "token_count": msg.token_count
                    }
                    for msg in context.messages
                ],
                "total_tokens": context.total_tokens,
                "created_at": context.created_at.isoformat(),
                "last_updated": context.last_updated.isoformat(),
                "workspace_path": context.workspace_path,
                "metadata": context.metadata
            }
            
            # Save to file
            context_file = self.storage_path / f"{session_id}.json"
            with open(context_file, 'w', encoding='utf-8') as f:
                json.dump(context_data, f, indent=2, ensure_ascii=False)
            
            self._logger.info(f"Saved context for session {session_id}")
            self.context_saved.emit(session_id)
            
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to save context for session {session_id}: {e}")
            return False
    
    def load_context(self, session_id: str) -> Optional[ConversationContext]:
        """
        Load conversation context from persistent storage.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Optional[ConversationContext]: Loaded context if found, None otherwise
        """
        if not self.persistence_enabled:
            return None
        
        try:
            context_file = self.storage_path / f"{session_id}.json"
            if not context_file.exists():
                self._logger.info(f"No saved context found for session {session_id}")
                return None
            
            # Load from file
            with open(context_file, 'r', encoding='utf-8') as f:
                context_data = json.load(f)
            
            # Reconstruct messages
            messages = []
            for msg_data in context_data["messages"]:
                message = ConversationMessage(
                    role=msg_data["role"],
                    content=msg_data["content"],
                    timestamp=datetime.fromisoformat(msg_data["timestamp"]),
                    metadata=msg_data["metadata"],
                    token_count=msg_data["token_count"]
                )
                messages.append(message)
            
            # Reconstruct context
            context = ConversationContext(
                session_id=context_data["session_id"],
                messages=messages,
                total_tokens=context_data["total_tokens"],
                created_at=datetime.fromisoformat(context_data["created_at"]),
                last_updated=datetime.fromisoformat(context_data["last_updated"]),
                workspace_path=context_data["workspace_path"],
                metadata=context_data["metadata"]
            )
            
            # Add to active contexts
            self._active_contexts[session_id] = context
            
            self._logger.info(f"Loaded context for session {session_id}")
            self.context_loaded.emit(session_id)
            
            return context
            
        except Exception as e:
            self._logger.error(f"Failed to load context for session {session_id}: {e}")
            return None
    
    def delete_context(self, session_id: str) -> bool:
        """
        Delete conversation context from memory and storage.
        
        Args:
            session_id: Session identifier
            
        Returns:
            bool: True if deleted successfully, False otherwise
        """
        try:
            # Remove from active contexts
            if session_id in self._active_contexts:
                del self._active_contexts[session_id]
            
            # Remove from storage
            if self.persistence_enabled:
                context_file = self.storage_path / f"{session_id}.json"
                if context_file.exists():
                    context_file.unlink()
            
            self._logger.info(f"Deleted context for session {session_id}")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to delete context for session {session_id}: {e}")
            return False
    
    def cleanup_old_contexts(self):
        """Clean up old contexts based on retention policy."""
        try:
            cutoff_time = datetime.now() - timedelta(hours=self.memory_retention_hours)
            
            # Clean up active contexts
            sessions_to_remove = []
            for session_id, context in self._active_contexts.items():
                if context.last_updated < cutoff_time:
                    sessions_to_remove.append(session_id)
            
            for session_id in sessions_to_remove:
                self.delete_context(session_id)
            
            # Clean up storage files
            if self.persistence_enabled and self.storage_path.exists():
                for context_file in self.storage_path.glob("*.json"):
                    try:
                        if context_file.stat().st_mtime < cutoff_time.timestamp():
                            context_file.unlink()
                            self._logger.debug(f"Cleaned up old context file: {context_file}")
                    except Exception as e:
                        self._logger.warning(f"Failed to clean up context file {context_file}: {e}")
            
            if sessions_to_remove:
                self._logger.info(f"Cleaned up {len(sessions_to_remove)} old contexts")
                
        except Exception as e:
            self._logger.error(f"Error during context cleanup: {e}")
    
    def get_context_stats(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get statistics about a conversation context.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Optional[Dict[str, Any]]: Context statistics if found, None otherwise
        """
        context = self._active_contexts.get(session_id)
        if not context:
            return None
        
        message_counts = {}
        for message in context.messages:
            role = message.role
            message_counts[role] = message_counts.get(role, 0) + 1
        
        return {
            "session_id": session_id,
            "total_messages": len(context.messages),
            "total_tokens": context.total_tokens,
            "message_counts": message_counts,
            "created_at": context.created_at.isoformat(),
            "last_updated": context.last_updated.isoformat(),
            "workspace_path": context.workspace_path,
            "duration_hours": (datetime.now() - context.created_at).total_seconds() / 3600
        }
    
    def get_all_active_sessions(self) -> List[str]:
        """
        Get list of all active session IDs.
        
        Returns:
            List[str]: List of active session IDs
        """
        return list(self._active_contexts.keys())


class TokenEstimator:
    """Simple token estimator for context management."""
    
    def __init__(self):
        # Rough approximation: 1 token ≈ 4 characters for English text
        self.chars_per_token = 4
    
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        
        Args:
            text: Text to estimate tokens for
            
        Returns:
            int: Estimated token count
        """
        if not text:
            return 0
        
        # Simple character-based estimation
        char_count = len(text)
        token_estimate = max(1, char_count // self.chars_per_token)
        
        return token_estimate