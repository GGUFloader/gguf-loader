#!/usr/bin/env python3
"""
Example usage of the enhanced streaming agentic chatbot.

This example shows how to integrate and use the streaming features
in your own applications.
"""

import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QTextEdit
from PySide6.QtCore import QTimer

from addons.agentic_chatbot.agent_window import AgentWindow
from addons.agentic_chatbot.streaming_handler import StreamingHandler


class StreamingChatbotExample(QMainWindow):
    """Example application showing streaming chatbot integration."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Streaming Agentic Chatbot Example")
        self.setGeometry(100, 100, 1200, 800)
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Create mock addon (in real usage, this would be your actual addon)
        self.addon = self._create_mock_addon()
        
        # Setup UI
        self._setup_ui()
        
        # Connect streaming signals for monitoring
        self._connect_streaming_signals()
    
    def _setup_ui(self):
        """Setup the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Add instructions
        instructions = QTextEdit()
        instructions.setMaximumHeight(100)
        instructions.setPlainText(
            "This example demonstrates the streaming agentic chatbot features:\n"
            "• Real-time token streaming\n"
            "• Process step visibility\n"
            "• Tool execution monitoring\n"
            "• Enhanced user experience"
        )
        instructions.setReadOnly(True)
        layout.addWidget(instructions)
        
        # Add the agent window
        self.agent_window = AgentWindow(self.addon)
        layout.addWidget(self.agent_window)
        
        # Add demo button
        demo_button = QPushButton("🚀 Run Demo Interaction")
        demo_button.clicked.connect(self._run_demo)
        layout.addWidget(demo_button)
    
    def _create_mock_addon(self):
        """Create a mock addon for demonstration."""
        from unittest.mock import Mock
        
        # Create mock addon with necessary attributes
        addon = Mock()
        addon.gguf_app = Mock()
        addon.gguf_app.model = Mock()
        addon.gguf_app.model_loaded = Mock()
        
        # Create mock tool registry
        addon._tool_registry = Mock()
        addon._tool_registry.get_available_tools.return_value = [
            "file_read", "file_write", "execute_command", "search_web"
        ]
        
        # Create mock agent loop
        addon._agent_loop = Mock()
        addon.get_agent_loop.return_value = addon._agent_loop
        
        # Mock session creation
        addon.create_agent_session = Mock(return_value="demo_session_123")
        
        return addon
    
    def _connect_streaming_signals(self):
        """Connect to streaming signals for monitoring."""
        try:
            agent_loop = self.addon.get_agent_loop()
            if agent_loop and hasattr(agent_loop, 'streaming_handler'):
                streaming_handler = agent_loop.streaming_handler
                
                # Connect to streaming events
                streaming_handler.streaming_started.connect(
                    lambda stream_type: self.logger.info(f"Streaming started: {stream_type}")
                )
                
                streaming_handler.process_step_started.connect(
                    lambda step, desc: self.logger.info(f"Process step: {step} - {desc}")
                )
                
                streaming_handler.tool_call_detected.connect(
                    lambda tool_info: self.logger.info(f"Tool detected: {tool_info.get('tool_name')}")
                )
                
                streaming_handler.streaming_finished.connect(
                    lambda stream_type: self.logger.info(f"Streaming finished: {stream_type}")
                )
                
                self.logger.info("Connected to streaming signals")
        
        except Exception as e:
            self.logger.warning(f"Could not connect to streaming signals: {e}")
    
    def _run_demo(self):
        """Run a demonstration of the streaming features."""
        self.logger.info("Starting streaming demo...")
        
        # Create session
        self.agent_window._workspace_selector.setCurrentText("./demo_workspace")
        self.agent_window._create_session()
        
        # Send demo messages with delays
        QTimer.singleShot(1000, self._send_first_message)
        QTimer.singleShot(8000, self._send_second_message)
        QTimer.singleShot(15000, self._send_third_message)
    
    def _send_first_message(self):
        """Send first demo message."""
        message = "Hello! Can you help me create a Python script that reads a file and counts the words?"
        self.agent_window._input_field.setPlainText(message)
        self.agent_window._send_message()
        self.logger.info("Sent first demo message")
    
    def _send_second_message(self):
        """Send second demo message."""
        message = "What tools do you have available for file operations?"
        self.agent_window._input_field.setPlainText(message)
        self.agent_window._send_message()
        self.logger.info("Sent second demo message")
    
    def _send_third_message(self):
        """Send third demo message."""
        message = "Can you search for Python best practices online?"
        self.agent_window._input_field.setPlainText(message)
        self.agent_window._send_message()
        self.logger.info("Sent third demo message")


def main():
    """Main function to run the example."""
    print("🚀 Streaming Agentic Chatbot Example")
    print("=" * 50)
    print("This example demonstrates:")
    print("• Integration of streaming chatbot")
    print("• Real-time process monitoring")
    print("• Enhanced user experience")
    print("• Signal-based architecture")
    print("=" * 50)
    
    # Create Qt application
    app = QApplication(sys.argv)
    
    # Create and show example window
    example = StreamingChatbotExample()
    example.show()
    
    # Run application
    return app.exec()


if __name__ == "__main__":
    try:
        exit_code = main()
        print(f"\n✅ Example completed with exit code: {exit_code}")
    except Exception as e:
        print(f"\n❌ Example failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)