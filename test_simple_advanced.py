#!/usr/bin/env python3
"""
Simple test for advanced agent features without circular imports
"""

import sys
import os
import logging

# Add the project root to Python path
sys.path.insert(0, os.path.abspath('.'))

def test_direct_imports():
    """Test direct imports of advanced features."""
    print("Testing direct imports...")
    
    try:
        # Test streaming handler
        from addons.agentic_chatbot.streaming_handler import StreamingHandler
        print("✓ StreamingHandler imported")
        
        # Test memory manager
        from addons.agentic_chatbot.memory_manager import MemoryManager
        print("✓ MemoryManager imported")
        
        # Test progress monitor
        from addons.agentic_chatbot.progress_monitor import ProgressMonitor
        print("✓ ProgressMonitor imported")
        
        # Test safety monitor
        from addons.agentic_chatbot.safety_monitor import SafetyMonitor
        print("✓ SafetyMonitor imported")
        
        # Test event system
        from addons.agentic_chatbot.event_system import EventSystem
        print("✓ EventSystem imported")
        
        return True
        
    except Exception as e:
        print(f"✗ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_basic_functionality():
    """Test basic functionality of advanced features."""
    print("\nTesting basic functionality...")
    
    try:
        from addons.agentic_chatbot.streaming_handler import StreamingHandler
        from addons.agentic_chatbot.memory_manager import MemoryManager
        from addons.agentic_chatbot.progress_monitor import ProgressMonitor
        from addons.agentic_chatbot.safety_monitor import SafetyMonitor
        from addons.agentic_chatbot.event_system import EventSystem, EventType
        
        # Test streaming handler
        config = {"enable_streaming": True}
        handler = StreamingHandler(config)
        print("✓ StreamingHandler created")
        
        # Test memory manager
        config = {"enable_memory_persistence": False}
        manager = MemoryManager(config)
        print("✓ MemoryManager created")
        
        # Test progress monitor
        config = {"max_concurrent_operations": 5}
        monitor = ProgressMonitor(config)
        print("✓ ProgressMonitor created")
        
        # Test safety monitor
        config = {"enable_safety_monitoring": True}
        safety = SafetyMonitor(config)
        print("✓ SafetyMonitor created")
        
        # Test event system
        config = {"enable_async_callbacks": False}
        events = EventSystem(config)
        print("✓ EventSystem created")
        
        # Cleanup
        events.shutdown()
        
        return True
        
    except Exception as e:
        print(f"✗ Functionality test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run tests."""
    print("Running Simple Advanced Features Tests...")
    print("=" * 50)
    
    # Setup logging
    logging.basicConfig(level=logging.WARNING)
    
    success = True
    
    if not test_direct_imports():
        success = False
    
    if not test_basic_functionality():
        success = False
    
    print("=" * 50)
    if success:
        print("✓ All tests passed!")
    else:
        print("✗ Some tests failed!")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)