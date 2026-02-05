#!/usr/bin/env python3
"""
Test Debug Model Detection

This script tests the agent window with debug output to see why model detection fails.
"""

import sys
import os
import tempfile
import logging
from pathlib import Path
from unittest.mock import Mock, MagicMock

# Add current directory to path for imports
sys.path.insert(0, '.')

def test_debug_model_detection():
    """Test model detection with debug output."""
    print("=== Testing Model Detection with Debug Output ===\n")
    
    try:
        from PySide6.QtWidgets import QApplication
        from addons.agentic_chatbot.main import AgenticChatbotAddon
        from addons.agentic_chatbot.agent_window import AgentWindow
        
        # Create QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        print("1. Creating mock GGUF app with model...")
        
        # Create a realistic mock GGUF app
        mock_app = Mock()
        
        # Create a mock model
        mock_model = Mock()
        mock_model.side_effect = lambda *args, **kwargs: iter([{"choices": [{"text": "test"}]}])
        mock_app.model = mock_model
        
        # Add signals
        mock_app.model_loaded = Mock()
        mock_app.generation_finished = Mock()
        mock_app.generation_error = Mock()
        
        print(f"   Mock app created: {mock_app}")
        print(f"   Mock model: {mock_model}")
        
        print("\n2. Creating and starting addon...")
        
        # Create addon
        addon = AgenticChatbotAddon(mock_app)
        
        print(f"   Addon created: {addon}")
        print(f"   Addon.gguf_app: {addon.gguf_app}")
        print(f"   Addon.gguf_app.model: {addon.gguf_app.model}")
        
        # Start addon
        if not addon.start():
            print("   ERROR: Failed to start addon")
            return False
        
        print("   Addon started successfully")
        
        print("\n3. Creating agent window...")
        
        # Create agent window
        agent_window = AgentWindow(addon)
        
        print(f"   Agent window created: {agent_window}")
        print(f"   Agent window addon: {agent_window.addon}")
        
        print("\n4. Testing initial model detection...")
        
        # Test model detection
        model_loaded = agent_window._is_model_loaded()
        print(f"   Initial model detection result: {model_loaded}")
        
        print("\n5. Testing model status update...")
        
        # Update model status
        agent_window._update_model_status()
        
        print(f"   Model status label text: {agent_window.model_status_label.text()}")
        print(f"   Send button enabled: {agent_window._send_btn.isEnabled()}")
        
        print("\n6. Simulating model loaded signal...")
        
        # Simulate model loaded signal
        agent_window._on_model_loaded(mock_model)
        
        print(f"   After signal - Model status label: {agent_window.model_status_label.text()}")
        print(f"   After signal - Send button enabled: {agent_window._send_btn.isEnabled()}")
        
        print("\n7. Testing session creation and message sending...")
        
        # Create session
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "test_workspace"
            workspace.mkdir()
            
            session_id = addon.create_agent_session(str(workspace))
            if session_id:
                print(f"   Session created: {session_id[:8]}...")
                
                # Set session in agent window
                agent_window._current_session_id = session_id
                agent_window._current_workspace = workspace
                
                # Set test message
                agent_window._input_field.setPlainText("Hello, test message")
                
                print("\n8. Attempting to send message (this will trigger debug output)...")
                
                # Try to send message (this will show debug output)
                agent_window._send_message()
                
            else:
                print("   ERROR: Failed to create session")
                return False
        
        print("\n9. Cleanup...")
        
        # Cleanup
        agent_window.close()
        addon.stop()
        
        print("   Cleanup completed")
        
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_real_app_structure():
    """Test what the real GGUF app structure looks like."""
    print("\n=== Testing Real App Structure ===\n")
    
    try:
        # Try to import the main GGUF app
        try:
            import main
            print("1. Main GGUF module imported successfully")
            
            # Check what classes are available
            if hasattr(main, 'AIChat'):
                print("   Found AIChat class")
                
                # Create a mock instance to see its structure
                from unittest.mock import Mock
                mock_ai_chat = Mock(spec=main.AIChat)
                
                # Check common attributes
                attrs_to_check = ['model', 'model_loaded', 'generation_finished', 'generation_error']
                for attr in attrs_to_check:
                    if hasattr(main.AIChat, attr):
                        print(f"   AIChat has attribute: {attr}")
                    else:
                        print(f"   AIChat missing attribute: {attr}")
                        
            else:
                print("   AIChat class not found in main module")
                
        except ImportError as e:
            print(f"1. Could not import main GGUF module: {e}")
            print("   This is expected in test environment")
        
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def main():
    """Run debug tests."""
    print("=== Debug Model Detection Tests ===")
    
    # Suppress some logging but keep our debug prints
    logging.getLogger('addons.agentic_chatbot').setLevel(logging.WARNING)
    
    tests = [
        ("Real App Structure", test_real_app_structure),
        ("Debug Model Detection", test_debug_model_detection)
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
    
    print(f"\n=== DEBUG TEST SUMMARY ===")
    print(f"Tests passed: {passed}/{total}")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)