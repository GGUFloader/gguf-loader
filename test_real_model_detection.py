#!/usr/bin/env python3
"""
Test Real Model Detection - Test with simulated real Llama model
"""

import sys
import os
import logging
from pathlib import Path
from unittest.mock import Mock

# Add current directory to path for imports
sys.path.insert(0, '.')

def test_llama_model_detection():
    """Test model detection with simulated Llama model."""
    print("=== Testing Llama Model Detection ===")
    
    try:
        from PySide6.QtWidgets import QApplication
        from addons.agentic_chatbot.main import AgenticChatbotAddon
        from addons.agentic_chatbot.agent_window import AgentWindow
        
        # Create QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        print("1. Creating mock GGUF app with Llama-like model...")
        
        # Create mock GGUF app with Llama-like model
        mock_app = Mock()
        
        # Create a mock that looks like a real Llama model
        mock_model = Mock()
        mock_model.__class__.__name__ = 'Llama'  # This should match the real class name
        
        # Add some methods that real Llama models have
        def mock_call(*args, **kwargs):
            return {"choices": [{"text": "Test response"}]}
        
        mock_model.__call__ = mock_call
        mock_model.generate = Mock()
        
        mock_app.model = mock_model
        
        # Add required signals
        mock_app.model_loaded = Mock()
        mock_app.generation_finished = Mock()
        mock_app.generation_error = Mock()
        
        print("   ✓ Mock app created with Llama-like model")
        
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
        
        print("4. Testing Llama model detection...")
        
        # Test direct model access
        print(f"   - addon: {agent_window.addon}")
        print(f"   - gguf_app: {getattr(agent_window.addon, 'gguf_app', 'NOT FOUND')}")
        
        if hasattr(agent_window.addon, 'gguf_app'):
            gguf_app = agent_window.addon.gguf_app
            print(f"   - model attribute exists: {hasattr(gguf_app, 'model')}")
            if hasattr(gguf_app, 'model'):
                print(f"   - model: {gguf_app.model}")
                print(f"   - model type: {type(gguf_app.model)}")
                print(f"   - model class name: {type(gguf_app.model).__name__}")
        
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
            print("\n✅ SUCCESS: Llama model detection working correctly")
            return True
        else:
            print(f"\n❌ FAILED: Llama model detection not working")
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

def test_model_loading_workflow():
    """Test the complete model loading workflow."""
    print("\n=== Testing Model Loading Workflow ===")
    
    try:
        from PySide6.QtWidgets import QApplication
        from ui.ai_chat_window import AIChat
        from addons.agentic_chatbot.main import AgenticChatbotAddon
        from addons.agentic_chatbot.agent_window import AgentWindow
        
        # Create QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        print("1. Creating AIChat app (no model initially)...")
        
        # Create real AIChat app without model
        real_app = AIChat()
        real_app.model = None  # Start with no model
        
        print("   ✓ AIChat app created without model")
        
        print("2. Creating addon...")
        
        # Create addon
        addon = AgenticChatbotAddon(real_app)
        if not addon.start():
            print("   ❌ Failed to start addon")
            return False
        
        print("   ✓ Addon started")
        
        print("3. Creating agent window...")
        
        # Create agent window
        agent_window = AgentWindow(addon)
        
        print("   ✓ Agent window created")
        
        print("4. Testing initial state (no model)...")
        
        # Test model detection with no model
        model_detected = agent_window._is_model_loaded()
        status_text = agent_window.model_status_label.text()
        
        print(f"   - Model detected: {model_detected}")
        print(f"   - UI status: {status_text}")
        
        if model_detected or "Ready" in status_text:
            print("   ⚠️  WARNING: Model detected when none should be present")
        
        print("5. Simulating model loading...")
        
        # Create and "load" a mock Llama model
        mock_model = Mock()
        mock_model.__class__.__name__ = 'Llama'
        mock_model.__call__ = Mock(return_value={"choices": [{"text": "Test"}]})
        
        # Set the model in the app
        real_app.model = mock_model
        
        # Emit the model_loaded signal
        real_app.model_loaded.emit(mock_model)
        
        print("   ✓ Model loaded and signal emitted")
        
        print("6. Testing after model loading...")
        
        # Test model detection after loading
        model_detected_after = agent_window._is_model_loaded()
        status_text_after = agent_window.model_status_label.text()
        
        print(f"   - Model detected: {model_detected_after}")
        print(f"   - UI status: {status_text_after}")
        
        # Final result
        if not model_detected and model_detected_after and "Ready" in status_text_after:
            print("\n✅ SUCCESS: Model loading workflow working correctly")
            return True
        else:
            print(f"\n❌ FAILED: Model loading workflow not working")
            print(f"   - Initial detection: {model_detected}")
            print(f"   - After loading detection: {model_detected_after}")
            print(f"   - Final UI status: {status_text_after}")
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
        ("Llama Model Detection", test_llama_model_detection),
        ("Model Loading Workflow", test_model_loading_workflow)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"Running: {test_name}")
        print('='*60)
        
        try:
            if test_func():
                passed += 1
                print(f"\n✅ PASSED: {test_name}")
            else:
                print(f"\n❌ FAILED: {test_name}")
        except Exception as e:
            print(f"\n💥 ERROR: {test_name} - {e}")
    
    print(f"\n{'='*60}")
    print(f"SUMMARY: {passed}/{total} tests passed")
    print('='*60)
    
    if passed == total:
        print("🎉 All tests passed! Model detection should work with real models.")
        print("\nIf you're still having issues:")
        print("1. Make sure you load a model in the main window first")
        print("2. Click the refresh button (🔄) in the agent window")
        print("3. Check the console for debug messages")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)