#!/usr/bin/env python3
"""
Test Complete Model Detection Fix - Test the complete workflow with the fix
"""

import sys
import os
import logging

# Add current directory to path for imports
sys.path.insert(0, '.')

def test_complete_workflow():
    """Test the complete workflow from addon registration to model detection."""
    print("=== Testing Complete Model Detection Workflow ===")
    
    try:
        from PySide6.QtWidgets import QApplication, QDialog
        from ui.ai_chat_window import AIChat
        from addons.agentic_chatbot.main import register
        from addons.agentic_chatbot.agent_window import AgentWindow
        from unittest.mock import Mock
        
        # Create QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        print("1. Creating AIChat app and loading model...")
        
        # Create real AIChat app
        real_app = AIChat()
        
        # Simulate model loading
        mock_model = Mock()
        mock_model.__class__.__name__ = 'Llama'
        real_app.model = mock_model
        
        print("   ✓ AIChat app created with loaded model")
        
        print("2. Simulating addon manager behavior...")
        
        # Create dialog to simulate addon manager
        dialog = QDialog(real_app)
        
        # Call register function (this is what addon manager does)
        status_widget = register(dialog)
        
        if status_widget is None:
            print("   ❌ Addon registration failed")
            return False
        
        print("   ✓ Addon registered successfully")
        
        # Get the addon instance
        addon = real_app._agentic_chatbot_addon
        
        print("3. Creating agent window...")
        
        # Create agent window
        agent_window = AgentWindow(addon)
        
        print("   ✓ Agent window created")
        
        print("4. Testing model detection...")
        
        # Test model detection
        model_detected = agent_window._is_model_loaded()
        status_text = agent_window.model_status_label.text()
        
        print(f"   - Model detected: {model_detected}")
        print(f"   - UI status: {status_text}")
        
        if not model_detected:
            print("   ❌ Model not detected")
            return False
        
        if "Ready" not in status_text:
            print("   ❌ UI status not showing ready")
            return False
        
        print("   ✓ Model detected correctly")
        
        print("5. Testing manual refresh...")
        
        # Test manual refresh
        agent_window._refresh_model_status()
        
        status_text_after = agent_window.model_status_label.text()
        print(f"   - UI status after refresh: {status_text_after}")
        
        if "Ready" not in status_text_after:
            print("   ❌ Manual refresh failed")
            return False
        
        print("   ✓ Manual refresh working")
        
        print("6. Testing session creation...")
        
        # Test session creation
        import tempfile
        from pathlib import Path
        
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "test_workspace"
            workspace.mkdir()
            
            # Set workspace in agent window
            agent_window._workspace_selector.setCurrentText(str(workspace))
            
            # Create session
            agent_window._create_session()
            
            if agent_window._current_session_id:
                print("   ✓ Session created successfully")
            else:
                print("   ❌ Session creation failed")
                return False
        
        print("7. Testing model_loaded signal...")
        
        # Test signal emission
        real_app.model_loaded.emit(mock_model)
        
        # Check if signal was handled
        final_status = agent_window.model_status_label.text()
        print(f"   - Final status after signal: {final_status}")
        
        if "Ready" not in final_status:
            print("   ❌ Signal handling failed")
            return False
        
        print("   ✓ Signal handling working")
        
        print("\n✅ SUCCESS: Complete workflow working correctly")
        return True
        
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
            if 'dialog' in locals():
                dialog.close()
            if 'real_app' in locals():
                real_app.close()
        except:
            pass

def test_no_model_scenario():
    """Test behavior when no model is loaded."""
    print("\n=== Testing No Model Scenario ===")
    
    try:
        from PySide6.QtWidgets import QApplication, QDialog
        from ui.ai_chat_window import AIChat
        from addons.agentic_chatbot.main import register
        from addons.agentic_chatbot.agent_window import AgentWindow
        
        # Create QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        print("1. Creating AIChat app without model...")
        
        # Create real AIChat app without model
        real_app = AIChat()
        real_app.model = None  # Explicitly no model
        
        print("   ✓ AIChat app created without model")
        
        print("2. Registering addon...")
        
        # Create dialog and register addon
        dialog = QDialog(real_app)
        status_widget = register(dialog)
        
        if status_widget is None:
            print("   ❌ Addon registration failed")
            return False
        
        print("   ✓ Addon registered successfully")
        
        # Get the addon instance
        addon = real_app._agentic_chatbot_addon
        
        print("3. Creating agent window...")
        
        # Create agent window
        agent_window = AgentWindow(addon)
        
        print("   ✓ Agent window created")
        
        print("4. Testing model detection (should be false)...")
        
        # Test model detection
        model_detected = agent_window._is_model_loaded()
        status_text = agent_window.model_status_label.text()
        
        print(f"   - Model detected: {model_detected}")
        print(f"   - UI status: {status_text}")
        
        if model_detected:
            print("   ❌ Model detected when none should be present")
            return False
        
        if "Not loaded" not in status_text:
            print("   ❌ UI status not showing 'not loaded'")
            return False
        
        print("   ✓ Correctly detected no model")
        
        print("5. Simulating model loading...")
        
        # Load a model
        from unittest.mock import Mock
        mock_model = Mock()
        mock_model.__class__.__name__ = 'Llama'
        real_app.model = mock_model
        
        # Emit signal
        real_app.model_loaded.emit(mock_model)
        
        print("   ✓ Model loaded and signal emitted")
        
        print("6. Testing detection after loading...")
        
        # Test detection again
        model_detected_after = agent_window._is_model_loaded()
        status_text_after = agent_window.model_status_label.text()
        
        print(f"   - Model detected after loading: {model_detected_after}")
        print(f"   - UI status after loading: {status_text_after}")
        
        if not model_detected_after:
            print("   ❌ Model not detected after loading")
            return False
        
        if "Ready" not in status_text_after:
            print("   ❌ UI status not updated after loading")
            return False
        
        print("   ✓ Model correctly detected after loading")
        
        print("\n✅ SUCCESS: No model scenario working correctly")
        return True
        
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
            if 'dialog' in locals():
                dialog.close()
            if 'real_app' in locals():
                real_app.close()
        except:
            pass

def main():
    """Run all tests."""
    # Enable info logging
    logging.basicConfig(level=logging.INFO)
    
    tests = [
        ("Complete Workflow Test", test_complete_workflow),
        ("No Model Scenario Test", test_no_model_scenario)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*70}")
        print(f"Running: {test_name}")
        print('='*70)
        
        try:
            if test_func():
                passed += 1
                print(f"\n✅ PASSED: {test_name}")
            else:
                print(f"\n❌ FAILED: {test_name}")
        except Exception as e:
            print(f"\n💥 ERROR: {test_name} - {e}")
    
    print(f"\n{'='*70}")
    print(f"FINAL SUMMARY: {passed}/{total} tests passed")
    print('='*70)
    
    if passed == total:
        print("🎉 ALL TESTS PASSED!")
        print("\n✨ The model detection issue has been fixed!")
        print("\nWhat was fixed:")
        print("- ✅ Addon register function now correctly finds the main AIChat app")
        print("- ✅ Model detection works when addon is started from UI")
        print("- ✅ Signal connections work properly")
        print("- ✅ Manual refresh button works")
        print("- ✅ Both 'no model' and 'model loaded' scenarios work")
        print("\nYou should now be able to:")
        print("1. Start the app with launch.bat")
        print("2. Load a model in the main window")
        print("3. Start the agentic chatbot addon")
        print("4. See 'Model: Ready' status in the agent window")
    else:
        print("⚠️  Some tests failed. The fix may not be complete.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)