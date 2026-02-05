#!/usr/bin/env python3
"""
Test script for streaming agent functionality.

This script demonstrates the enhanced streaming capabilities of the agentic chatbot,
showing real-time token streaming and process visibility.
"""

import sys
import time
import logging
from pathlib import Path
from unittest.mock import Mock, MagicMock

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, Signal, QObject

# Import the enhanced components
from addons.agentic_chatbot.streaming_handler import StreamingHandler
from addons.agentic_chatbot.agent_window import AgentWindow
from addons.agentic_chatbot.agent_loop import AgentLoop
from addons.agentic_chatbot.tool_registry import ToolRegistry


class MockModel:
    """Mock model for testing streaming functionality."""
    
    def __init__(self):
        self.name = "MockStreamingModel"
    
    def __call__(self, *args, **kwargs):
        return "Mock response for testing streaming"


class MockChatGenerator(QObject):
    """Mock chat generator that simulates streaming tokens."""
    
    token_received = Signal(str)
    finished = Signal()
    error = Signal(str)
    
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.response_text = "I'll help you with that request. Let me analyze what you need and execute the appropriate tools to assist you."
        
    def run(self):
        """Simulate streaming token generation."""
        QTimer.singleShot(100, self._start_streaming)
    
    def _start_streaming(self):
        """Start the streaming simulation."""
        words = self.response_text.split()
        
        def emit_next_word(index=0):
            if index < len(words):
                word = words[index] + " "
                self.token_received.emit(word)
                # Schedule next word
                QTimer.singleShot(150, lambda: emit_next_word(index + 1))
            else:
                self.finished.emit()
        
        emit_next_word()


class MockGGUFApp:
    """Mock GGUF application for testing."""
    
    def __init__(self):
        self.model = MockModel()
        self.model_loaded = Signal()


class MockAddon:
    """Mock addon for testing agent window."""
    
    def __init__(self):
        self.gguf_app = MockGGUFApp()
        self._tool_registry = ToolRegistry({})
        self._agent_loop = None
        
        # Create agent loop with mocked dependencies
        self._setup_agent_loop()
    
    def _setup_agent_loop(self):
        """Setup mock agent loop."""
        config = {
            "max_iterations": 10,
            "max_tool_calls_per_turn": 3,
            "temperature": 0.1,
            "max_tokens": 1024,
            "streaming_buffer_size": 5,
            "streaming_flush_interval": 100,
            "enable_streaming": True
        }
        
        self._agent_loop = AgentLoop(self.gguf_app, self._tool_registry, config)
        
        # Mock the chat generator creation
        original_generate = self._agent_loop._generate_agent_response
        
        def mock_generate(message):
            # Simulate streaming response generation
            self._agent_loop.streaming_handler.add_process_step("mock_generation", "Generating mock response...")
            
            # Simulate token streaming
            response_text = f"I understand your request: '{message}'. Let me help you with that."
            for i, char in enumerate(response_text):
                QTimer.singleShot(i * 50, lambda c=char: self._agent_loop.streaming_handler.add_token(c))
            
            # Complete the step
            QTimer.singleShot(len(response_text) * 50 + 100, 
                            lambda: self._agent_loop.streaming_handler.complete_process_step("mock_generation"))
            
            return {
                "reasoning": "This is a mock reasoning process for testing streaming functionality.",
                "tool_calls": [],
                "response": response_text
            }
        
        self._agent_loop._generate_agent_response = mock_generate
    
    def get_agent_loop(self):
        """Get the agent loop instance."""
        return self._agent_loop
    
    def create_agent_session(self, workspace_path):
        """Create a mock agent session."""
        session_id = f"test_session_{int(time.time())}"
        if self._agent_loop:
            self._agent_loop.set_session(session_id, workspace_path)
        return session_id


def test_streaming_functionality():
    """Test the streaming functionality of the agent."""
    
    # Setup logging
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)
    
    # Create Qt application
    app = QApplication(sys.argv)
    
    # Create mock addon
    addon = MockAddon()
    
    # Create agent window
    agent_window = AgentWindow(addon)
    
    # Show the window
    agent_window.show()
    
    # Simulate automatic session creation and message sending for demo
    def demo_interaction():
        logger.info("Starting demo interaction...")
        
        # Create session
        agent_window._workspace_selector.setCurrentText("./test_workspace")
        agent_window._create_session()
        
        # Wait a bit then send a test message
        QTimer.singleShot(2000, lambda: send_test_message())
    
    def send_test_message():
        logger.info("Sending test message...")
        agent_window._input_field.setPlainText("Hello! Can you help me create a simple Python script?")
        agent_window._send_message()
        
        # Send another message after a delay
        QTimer.singleShot(8000, lambda: send_second_message())
    
    def send_second_message():
        logger.info("Sending second test message...")
        agent_window._input_field.setPlainText("What tools do you have available?")
        agent_window._send_message()
    
    # Start demo after window is shown
    QTimer.singleShot(1000, demo_interaction)
    
    # Run the application
    logger.info("Starting streaming agent test application...")
    return app.exec()


if __name__ == "__main__":
    print("🚀 Testing Enhanced Streaming Agent Functionality")
    print("=" * 60)
    print("This test demonstrates:")
    print("• Real-time token streaming")
    print("• Process step visibility")
    print("• Tool execution monitoring")
    print("• Enhanced user experience")
    print("=" * 60)
    
    try:
        exit_code = test_streaming_functionality()
        print(f"\n✅ Test completed with exit code: {exit_code}")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)