#!/usr/bin/env python3
"""
Test Agent Window UI Model Detection

This test checks if the agent window UI properly detects and responds to model loading.
"""

import sys
import os
import tempfile
import logging
from pathlib import Path
from unittest.mock import Mock, MagicMock

# Add current directory to path for imports
sys.path.insert(0, '.')

def test_agent_window_model_detection():
    """Test agent window model detection and UI state."""
    print("Testing agent window model detection...")
    
    try:
        from PySide6.QtWidgets import QApplication
        from addons.agentic_chatbot.main import AgenticChatbotAddon
        from addons.agentic_chatbot.agent_window import AgentWindow
        
        # Create QApplication if it doesn't exist
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # Create a realistic mock GGUF app
        mock_app = Mock()
        mock_app.model = None  # Start with no model
        
        # Add the signals that AIChat has
        mock_app.model_loaded = Mock()
        mock_app.generation_finished = Mock()
        mock_app.generation_error = Mock()
        mock_app.model_unloaded = Mock()
        mock_app.generation_started = Mock()
        
        print("- Mock GGUF app created (no model initially)")
        
        # Create addon
        addon = AgenticChatbotAddon(mock_app)
        
        # Start addon
        if not addon.start():
            print("- Failed to start addon")
            return False
        
        print("- Addon started successfully")
        
        # Create agent window
        agent_window = AgentWindow(addon)
        print("- Agent window created")
        
        # Test initial model status (should be not loaded)
        if agent_window._is_model_loaded():
            print("- ERROR: Agent window incorrectly detects model as loaded initially")
            return False
        else:
            print("- Agent window correctly detects no model initially")
        
        # Check UI state with no model
        if agent_window._send_btn.isEnabled():
            print("- ERROR: Send button should be disabled with no model")
            return False
        else:
            print("- Send button correctly disabled with no model")
        
        # Now simulate loading a model
        print("\n- Simulating model loading...")
        mock_model = Mock()
        
        def mock_model_call(prompt, max_tokens=100, temperature=0.1, stream=True, stop=None, **kwargs):
            tokens = ["Hello", " there", "!", " How", " can", " I", " help", "?"]
            for token in tokens:
                yield {"choices": [{"text": token}]}
        
        mock_model.side_effect = mock_model_call
        mock_app.model = mock_model
        
        # Notify agent window of model loading
        agent_window._on_model_loaded(mock_model)
        print("- Model loaded signal sent to agent window")
        
        # Test model detection after loading
        if not agent_window._is_model_loaded():
            print("- ERROR: Agent window doesn't detect model after loading")
            return False
        else:
            print("- Agent window correctly detects model after loading")
        
        # Check UI state with model loaded
        if not agent_window._send_btn.isEnabled():
            print("- ERROR: Send button should be enabled with model loaded")
            return False
        else:
            print("- Send button correctly enabled with model loaded")
        
        # Test creating a session
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "test_workspace"
            workspace.mkdir()
            
            session_id = addon.create_agent_session(str(workspace))
            if not session_id:
                print("- Failed to create session")
                return False
            
            print("- Session created successfully")
            
            # Set current session in agent window
            agent_window._current_session_id = session_id
            agent_window._current_workspace = workspace
            
            # Test that we can now send a message (simulate)
            test_message = "Hello, can you help me?"
            agent_window._input_field.setPlainText(test_message)
            
            # Check if send button is still enabled with session and model
            if not agent_window._send_btn.isEnabled():
                print("- ERROR: Send button should be enabled with model and session")
                return False
            else:
                print("- Send button correctly enabled with model and session")
        
        # Cleanup
        agent_window.close()
        addon.stop()
        print("- Cleanup completed")
        
        return True
        
    except Exception as e:
        print(f"- Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_model_status_updates():
    """Test model status updates in agent window."""
    print("\nTesting model status updates...")
    
    try:
        from PySide6.QtWidgets import QApplication
        from addons.agentic_chatbot.main import AgenticChatbotAddon
        from addons.agentic_chatbot.agent_window import AgentWindow
        
        # Create QApplication if it doesn't exist
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # Create mock GGUF app
        mock_app = Mock()
        mock_app.model = None
        mock_app.model_loaded = Mock()
        mock_app.generation_finished = Mock()
        mock_app.generation_error = Mock()
        
        # Create addon and agent window
        addon = AgenticChatbotAddon(mock_app)
        addon.start()
        
        agent_window = AgentWindow(addon)
        print("- Agent window created")
        
        # Test initial model status label
        initial_status = agent_window.model_status_label.text()
        print(f"- Initial model status: {initial_status}")
        
        if "Not loaded" not in initial_status:
            print("- ERROR: Initial status should indicate model not loaded")
            return False
        
        # Update model status
        agent_window._update_model_status()
        updated_status = agent_window.model_status_label.text()
        print(f"- Updated model status: {updated_status}")
        
        # Load model and update
        mock_model = Mock()
        mock_app.model = mock_model
        agent_window._update_model_status()
        
        loaded_status = agent_window.model_status_label.text()
        print(f"- Model loaded status: {loaded_status}")
        
        if "Ready" not in loaded_status:
            print("- ERROR: Status should indicate model ready")
            return False
        else:
            print("- Model status correctly updated to ready")
        
        # Cleanup
        agent_window.close()
        addon.stop()
        
        return True
        
    except Exception as e:
        print(f"- Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run agent window UI tests."""
    print("=== Agent Window UI Model Detection Tests ===")
    
    # Suppress logging during tests
    logging.getLogger().setLevel(logging.CRITICAL)
    
    tests = [
        ("Agent Window Model Detection", test_agent_window_model_detection),
        ("Model Status Updates", test_model_status_updates)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"PASS: {test_name}")
            else:
                print(f"FAIL: {test_name}")
        except Exception as e:
            print(f"ERROR: {test_name} - {e}")
    
    print(f"\n=== AGENT WINDOW UI TEST SUMMARY ===")
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("ALL AGENT WINDOW UI TESTS PASSED!")
        return True
    else:
        print("SOME AGENT WINDOW UI TESTS FAILED")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)