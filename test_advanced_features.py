#!/usr/bin/env python3
"""
Test script for advanced agent features
"""

import sys
import os
import logging
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, os.path.abspath('.'))

from addons.agentic_chatbot.streaming_handler import StreamingHandler
from addons.agentic_chatbot.memory_manager import MemoryManager
from addons.agentic_chatbot.progress_monitor import ProgressMonitor
from addons.agentic_chatbot.safety_monitor import SafetyMonitor
from addons.agentic_chatbot.event_system import EventSystem, EventType

def test_streaming_handler():
    """Test streaming handler functionality."""
    print("Testing Streaming Handler...")
    
    config = {
        "streaming_buffer_size": 5,
        "streaming_flush_interval": 100,
        "enable_streaming": True
    }
    
    handler = StreamingHandler(config)
    
    # Test streaming session
    handler.start_streaming("response", 10)
    assert handler.is_streaming()
    
    # Add some tokens
    handler.add_token("Hello")
    handler.add_token(" ")
    handler.add_token("world")
    
    # Add a chunk
    handler.add_chunk("Tool execution started", "tool_call")
    
    # Finish streaming
    handler.finish_streaming()
    assert not handler.is_streaming()
    
    print("✓ Streaming Handler test passed")

def test_memory_manager():
    """Test memory manager functionality."""
    print("Testing Memory Manager...")
    
    config = {
        "memory_retention_days": 7,
        "max_completed_tasks": 100,
        "max_file_modifications": 500,
        "enable_memory_persistence": False  # Disable for testing
    }
    
    manager = MemoryManager(config)
    
    # Record a completed task
    task_id = manager.record_completed_task(
        "Test task",
        "/test/workspace",
        ["read_file", "write_file"],
        "Task completed successfully",
        "test_session"
    )
    
    assert task_id != ""
    
    # Check for redundancy
    redundant = manager.check_task_redundancy(
        "Test task",
        "/test/workspace", 
        ["read_file", "write_file"]
    )
    
    assert redundant is not None
    
    # Record file modification
    manager.record_file_modification(
        "/test/file.txt",
        "created",
        "write_file",
        "test_session"
    )
    
    # Get file history
    history = manager.get_file_history("/test/file.txt")
    assert len(history) == 1
    
    print("✓ Memory Manager test passed")

def test_progress_monitor():
    """Test progress monitor functionality."""
    print("Testing Progress Monitor...")
    
    config = {
        "progress_update_interval": 100,
        "enable_progress_estimation": True,
        "max_concurrent_operations": 5
    }
    
    monitor = ProgressMonitor(config)
    
    # Start an operation
    success = monitor.start_operation("test_op", "Test Operation", 3)
    assert success
    
    # Update progress
    monitor.update_progress("test_op", 1, "Step 1 completed")
    monitor.update_progress("test_op", 2, "Step 2 completed")
    
    # Complete operation
    monitor.complete_operation("test_op", "All steps completed")
    
    # Check operation info
    info = monitor.get_operation_info("test_op")
    # Operation should be cleaned up after completion
    
    print("✓ Progress Monitor test passed")

def test_safety_monitor():
    """Test safety monitor functionality."""
    print("Testing Safety Monitor...")
    
    config = {
        "enable_safety_monitoring": True,
        "require_confirmation_for_high_risk": False,  # Disable for testing
        "block_critical_operations": True,
        "log_all_violations": True
    }
    
    monitor = SafetyMonitor(config, parent_widget=None)
    
    # Test safe operation
    is_allowed, violation = monitor.validate_operation(
        "file_operation",
        "read file.txt"
    )
    assert is_allowed
    assert violation is None
    
    # Test dangerous operation
    is_allowed, violation = monitor.validate_operation(
        "command_execution",
        "sudo rm -rf /"
    )
    assert not is_allowed  # Should be blocked
    assert violation is not None
    
    print("✓ Safety Monitor test passed")

def test_event_system():
    """Test event system functionality."""
    print("Testing Event System...")
    
    config = {
        "enable_async_callbacks": False,  # Disable for testing
        "max_callback_timeout": 30,
        "max_event_queue_size": 100,
        "enable_event_logging": True
    }
    
    event_system = EventSystem(config)
    
    # Register a callback
    callback_executed = False
    
    def test_callback(event):
        nonlocal callback_executed
        callback_executed = True
        assert event.event_type == EventType.TOOL_CALL_STARTED
    
    callback_id = event_system.register_callback(
        EventType.TOOL_CALL_STARTED,
        test_callback
    )
    
    assert callback_id != ""
    
    # Emit an event
    event_id = event_system.emit_event(
        EventType.TOOL_CALL_STARTED,
        "test_source",
        {"tool_name": "test_tool"},
        immediate=True
    )
    
    assert event_id != ""
    assert callback_executed
    
    # Cleanup
    event_system.shutdown()
    
    print("✓ Event System test passed")

def main():
    """Run all tests."""
    print("Running Advanced Features Tests...")
    print("=" * 50)
    
    # Setup logging
    logging.basicConfig(level=logging.WARNING)
    
    try:
        test_streaming_handler()
        test_memory_manager()
        test_progress_monitor()
        test_safety_monitor()
        test_event_system()
        
        print("=" * 50)
        print("✓ All tests passed!")
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)