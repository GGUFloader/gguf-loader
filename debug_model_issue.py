#!/usr/bin/env python3
"""
Debug Model Issue - Test the complete workflow to identify the specific problem
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

def debug_complete_workflow():
    """Debug the complete workflow from UI to model generation."""
    print("Debugging complete workflow...")
    
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QTimer, QEventLoop
        from addons.agentic_chatbot.main import AgenticChatbotAddon
        from addons.agentic_chatbot.agent_window import AgentWindow
        
        # Create QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # Create mock GGUF app with model
        mock_app = Mock()
        
        # Create a more realistic mock model
        mock_model = Mock()
        
        def mock_model_call(prompt, max_tokens=100, temperature=0.1, stream=True, stop=None, **kwargs):
            print(f"  - Model called with prompt length: {len(prompt)}")
            print(f"  - Model parameters: max_tokens={max_tokens}, temperature={temperature}")
            
            # Simulate token generation
            tokens = ["I", " understand", " your", " request", ".", " How", " can", " I", " help", " you", "?"]
            for token in tokens:
                yield {"choices": [{"text": token}]}
        
        mock_model.side_effect = mock_model_call
        mock_app.model = mock_model
        
        # Add signals
        mock_app.model_loaded = Mock()
        mock_app.generation_finished = Mock()
        mock_app.generation_error = Mock()
        
        print("- Mock GGUF app with model created")
        
        # Create and start addon
        addon = AgenticChatbotAddon(mock_app)
        if not addon.start():
            print("- Failed to start addon")
            return False
        
        print("- Addon started")
        
        # Create agent window
        agent_window = AgentWindow(addon)
        print("- Agent window created")
        
        # Verify model is detected
        if not agent_window._is_model_loaded():
            print("- ERROR: Model not detected in agent window")
            return False
        
        print("- Model detected in agent window")
        
        # Create session
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "test_workspace"
            workspace.mkdir()
            
            session_id = addon.create_agent_session(str(workspace))
            if not session_id:
                print("- Failed to create session")
                return False
            
            print(f"- Session created: {session_id[:8]}...")
            
            # Set session in agent window
            agent_window._current_session_id = session_id
            agent_window._current_workspace = workspace
            
            # Get agent loop
            agent_loop = addon.get_agent_loop()
            if not agent_loop:
                print("- ERROR: No agent loop available")
                return False
            
            print("- Agent loop retrieved")
            
            # Set session for agent loop
            agent_loop.set_session(session_id, str(workspace))
            print("- Session set for agent loop")
            
            # Test direct agent loop message processing
            print("\n- Testing direct agent loop processing...")
            
            test_message = "Hello, can you help me list the files in this directory?"
            
            # Set up signal handlers to capture results
            response_received = []
            error_received = []
            
            def on_response(response):
                print(f"  - Response received: {response[:50]}...")
                response_received.append(response)
            
            def on_error(error):
                print(f"  - Error received: {error}")
                error_received.append(error)
            
            agent_loop.response_generated.connect(on_response)
            agent_loop.error_occurred.connect(on_error)
            
            # Process message
            print(f"  - Processing message: '{test_message}'")
            
            try:
                # This should trigger the complete workflow
                agent_loop.process_user_message(test_message)
                
                # Wait for processing to complete
                print("  - Waiting for processing to complete...")
                
                # Create event loop to wait for signals
                loop = QEventLoop()
                timer = QTimer()
                timer.timeout.connect(loop.quit)
                timer.start(10000)  # 10 second timeout
                
                def check_completion():
                    if response_received or error_received or not agent_loop.is_processing():
                        loop.quit()
                
                completion_timer = QTimer()
                completion_timer.timeout.connect(check_completion)
                completion_timer.start(100)  # Check every 100ms
                
                loop.exec()
                
                timer.stop()
                completion_timer.stop()
                
                # Check results
                if response_received:
                    print(f"  - SUCCESS: Response generated: {response_received[0][:100]}...")
                    return True
                elif error_received:
                    print(f"  - ERROR: Agent loop error: {error_received[0]}")
                    return False
                else:
                    print("  - ERROR: No response or error received (timeout)")
                    return False
                    
            except Exception as e:
                print(f"  - ERROR: Exception during processing: {e}")
                import traceback
                traceback.print_exc()
                return False
        
    except Exception as e:
        print(f"- Error: {e}")
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

def debug_model_access():
    """Debug model access specifically."""
    print("\nDebugging model access...")
    
    try:
        from addons.agentic_chatbot.agent_loop import AgentLoop
        from addons.agentic_chatbot.tool_registry import ToolRegistry
        from models.chat_generator import ChatGenerator
        
        # Create mock model
        mock_model = Mock()
        
        def mock_model_call(prompt, max_tokens=100, temperature=0.1, stream=True, stop=None, **kwargs):
            print(f"  - Model accessed successfully")
            print(f"  - Prompt length: {len(prompt)}")
            tokens = ["Test", " response"]
            for token in tokens:
                yield {"choices": [{"text": token}]}
        
        mock_model.side_effect = mock_model_call
        
        # Create mock GGUF app
        mock_app = Mock()
        mock_app.model = mock_model
        
        print("- Mock model and app created")
        
        # Test ChatGenerator directly
        print("- Testing ChatGenerator directly...")
        
        try:
            chat_gen = ChatGenerator(
                model=mock_model,
                prompt="Test prompt",
                chat_history=[],
                max_tokens=100,
                temperature=0.1
            )
            
            response_text = ""
            
            def on_token(token):
                nonlocal response_text
                response_text += token
            
            chat_gen.token_received.connect(on_token)
            chat_gen.run()
            
            if response_text:
                print(f"  - ChatGenerator SUCCESS: {response_text}")
            else:
                print("  - ChatGenerator FAILED: No response")
                return False
                
        except Exception as e:
            print(f"  - ChatGenerator ERROR: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # Test agent loop model access
        print("- Testing agent loop model access...")
        
        try:
            tool_registry = ToolRegistry(None, None, None)
            config = {"max_tokens": 2048, "temperature": 0.1}
            
            agent_loop = AgentLoop(mock_app, tool_registry, config)
            
            # Check model access
            if agent_loop.gguf_app and hasattr(agent_loop.gguf_app, 'model') and agent_loop.gguf_app.model:
                print("  - Agent loop can access model")
            else:
                print("  - Agent loop CANNOT access model")
                return False
            
            # Test response generation
            with tempfile.TemporaryDirectory() as temp_dir:
                workspace = Path(temp_dir) / "test_workspace"
                workspace.mkdir()
                
                agent_loop.set_session("test_session", str(workspace))
                
                print("  - Testing response generation...")
                response_data = agent_loop._generate_agent_response("Hello")
                
                if response_data and "response" in response_data:
                    print(f"  - Response generation SUCCESS: {response_data['response'][:50]}...")
                else:
                    print(f"  - Response generation FAILED: {response_data}")
                    return False
                    
        except Exception as e:
            print(f"  - Agent loop ERROR: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        return True
        
    except Exception as e:
        print(f"- Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run debugging tests."""
    print("=== Debugging Model Issue ===")
    
    # Enable more detailed logging
    logging.basicConfig(level=logging.DEBUG)
    
    tests = [
        ("Model Access Debug", debug_model_access),
        ("Complete Workflow Debug", debug_complete_workflow)
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
    
    print(f"\n=== DEBUG SUMMARY ===")
    print(f"Tests passed: {passed}/{total}")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)