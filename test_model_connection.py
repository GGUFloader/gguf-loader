#!/usr/bin/env python3
"""
Test Model Connection for Agentic Chatbot

This test checks the connection between the agentic chatbot and GGUF loader model.
"""

import sys
import os
import tempfile
import logging
from pathlib import Path
from unittest.mock import Mock, MagicMock

# Add current directory to path for imports
sys.path.insert(0, '.')

def test_model_connection_simulation():
    """Test model connection with realistic GGUF app simulation."""
    print("Testing model connection simulation...")
    
    try:
        from addons.agentic_chatbot.main import AgenticChatbotAddon
        from addons.agentic_chatbot.agent_loop import AgentLoop
        
        # Create a realistic mock GGUF app that simulates AIChat
        mock_app = Mock()
        
        # Simulate the model being None initially (no model loaded)
        mock_app.model = None
        
        # Add the signals that AIChat has
        mock_app.model_loaded = Mock()
        mock_app.generation_finished = Mock()
        mock_app.generation_error = Mock()
        mock_app.model_unloaded = Mock()
        mock_app.generation_started = Mock()
        
        # Create addon
        addon = AgenticChatbotAddon(mock_app)
        print("- Addon created with no model")
        
        # Start addon
        if not addon.start():
            print("- Failed to start addon")
            return False
        
        print("- Addon started successfully")
        
        # Test agent loop with no model
        agent_loop = addon.get_agent_loop()
        if agent_loop:
            print("- Agent loop retrieved")
            
            # Test model availability check
            try:
                # This should detect no model available
                if not agent_loop.gguf_app or not hasattr(agent_loop.gguf_app, 'model') or not agent_loop.gguf_app.model:
                    print("- Correctly detected no model available")
                else:
                    print("- Incorrectly detected model available")
                    return False
            except Exception as e:
                print(f"- Error checking model availability: {e}")
                return False
        else:
            print("- Failed to retrieve agent loop")
            return False
        
        # Now simulate loading a model
        print("\n- Simulating model loading...")
        mock_model = Mock()
        mock_model.return_value = "Test response from model"
        mock_app.model = mock_model
        
        # Simulate the model_loaded signal
        addon._on_model_loaded(mock_model)
        print("- Model loaded signal sent")
        
        # Test model availability check again
        if not agent_loop.gguf_app or not hasattr(agent_loop.gguf_app, 'model') or not agent_loop.gguf_app.model:
            print("- Incorrectly detected no model available after loading")
            return False
        else:
            print("- Correctly detected model available after loading")
        
        # Test creating a session with model available
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "test_workspace"
            workspace.mkdir()
            
            session_id = addon.create_agent_session(str(workspace))
            if session_id:
                print("- Session created successfully with model available")
            else:
                print("- Failed to create session with model available")
                return False
        
        # Cleanup
        addon.stop()
        print("- Addon stopped")
        
        return True
        
    except Exception as e:
        print(f"- Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_chat_generator_integration():
    """Test ChatGenerator integration with mock model."""
    print("\nTesting ChatGenerator integration...")
    
    try:
        from models.chat_generator import ChatGenerator
        from unittest.mock import Mock, patch
        
        # Create a mock model that behaves like llama-cpp-python
        mock_model = Mock()
        
        # Mock the model call to return tokens
        def mock_model_call(prompt, max_tokens=100, temperature=0.1, **kwargs):
            # Simulate token generation
            tokens = ["Hello", " there", "!", " How", " can", " I", " help", "?"]
            for token in tokens:
                yield {"choices": [{"text": token}]}
        
        mock_model.side_effect = mock_model_call
        
        print("- Mock model created")
        
        # Test ChatGenerator creation
        try:
            chat_generator = ChatGenerator(
                model=mock_model,
                prompt="Hello, AI!",
                chat_history=[],
                max_tokens=100,
                temperature=0.1,
                system_prompt_name="assistant"
            )
            print("- ChatGenerator created successfully")
        except Exception as e:
            print(f"- ChatGenerator creation failed: {e}")
            return False
        
        # Test if ChatGenerator has the expected interface
        if hasattr(chat_generator, 'token_received'):
            print("- ChatGenerator has token_received signal")
        else:
            print("- ChatGenerator missing token_received signal")
            return False
        
        if hasattr(chat_generator, 'finished'):
            print("- ChatGenerator has finished signal")
        else:
            print("- ChatGenerator missing finished signal")
            return False
        
        if hasattr(chat_generator, 'error'):
            print("- ChatGenerator has error signal")
        else:
            print("- ChatGenerator missing error signal")
            return False
        
        if hasattr(chat_generator, 'run'):
            print("- ChatGenerator has run method")
        else:
            print("- ChatGenerator missing run method")
            return False
        
        return True
        
    except Exception as e:
        print(f"- Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_model_integration_workflow():
    """Test the complete model integration workflow."""
    print("\nTesting complete model integration workflow...")
    
    try:
        from addons.agentic_chatbot.main import AgenticChatbotAddon
        from addons.agentic_chatbot.agent_loop import ModelNotAvailableError
        
        # Create mock GGUF app
        mock_app = Mock()
        mock_app.model = None
        mock_app.model_loaded = Mock()
        mock_app.generation_finished = Mock()
        mock_app.generation_error = Mock()
        
        # Create addon
        addon = AgenticChatbotAddon(mock_app)
        addon.start()
        
        print("- Addon started")
        
        # Get agent loop
        agent_loop = addon.get_agent_loop()
        
        # Set up a session
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "test_workspace"
            workspace.mkdir()
            
            session_id = addon.create_agent_session(str(workspace))
            agent_loop.set_session(session_id, str(workspace))
            
            print("- Session created and set")
            
            # Test response generation without model (should fail gracefully)
            try:
                response_data = agent_loop._generate_agent_response("Hello")
                print("- Response generation without model handled gracefully")
                
                # Check if it's an error response
                if "error" in response_data.get("reasoning", "").lower() or "no model" in response_data.get("response", "").lower():
                    print("- Correctly indicated no model available")
                else:
                    print("- Did not properly indicate no model available")
                    return False
                    
            except ModelNotAvailableError:
                print("- Correctly raised ModelNotAvailableError")
            except Exception as e:
                print(f"- Unexpected error: {e}")
                return False
            
            # Now add a model
            mock_model = Mock()
            mock_app.model = mock_model
            
            # Notify agent loop of model
            agent_loop.on_model_loaded(mock_model)
            print("- Model loaded notification sent")
            
            # Test that model is now available
            if agent_loop.gguf_app.model:
                print("- Model now available in agent loop")
            else:
                print("- Model still not available in agent loop")
                return False
        
        # Cleanup
        addon.stop()
        print("- Addon stopped")
        
        return True
        
    except Exception as e:
        print(f"- Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all model connection tests."""
    print("=== Model Connection Tests ===")
    
    # Suppress logging during tests
    logging.getLogger().setLevel(logging.CRITICAL)
    
    tests = [
        ("Model Connection Simulation", test_model_connection_simulation),
        ("ChatGenerator Integration", test_chat_generator_integration),
        ("Model Integration Workflow", test_model_integration_workflow)
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
    
    print(f"\n=== MODEL CONNECTION TEST SUMMARY ===")
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("ALL MODEL CONNECTION TESTS PASSED!")
        return True
    else:
        print("SOME MODEL CONNECTION TESTS FAILED")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)