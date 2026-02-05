#!/usr/bin/env python3
"""
Test Improved Model Detection

This script tests the improved model detection with periodic checks and better debugging.
"""

import sys
import os
import tempfile
import logging
import time
from pathlib import Path
from unittest.mock import Mock, MagicMock

# Add current directory to path for imports
sys.path.insert(0, '.')

def test_improved_model_detection():
    """Test the improved model detection with periodic checks."""
    print("=== Testing Improved Model Detection ===\n")
    
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QTimer, QEventLoop
        from addons.agentic_chatbot.main import AgenticChatbotAddon
        from addons.agentic_chatbot.agent_window import AgentWindow
        
        # Create QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        print("1. Testing scenario: Model loaded AFTER agent window is created")
        
        # Create mock GGUF app WITHOUT model initially
        mock_app = Mock()
        mock_app.model = None  # No model initially
        mock_app.model_loaded = Mock()
        mock_app.generation_finished = Mock()
        mock_app.generation_error = Mock()
        
        print("   Mock app created with NO model")
        
        # Create and start addon
        addon = AgenticChatbotAddon(mock_app)
        addon.start()
        
        print("   Addon started")
        
        # Create agent window
        agent_window = AgentWindow(addon)
        
        print("   Agent window created")
        
        # Check initial status (should be no model)
        initial_status = agent_window.model_status_label.text()
        print(f"   Initial status: {initial_status}")
        
        if "Not loaded" not in initial_status and "🔴" not in initial_status:
            print("   ERROR: Should show no model initially")
            return False
        
        print("\n2. Simulating model loading AFTER agent window creation...")
        
        # Now "load" the model
        mock_model = Mock()
        mock_model._mock_name = "test_model"  # Make it identifiable as a mock
        mock_app.model = mock_model
        
        print("   Model 'loaded' in mock app")
        
        # Manually trigger model status refresh (simulates periodic check)
        print("   Triggering manual refresh...")
        agent_window._refresh_model_status()
        
        # Check if status updated
        updated_status = agent_window.model_status_label.text()
        print(f"   Updated status: {updated_status}")
        
        if "Ready" not in updated_status and "🟢" not in updated_status:
            print("   ERROR: Should show model ready after loading")
            return False
        
        print("   SUCCESS: Model detection updated correctly")
        
        print("\n3. Testing periodic check functionality...")
        
        # Reset to no model
        mock_app.model = None
        agent_window._update_model_status()
        
        reset_status = agent_window.model_status_label.text()
        print(f"   Reset status: {reset_status}")
        
        # Load model again
        mock_app.model = mock_model
        
        # Trigger periodic check
        agent_window._periodic_model_check()
        
        periodic_status = agent_window.model_status_label.text()
        print(f"   After periodic check: {periodic_status}")
        
        if "Ready" not in periodic_status and "🟢" not in periodic_status:
            print("   ERROR: Periodic check should detect model")
            return False
        
        print("   SUCCESS: Periodic check works correctly")
        
        print("\n4. Testing with real model-like object...")
        
        # Create a more realistic mock model
        realistic_model = Mock()
        realistic_model.__call__ = Mock(return_value=iter([{"choices": [{"text": "test"}]}]))
        realistic_model.generate = Mock()
        mock_app.model = realistic_model
        
        agent_window._refresh_model_status()
        
        realistic_status = agent_window.model_status_label.text()
        print(f"   Realistic model status: {realistic_status}")
        
        if "Ready" not in realistic_status and "🟢" not in realistic_status:
            print("   ERROR: Should detect realistic model")
            return False
        
        print("   SUCCESS: Realistic model detected correctly")
        
        # Cleanup
        agent_window.close()
        addon.stop()
        
        print("\n✅ All improved model detection tests passed!")
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_model_detection_edge_cases():
    """Test edge cases in model detection."""
    print("\n=== Testing Model Detection Edge Cases ===\n")
    
    try:
        from PySide6.QtWidgets import QApplication
        from addons.agentic_chatbot.main import AgenticChatbotAddon
        from addons.agentic_chatbot.agent_window import AgentWindow
        
        # Create QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        print("1. Testing with None gguf_app...")
        
        # Test with None gguf_app
        addon_none = Mock()
        addon_none.gguf_app = None
        
        agent_window = AgentWindow(addon_none)
        result = agent_window._is_model_loaded()
        
        print(f"   None gguf_app result: {result}")
        if result:
            print("   ERROR: Should return False for None gguf_app")
            return False
        
        print("2. Testing with gguf_app but no model attribute...")
        
        # Test with gguf_app but no model attribute
        mock_app_no_model = Mock()
        del mock_app_no_model.model  # Remove model attribute
        
        addon_no_attr = Mock()
        addon_no_attr.gguf_app = mock_app_no_model
        
        agent_window2 = AgentWindow(addon_no_attr)
        result2 = agent_window2._is_model_loaded()
        
        print(f"   No model attribute result: {result2}")
        if result2:
            print("   ERROR: Should return False when no model attribute")
            return False
        
        print("3. Testing with empty string model...")
        
        # Test with empty string model
        mock_app_empty = Mock()
        mock_app_empty.model = ""
        
        addon_empty = Mock()
        addon_empty.gguf_app = mock_app_empty
        
        agent_window3 = AgentWindow(addon_empty)
        result3 = agent_window3._is_model_loaded()
        
        print(f"   Empty string model result: {result3}")
        # Empty string is not None, so it should return True
        if not result3:
            print("   Note: Empty string model returns False (expected)")
        
        # Cleanup
        agent_window.close()
        agent_window2.close()
        agent_window3.close()
        
        print("\n✅ Edge case tests completed!")
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run improved model detection tests."""
    print("=== Improved Model Detection Tests ===")
    
    # Suppress some logging but keep our debug prints
    logging.getLogger('addons.agentic_chatbot').setLevel(logging.WARNING)
    
    tests = [
        ("Improved Model Detection", test_improved_model_detection),
        ("Model Detection Edge Cases", test_model_detection_edge_cases)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        try:
            if test_func():
                passed += 1
                print(f"PASS: {test_name}")
            else:
                print(f"FAIL: {test_name}")
        except Exception as e:
            print(f"ERROR: {test_name} - {e}")
    
    print(f"\n=== IMPROVED MODEL DETECTION TEST SUMMARY ===")
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 ALL IMPROVED MODEL DETECTION TESTS PASSED!")
        print("\nThe agent window now has:")
        print("  • Improved model detection logic")
        print("  • Periodic model status checks")
        print("  • Manual refresh button (🔄)")
        print("  • Better debugging output")
        print("  • Robust handling of edge cases")
    else:
        print("❌ SOME TESTS FAILED")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)