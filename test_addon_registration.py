#!/usr/bin/env python3
"""
Test Addon Registration - Test the fixed register function
"""

import sys
import os
import logging

# Add current directory to path for imports
sys.path.insert(0, '.')

def test_register_with_dialog_parent():
    """Test register function when called with dialog as parent."""
    print("=== Testing Register Function with Dialog Parent ===")
    
    try:
        from PySide6.QtWidgets import QApplication, QDialog
        from ui.ai_chat_window import AIChat
        from addons.agentic_chatbot.main import register
        from unittest.mock import Mock
        
        # Create QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        print("1. Creating real AIChat app...")
        
        # Create real AIChat app
        real_app = AIChat()
        
        # Set a mock model to simulate loaded state
        mock_model = Mock()
        mock_model.__class__.__name__ = 'Llama'
        real_app.model = mock_model
        
        print("   ✓ AIChat app created with model")
        
        print("2. Creating dialog (simulating addon manager behavior)...")
        
        # Create a dialog to simulate what addon manager does
        dialog = QDialog(real_app)
        dialog.setWindowTitle("Test Dialog")
        
        print("   ✓ Dialog created with AIChat as parent")
        
        print("3. Testing register function with dialog as parent...")
        
        # Call register function with dialog as parent (this is what addon manager does)
        status_widget = register(dialog)
        
        if status_widget is None:
            print("   ❌ Register function returned None")
            return False
        
        print("   ✓ Register function returned status widget")
        
        print("4. Verifying addon was created correctly...")
        
        # Check if addon was stored in the real app (not the dialog)
        if hasattr(real_app, '_agentic_chatbot_addon'):
            addon = real_app._agentic_chatbot_addon
            print(f"   ✓ Addon stored in real app: {addon}")
            
            # Check if addon has correct gguf_app reference
            if hasattr(addon, 'gguf_app') and addon.gguf_app is real_app:
                print("   ✓ Addon has correct gguf_app reference")
            else:
                print("   ❌ Addon has incorrect gguf_app reference")
                return False
        else:
            print("   ❌ Addon not stored in real app")
            return False
        
        print("5. Testing model detection...")
        
        # Test if the addon can detect the model
        if hasattr(addon, 'gguf_app') and hasattr(addon.gguf_app, 'model'):
            detected_model = addon.gguf_app.model
            print(f"   ✓ Addon can access model: {detected_model}")
            
            if detected_model is mock_model:
                print("   ✓ Model reference is correct")
            else:
                print("   ❌ Model reference is incorrect")
                return False
        else:
            print("   ❌ Addon cannot access model")
            return False
        
        print("\n✅ SUCCESS: Register function works correctly with dialog parent")
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup
        try:
            if 'addon' in locals() and addon:
                addon.stop()
            if 'dialog' in locals():
                dialog.close()
            if 'real_app' in locals():
                real_app.close()
        except:
            pass

def test_register_with_direct_parent():
    """Test register function when called with AIChat directly as parent."""
    print("\n=== Testing Register Function with Direct Parent ===")
    
    try:
        from PySide6.QtWidgets import QApplication
        from ui.ai_chat_window import AIChat
        from addons.agentic_chatbot.main import register
        from unittest.mock import Mock
        
        # Create QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        print("1. Creating real AIChat app...")
        
        # Create real AIChat app
        real_app = AIChat()
        
        # Set a mock model to simulate loaded state
        mock_model = Mock()
        mock_model.__class__.__name__ = 'Llama'
        real_app.model = mock_model
        
        print("   ✓ AIChat app created with model")
        
        print("2. Testing register function with AIChat directly as parent...")
        
        # Call register function with real app as parent (ideal case)
        status_widget = register(real_app)
        
        if status_widget is None:
            print("   ❌ Register function returned None")
            return False
        
        print("   ✓ Register function returned status widget")
        
        print("3. Verifying addon was created correctly...")
        
        # Check if addon was stored in the real app
        if hasattr(real_app, '_agentic_chatbot_addon'):
            addon = real_app._agentic_chatbot_addon
            print(f"   ✓ Addon stored in real app: {addon}")
            
            # Check if addon has correct gguf_app reference
            if hasattr(addon, 'gguf_app') and addon.gguf_app is real_app:
                print("   ✓ Addon has correct gguf_app reference")
            else:
                print("   ❌ Addon has incorrect gguf_app reference")
                return False
        else:
            print("   ❌ Addon not stored in real app")
            return False
        
        print("\n✅ SUCCESS: Register function works correctly with direct parent")
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup
        try:
            if 'addon' in locals() and addon:
                addon.stop()
            if 'real_app' in locals():
                real_app.close()
        except:
            pass

def main():
    """Run all tests."""
    # Enable debug logging
    logging.basicConfig(level=logging.INFO)
    
    tests = [
        ("Direct Parent Test", test_register_with_direct_parent),
        ("Dialog Parent Test", test_register_with_dialog_parent)
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
        print("🎉 All tests passed! Register function should work correctly.")
        print("\nThe addon should now properly detect loaded models when started from the UI.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)