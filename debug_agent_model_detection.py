#!/usr/bin/env python3
"""
Debug Agent Model Detection - Simple test to check model detection in agent window
"""

import sys
import os
import logging
from pathlib import Path
from unittest.mock import Mock

# Add current directory to path for imports
sys.path.insert(0, '.')

def test_model_detection():
    """Test model detection in agent window."""
    print("=== Testing Agent Model Detection ===")
    
    try:
        from PySide6.QtWidgets import QApplication
        from addons.agentic_chatbot.main import AgenticChatbotAddon
        from addons.agentic_chatbot.agent_window import AgentWindow
        
        # Create QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        print("1. Creating mock GGUF app...")
        
        # Create mock GGUF app with model
        mock_app = Mock()
        mock_model = Mock()
        mock_model._mock_name = "test_model"  # This should be detected
        mock_app.model = mock_model
        
        # Add required signals
        mock_app.model_loaded = Mock()
        mock_app.generation_finished = Mock()
        mock_app.generation_error = Mock()
        
        print("   ✓ Mock app created with model")
        
        print("2. Creating and starting addon...")
        
        # Create addon
        addon = AgenticChatbotAddon(mock_app)
        if not addon.start():
            print("   ❌ Failed to start addon")
            return False
        
        print("   ✓ Addon started")
        
        print("3. Creating agent window...")
        
        # Create agent window
        agent_window = AgentWindow(addon)
        
        print("   ✓ Agent window created")
        
        print("4. Testing model detection...")
        
        # Test direct model access
        print(f"   - addon: {agent_window.addon}")
        print(f"   - gguf_app: {getattr(agent_window.addon, 'gguf_app', 'NOT FOUND')}")
        
        if hasattr(agent_window.addon, 'gguf_app'):
            gguf_app = agent_window.addon.gguf_app
            print(f"   - model attribute exists: {hasattr(gguf_app, 'model')}")
            if hasattr(gguf_app, 'model'):
                print(f"   - model: {gguf_app.model}")
                print(f"   - model type: {type(gguf_app.model)}")
        
        # Test model detection method
        model_detected = agent_window._is_model_loaded()
        print(f"   - Model detected: {model_detected}")
        
        # Check UI status
        status_text = agent_window.model_status_label.text()
        print(f"   - UI status: {status_text}")
        
        # Test refresh button
        print("5. Testing manual refresh...")
        agent_window._refresh_model_status()
        
        # Check status after refresh
        status_text_after = agent_window.model_status_label.text()
        print(f"   - UI status after refresh: {status_text_after}")
        
        # Final result
        if model_detected and "Ready" in status_text_after:
            print("\n✅ SUCCESS: Model detection working correctly")
            return True
        else:
            print(f"\n❌ FAILED: Model detection not working")
            print(f"   - Detection result: {model_detected}")
            print(f"   - UI status: {status_text_after}")
            return False
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup
        try:
            if 'agent_window' in locals():
                agent_window.close()
            if 'addon' in locals():
                addon.stop()
        except:
            pass

def test_real_app_integration():
    """Test with real app structure (if available)."""
    print("\n=== Testing Real App Integration ===")
    
    try:
        from ui.ai_chat_window import AIChat
        from addons.agentic_chatbot.main import AgenticChatbotAddon
        from addons.agentic_chatbot.agent_window import AgentWindow
        
        print("1. Creating real AIChat app...")
        
        # Create real AIChat app
        real_app = AIChat()
        
        # Set a mock model to simulate loaded state
        mock_model = Mock()
        mock_model._mock_name = "test_model"
        real_app.model = mock_model
        
        print("   ✓ Real app created with mock model")
        
        print("2. Creating addon with real app...")
        
        # Create addon with real app
        addon = AgenticChatbotAddon(real_app)
        if not addon.start():
            print("   ❌ Failed to start addon")
            return False
        
        print("   ✓ Addon started with real app")
        
        print("3. Creating agent window...")
        
        # Create agent window
        agent_window = AgentWindow(addon)
        
        print("   ✓ Agent window created")
        
        print("4. Testing model detection with real app...")
        
        # Test model detection
        model_detected = agent_window._is_model_loaded()
        print(f"   - Model detected: {model_detected}")
        
        # Check UI status
        status_text = agent_window.model_status_label.text()
        print(f"   - UI status: {status_text}")
        
        # Emit model_loaded signal to simulate model loading
        print("5. Simulating model_loaded signal...")
        real_app.model_loaded.emit(mock_model)
        
        # Check status after signal
        status_text_after = agent_window.model_status_label.text()
        print(f"   - UI status after signal: {status_text_after}")
        
        # Final result
        if model_detected and "Ready" in status_text_after:
            print("\n✅ SUCCESS: Real app integration working")
            return True
        else:
            print(f"\n❌ FAILED: Real app integration not working")
            return False
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup
        try:
            if 'agent_window' in locals():
                agent_window.close()
            if 'addon' in locals():
                addon.stop()
            if 'real_app' in locals():
                real_app.close()
        except:
            pass

def main():
    """Run all tests."""
    # Enable debug logging
    logging.basicConfig(level=logging.DEBUG)
    
    tests = [
        ("Mock Model Detection", test_model_detection),
        ("Real App Integration", test_real_app_integration)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Running: {test_name}")
        print('='*50)
        
        try:
            if test_func():
                passed += 1
                print(f"\n✅ PASSED: {test_name}")
            else:
                print(f"\n❌ FAILED: {test_name}")
        except Exception as e:
            print(f"\n💥 ERROR: {test_name} - {e}")
    
    print(f"\n{'='*50}")
    print(f"SUMMARY: {passed}/{total} tests passed")
    print('='*50)
    
    if passed == total:
        print("🎉 All tests passed! Model detection should work correctly.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)