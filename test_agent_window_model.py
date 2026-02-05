#!/usr/bin/env python3
"""
Test Agent Window Model Integration

This test specifically checks if the agent window can properly use the model.
"""

import sys
import os
import tempfile
import logging
from pathlib import Path
from unittest.mock import Mock, MagicMock

# Add current directory to path for imports
sys.path.insert(0, '.')

def test_agent_window_model_integration():
    """Test agent window with model integration."""
    print("Testing agent window model integration...")
    
    try:
        # Import required modules
        from addons.agentic_chatbot.main import AgenticChatbotAddon
        from addons.agentic_chatbot.agent_window import AgentWindow
        from models.chat_generator import ChatGenerator
        
        # Create a realistic mock GGUF app
        mock_app = Mock()
        
        # Create a mock model that behaves like llama-cpp-python
        mock_model = Mock()
        
        # Mock the model call to return tokens
        def mock_model_call(prompt, max_tokens=100, temperature=0.1, stream=True, stop=None, **kwargs):
            # Simulate token generation
            tokens = ["Hello", " there", "!", " How", " can", " I", " help", " you", " today", "?"]
            for token in tokens:
                yield {"choices": [{"text": token}]}
        
        mock_model.side_effect = mock_model_call
        mock_app.model = mock_model
        
        # Add the signals that AIChat has
        mock_app.model_loaded = Mock()
        mock_app.generation_finished = Mock()
        mock_app.generation_error = Mock()
        mock_app.model_unloaded = Mock()
        mock_app.generation_started = Mock()
        
        print("- Mock GGUF app with model created")
        
        # Create addon
        addon = AgenticChatbotAddon(mock_app)
        
        # Start addon
        if not addon.start():
            print("- Failed to start addon")
            return False
        
        print("- Addon started successfully")
        
        # Get agent loop
        agent_loop = addon.get_agent_loop()
        if not agent_loop:
            print("- Failed to get agent loop")
            return False
        
        print("- Agent loop retrieved")
        
        # Create a session
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "test_workspace"
            workspace.mkdir()
            
            session_id = addon.create_agent_session(str(workspace))
            if not session_id:
                print("- Failed to create session")
                return False
            
            print("- Session created successfully")
            
            # Set session for agent loop
            agent_loop.set_session(session_id, str(workspace))
            print("- Session set for agent loop")
            
            # Test ChatGenerator creation with the mock model
            try:
                chat_generator = ChatGenerator(
                    model=mock_model,
                    prompt="Hello, how are you?",
                    chat_history=[],
                    max_tokens=100,
                    temperature=0.1,
                    system_prompt_name="assistant"
                )
                print("- ChatGenerator created successfully with mock model")
                
                # Test if we can run the generator
                response_text = ""
                
                def on_token(token):
                    nonlocal response_text
                    response_text += token
                
                def on_finished():
                    print(f"- Generation finished, response: '{response_text}'")
                
                def on_error(error):
                    print(f"- Generation error: {error}")
                
                chat_generator.token_received.connect(on_token)
                chat_generator.finished.connect(on_finished)
                chat_generator.error.connect(on_error)
                
                # Run generation
                chat_generator.run()
                
                if response_text:
                    print("- ChatGenerator produced response successfully")
                else:
                    print("- ChatGenerator did not produce response")
                    return False
                
            except Exception as e:
                print(f"- ChatGenerator test failed: {e}")
                import traceback
                traceback.print_exc()
                return False
            
            # Test agent loop response generation
            try:
                print("- Testing agent loop response generation...")
                
                # This should work now that we have a model
                response_data = agent_loop._generate_agent_response("Hello, can you help me?")
                
                if response_data:
                    print("- Agent loop generated response successfully")
                    print(f"- Response keys: {list(response_data.keys())}")
                    
                    if "response" in response_data and response_data["response"]:
                        print(f"- Response content: '{response_data['response'][:50]}...'")
                    else:
                        print("- No response content found")
                        return False
                else:
                    print("- Agent loop did not generate response")
                    return False
                    
            except Exception as e:
                print(f"- Agent loop response generation failed: {e}")
                import traceback
                traceback.print_exc()
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

def test_agent_loop_model_access():
    """Test direct agent loop model access."""
    print("\nTesting direct agent loop model access...")
    
    try:
        from addons.agentic_chatbot.agent_loop import AgentLoop
        from addons.agentic_chatbot.tool_registry import ToolRegistry
        
        # Create mock model
        mock_model = Mock()
        
        def mock_model_call(prompt, max_tokens=100, temperature=0.1, stream=True, stop=None, **kwargs):
            tokens = ["Test", " response", " from", " model"]
            for token in tokens:
                yield {"choices": [{"text": token}]}
        
        mock_model.side_effect = mock_model_call
        
        # Create mock GGUF app
        mock_app = Mock()
        mock_app.model = mock_model
        
        # Create tool registry
        tool_registry = ToolRegistry(None, None, None)
        
        # Create agent loop
        config = {
            "max_iterations": 15,
            "max_tool_calls_per_turn": 5,
            "temperature": 0.1,
            "max_tokens": 2048
        }
        
        agent_loop = AgentLoop(mock_app, tool_registry, config)
        print("- Agent loop created")
        
        # Check model access
        if agent_loop.gguf_app and hasattr(agent_loop.gguf_app, 'model') and agent_loop.gguf_app.model:
            print("- Agent loop can access model")
        else:
            print("- Agent loop cannot access model")
            return False
        
        # Test model availability check
        try:
            if not agent_loop.gguf_app or not hasattr(agent_loop.gguf_app, 'model') or not agent_loop.gguf_app.model:
                print("- Model availability check failed (should not happen)")
                return False
            else:
                print("- Model availability check passed")
        except Exception as e:
            print(f"- Model availability check error: {e}")
            return False
        
        return True
        
    except Exception as e:
        print(f"- Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run agent window model integration tests."""
    print("=== Agent Window Model Integration Tests ===")
    
    # Suppress logging during tests
    logging.getLogger().setLevel(logging.CRITICAL)
    
    tests = [
        ("Agent Loop Model Access", test_agent_loop_model_access),
        ("Agent Window Model Integration", test_agent_window_model_integration)
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
    
    print(f"\n=== AGENT WINDOW MODEL TEST SUMMARY ===")
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("ALL AGENT WINDOW MODEL TESTS PASSED!")
        return True
    else:
        print("SOME AGENT WINDOW MODEL TESTS FAILED")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)