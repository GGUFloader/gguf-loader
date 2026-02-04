"""
Memory Manager - Tracks completed work and file modifications

This component handles:
- Tracking completed tasks to avoid redundant operations
- Maintaining change history for file modifications
- Managing work session memory and state persistence
"""

import json
import logging
import hashlib
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QObject, Signal


@dataclass
class CompletedTask:
    """Represents a completed task in memory."""
    task_id: str
    description: str
    completed_at: datetime
    workspace_path: str
    tool_calls_used: List[str]
    result_summary: str
    metadata: Dict[str, Any]


@dataclass
class FileModification:
    """Represents a file modification event."""
    file_path: str
    modification_type: str  # 'created', 'modified', 'deleted'
    timestamp: datetime
    content_hash: Optional[str]
    size_bytes: Optional[int]
    tool_used: str
    session_id: str
    metadata: Dict[str, Any]


class MemoryManager(QObject):
    """
    Manages agent memory for completed work and file modifications.
    
    This component:
    - Tracks completed tasks to avoid redundant operations
    - Maintains change history for file modifications
    - Provides memory persistence and retrieval capabilities
    """
    
    # Signals
    task_completed = Signal(dict)           # completed_task
    file_modified = Signal(dict)            # file_modification
    memory_updated = Signal(str)            # session_id
    redundant_task_detected = Signal(dict)  # task_info
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the memory manager.
        
        Args:
            config: Configuration dictionary for memory management
        """
        super().__init__()
        
        self.config = config
        self._logger = logging.getLogger(__name__)
        
        # Memory settings
        self.memory_retention_days = config.get("memory_retention_days", 7)
        self.max_completed_tasks = config.get("max_completed_tasks", 1000)
        self.max_file_modifications = config.get("max_file_modifications", 5000)
        self.enable_persistence = config.get("enable_memory_persistence", True)
        
        # Storage settings
        self.storage_path = Path(config.get("memory_storage_path", "./agent_workspace/.memory"))
        
        # Memory storage
        self._completed_tasks: Dict[str, CompletedTask] = {}
        self._file_modifications: List[FileModification] = []
        self._task_signatures: Dict[str, str] = {}  # task_signature -> task_id
        self._file_hashes: Dict[str, str] = {}  # file_path -> content_hash
        
        # Initialize storage
        if self.enable_persistence:
            self._init_storage()
            self._load_memory()
    
    def _init_storage(self):
        """Initialize storage directory for memory persistence."""
        try:
            self.storage_path.mkdir(parents=True, exist_ok=True)
            self._logger.info(f"Memory storage initialized at {self.storage_path}")
        except Exception as e:
            self._logger.error(f"Failed to initialize memory storage: {e}")
            self.enable_persistence = False
    
    def _generate_task_signature(self, description: str, workspace_path: str, tool_calls: List[str]) -> str:
        """
        Generate a unique signature for a task.
        
        Args:
            description: Task description
            workspace_path: Workspace path
            tool_calls: List of tool calls used
            
        Returns:
            str: Task signature hash
        """
        # Create signature from task components
        signature_data = {
            "description": description.lower().strip(),
            "workspace": workspace_path,
            "tools": sorted(tool_calls)
        }
        
        signature_str = json.dumps(signature_data, sort_keys=True)
        return hashlib.sha256(signature_str.encode()).hexdigest()[:16]
    
    def _calculate_file_hash(self, file_path: Path) -> Optional[str]:
        """
        Calculate content hash for a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Optional[str]: File content hash or None if error
        """
        try:
            if not file_path.exists():
                return None
            
            with open(file_path, 'rb') as f:
                content = f.read()
                return hashlib.sha256(content).hexdigest()[:16]
                
        except Exception as e:
            self._logger.warning(f"Failed to calculate hash for {file_path}: {e}")
            return None
    
    def record_completed_task(self, description: str, workspace_path: str, 
                            tool_calls_used: List[str], result_summary: str,
                            session_id: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Record a completed task in memory.
        
        Args:
            description: Task description
            workspace_path: Workspace path where task was completed
            tool_calls_used: List of tool names used
            result_summary: Summary of task results
            session_id: Session ID where task was completed
            metadata: Optional task metadata
            
        Returns:
            str: Task ID for the recorded task
        """
        try:
            # Generate task signature and ID
            task_signature = self._generate_task_signature(description, workspace_path, tool_calls_used)
            task_id = f"task_{int(datetime.now().timestamp())}_{task_signature}"
            
            # Create completed task record
            completed_task = CompletedTask(
                task_id=task_id,
                description=description,
                completed_at=datetime.now(),
                workspace_path=workspace_path,
                tool_calls_used=tool_calls_used,
                result_summary=result_summary,
                metadata=metadata or {}
            )
            
            # Store in memory
            self._completed_tasks[task_id] = completed_task
            self._task_signatures[task_signature] = task_id
            
            # Emit signal
            self.task_completed.emit({
                "task_id": task_id,
                "description": description,
                "completed_at": completed_task.completed_at.isoformat(),
                "tool_calls_used": tool_calls_used,
                "result_summary": result_summary
            })
            
            # Cleanup old tasks if needed
            self._cleanup_old_tasks()
            
            # Save to persistence
            if self.enable_persistence:
                self._save_memory()
            
            self._logger.info(f"Recorded completed task: {task_id}")
            return task_id
            
        except Exception as e:
            self._logger.error(f"Failed to record completed task: {e}")
            return ""
    
    def check_task_redundancy(self, description: str, workspace_path: str, 
                            tool_calls: List[str]) -> Optional[CompletedTask]:
        """
        Check if a similar task has already been completed.
        
        Args:
            description: Task description to check
            workspace_path: Workspace path
            tool_calls: List of tool calls planned
            
        Returns:
            Optional[CompletedTask]: Previously completed similar task, if found
        """
        try:
            task_signature = self._generate_task_signature(description, workspace_path, tool_calls)
            
            if task_signature in self._task_signatures:
                task_id = self._task_signatures[task_signature]
                completed_task = self._completed_tasks.get(task_id)
                
                if completed_task:
                    # Check if task is still recent enough to be relevant
                    age = datetime.now() - completed_task.completed_at
                    if age.days <= self.memory_retention_days:
                        self._logger.info(f"Found similar completed task: {task_id}")
                        self.redundant_task_detected.emit({
                            "task_id": task_id,
                            "description": completed_task.description,
                            "completed_at": completed_task.completed_at.isoformat(),
                            "result_summary": completed_task.result_summary
                        })
                        return completed_task
            
            return None
            
        except Exception as e:
            self._logger.error(f"Error checking task redundancy: {e}")
            return None
    
    def record_file_modification(self, file_path: str, modification_type: str,
                               tool_used: str, session_id: str,
                               metadata: Optional[Dict[str, Any]] = None):
        """
        Record a file modification event.
        
        Args:
            file_path: Path to the modified file
            modification_type: Type of modification ('created', 'modified', 'deleted')
            tool_used: Name of the tool that made the modification
            session_id: Session ID where modification occurred
            metadata: Optional modification metadata
        """
        try:
            file_path_obj = Path(file_path)
            
            # Calculate file hash and size if file exists
            content_hash = None
            size_bytes = None
            
            if modification_type != 'deleted' and file_path_obj.exists():
                content_hash = self._calculate_file_hash(file_path_obj)
                size_bytes = file_path_obj.stat().st_size
            
            # Create modification record
            modification = FileModification(
                file_path=file_path,
                modification_type=modification_type,
                timestamp=datetime.now(),
                content_hash=content_hash,
                size_bytes=size_bytes,
                tool_used=tool_used,
                session_id=session_id,
                metadata=metadata or {}
            )
            
            # Store in memory
            self._file_modifications.append(modification)
            
            # Update file hash tracking
            if content_hash:
                self._file_hashes[file_path] = content_hash
            elif modification_type == 'deleted' and file_path in self._file_hashes:
                del self._file_hashes[file_path]
            
            # Emit signal
            self.file_modified.emit({
                "file_path": file_path,
                "modification_type": modification_type,
                "timestamp": modification.timestamp.isoformat(),
                "tool_used": tool_used,
                "session_id": session_id,
                "size_bytes": size_bytes
            })
            
            # Cleanup old modifications if needed
            self._cleanup_old_modifications()
            
            # Save to persistence
            if self.enable_persistence:
                self._save_memory()
            
            self._logger.debug(f"Recorded file modification: {file_path} ({modification_type})")
            
        except Exception as e:
            self._logger.error(f"Failed to record file modification: {e}")
    
    def get_file_history(self, file_path: str) -> List[FileModification]:
        """
        Get modification history for a specific file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            List[FileModification]: List of modifications for the file
        """
        try:
            modifications = [
                mod for mod in self._file_modifications
                if mod.file_path == file_path
            ]
            
            # Sort by timestamp (most recent first)
            modifications.sort(key=lambda x: x.timestamp, reverse=True)
            
            return modifications
            
        except Exception as e:
            self._logger.error(f"Error getting file history: {e}")
            return []
    
    def get_recent_modifications(self, hours: int = 24) -> List[FileModification]:
        """
        Get recent file modifications within specified time window.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            List[FileModification]: List of recent modifications
        """
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            recent_modifications = [
                mod for mod in self._file_modifications
                if mod.timestamp >= cutoff_time
            ]
            
            # Sort by timestamp (most recent first)
            recent_modifications.sort(key=lambda x: x.timestamp, reverse=True)
            
            return recent_modifications
            
        except Exception as e:
            self._logger.error(f"Error getting recent modifications: {e}")
            return []
    
    def get_completed_tasks(self, workspace_path: Optional[str] = None,
                          hours: Optional[int] = None) -> List[CompletedTask]:
        """
        Get completed tasks, optionally filtered by workspace and time.
        
        Args:
            workspace_path: Optional workspace path filter
            hours: Optional hours to look back
            
        Returns:
            List[CompletedTask]: List of completed tasks
        """
        try:
            tasks = list(self._completed_tasks.values())
            
            # Filter by workspace if specified
            if workspace_path:
                tasks = [task for task in tasks if task.workspace_path == workspace_path]
            
            # Filter by time if specified
            if hours:
                cutoff_time = datetime.now() - timedelta(hours=hours)
                tasks = [task for task in tasks if task.completed_at >= cutoff_time]
            
            # Sort by completion time (most recent first)
            tasks.sort(key=lambda x: x.completed_at, reverse=True)
            
            return tasks
            
        except Exception as e:
            self._logger.error(f"Error getting completed tasks: {e}")
            return []
    
    def _cleanup_old_tasks(self):
        """Clean up old completed tasks based on retention policy."""
        try:
            if len(self._completed_tasks) <= self.max_completed_tasks:
                return
            
            # Sort tasks by completion time
            tasks_by_time = sorted(
                self._completed_tasks.items(),
                key=lambda x: x[1].completed_at
            )
            
            # Remove oldest tasks
            tasks_to_remove = len(self._completed_tasks) - self.max_completed_tasks
            
            for i in range(tasks_to_remove):
                task_id, task = tasks_by_time[i]
                
                # Remove from storage
                del self._completed_tasks[task_id]
                
                # Remove from signature mapping
                task_signature = self._generate_task_signature(
                    task.description, task.workspace_path, task.tool_calls_used
                )
                if task_signature in self._task_signatures:
                    del self._task_signatures[task_signature]
            
            self._logger.info(f"Cleaned up {tasks_to_remove} old completed tasks")
            
        except Exception as e:
            self._logger.error(f"Error cleaning up old tasks: {e}")
    
    def _cleanup_old_modifications(self):
        """Clean up old file modifications based on retention policy."""
        try:
            if len(self._file_modifications) <= self.max_file_modifications:
                return
            
            # Sort modifications by timestamp
            self._file_modifications.sort(key=lambda x: x.timestamp)
            
            # Remove oldest modifications
            modifications_to_remove = len(self._file_modifications) - self.max_file_modifications
            self._file_modifications = self._file_modifications[modifications_to_remove:]
            
            self._logger.info(f"Cleaned up {modifications_to_remove} old file modifications")
            
        except Exception as e:
            self._logger.error(f"Error cleaning up old modifications: {e}")
    
    def _save_memory(self):
        """Save memory data to persistent storage."""
        try:
            if not self.enable_persistence:
                return
            
            # Prepare data for serialization
            memory_data = {
                "completed_tasks": {
                    task_id: {
                        "task_id": task.task_id,
                        "description": task.description,
                        "completed_at": task.completed_at.isoformat(),
                        "workspace_path": task.workspace_path,
                        "tool_calls_used": task.tool_calls_used,
                        "result_summary": task.result_summary,
                        "metadata": task.metadata
                    }
                    for task_id, task in self._completed_tasks.items()
                },
                "file_modifications": [
                    {
                        "file_path": mod.file_path,
                        "modification_type": mod.modification_type,
                        "timestamp": mod.timestamp.isoformat(),
                        "content_hash": mod.content_hash,
                        "size_bytes": mod.size_bytes,
                        "tool_used": mod.tool_used,
                        "session_id": mod.session_id,
                        "metadata": mod.metadata
                    }
                    for mod in self._file_modifications
                ],
                "task_signatures": self._task_signatures,
                "file_hashes": self._file_hashes,
                "saved_at": datetime.now().isoformat()
            }
            
            # Save to file
            memory_file = self.storage_path / "memory.json"
            with open(memory_file, 'w', encoding='utf-8') as f:
                json.dump(memory_data, f, indent=2, ensure_ascii=False)
            
            self._logger.debug("Memory data saved to persistent storage")
            
        except Exception as e:
            self._logger.error(f"Failed to save memory data: {e}")
    
    def _load_memory(self):
        """Load memory data from persistent storage."""
        try:
            if not self.enable_persistence:
                return
            
            memory_file = self.storage_path / "memory.json"
            if not memory_file.exists():
                self._logger.info("No saved memory data found")
                return
            
            # Load from file
            with open(memory_file, 'r', encoding='utf-8') as f:
                memory_data = json.load(f)
            
            # Restore completed tasks
            for task_id, task_data in memory_data.get("completed_tasks", {}).items():
                task = CompletedTask(
                    task_id=task_data["task_id"],
                    description=task_data["description"],
                    completed_at=datetime.fromisoformat(task_data["completed_at"]),
                    workspace_path=task_data["workspace_path"],
                    tool_calls_used=task_data["tool_calls_used"],
                    result_summary=task_data["result_summary"],
                    metadata=task_data["metadata"]
                )
                self._completed_tasks[task_id] = task
            
            # Restore file modifications
            for mod_data in memory_data.get("file_modifications", []):
                modification = FileModification(
                    file_path=mod_data["file_path"],
                    modification_type=mod_data["modification_type"],
                    timestamp=datetime.fromisoformat(mod_data["timestamp"]),
                    content_hash=mod_data["content_hash"],
                    size_bytes=mod_data["size_bytes"],
                    tool_used=mod_data["tool_used"],
                    session_id=mod_data["session_id"],
                    metadata=mod_data["metadata"]
                )
                self._file_modifications.append(modification)
            
            # Restore mappings
            self._task_signatures = memory_data.get("task_signatures", {})
            self._file_hashes = memory_data.get("file_hashes", {})
            
            self._logger.info(f"Loaded memory data: {len(self._completed_tasks)} tasks, "
                            f"{len(self._file_modifications)} modifications")
            
        except Exception as e:
            self._logger.error(f"Failed to load memory data: {e}")
    
    def clear_memory(self, workspace_path: Optional[str] = None):
        """
        Clear memory data, optionally for specific workspace.
        
        Args:
            workspace_path: Optional workspace path to clear (clears all if None)
        """
        try:
            if workspace_path:
                # Clear only for specific workspace
                tasks_to_remove = [
                    task_id for task_id, task in self._completed_tasks.items()
                    if task.workspace_path == workspace_path
                ]
                
                for task_id in tasks_to_remove:
                    task = self._completed_tasks[task_id]
                    del self._completed_tasks[task_id]
                    
                    # Remove from signature mapping
                    task_signature = self._generate_task_signature(
                        task.description, task.workspace_path, task.tool_calls_used
                    )
                    if task_signature in self._task_signatures:
                        del self._task_signatures[task_signature]
                
                # Clear file modifications for workspace
                self._file_modifications = [
                    mod for mod in self._file_modifications
                    if not mod.file_path.startswith(workspace_path)
                ]
                
                self._logger.info(f"Cleared memory for workspace: {workspace_path}")
            else:
                # Clear all memory
                self._completed_tasks.clear()
                self._file_modifications.clear()
                self._task_signatures.clear()
                self._file_hashes.clear()
                
                self._logger.info("Cleared all memory data")
            
            # Save changes
            if self.enable_persistence:
                self._save_memory()
                
        except Exception as e:
            self._logger.error(f"Error clearing memory: {e}")
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """
        Get memory usage statistics.
        
        Returns:
            Dict containing memory statistics
        """
        return {
            "completed_tasks": len(self._completed_tasks),
            "file_modifications": len(self._file_modifications),
            "task_signatures": len(self._task_signatures),
            "file_hashes": len(self._file_hashes),
            "memory_retention_days": self.memory_retention_days,
            "max_completed_tasks": self.max_completed_tasks,
            "max_file_modifications": self.max_file_modifications,
            "persistence_enabled": self.enable_persistence
        }