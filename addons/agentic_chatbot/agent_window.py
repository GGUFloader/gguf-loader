#!/usr/bin/env python3
"""
Agent Window - Main interface for agentic chatbot interaction

Provides a comprehensive chat interface for agent conversations with:
- Workspace selector and management
- Tool execution status display
- Message history with tool call visualization
- Real-time updates via Qt6 signals/slots
"""

import logging
from typing import Optional, Any, Dict, List
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QLabel, QScrollArea, QFrame, QSpacerItem, QSizePolicy,
    QComboBox, QFileDialog, QSplitter, QGroupBox, QProgressBar,
    QListWidget, QListWidgetItem, QTabWidget
)
from PySide6.QtCore import Qt, Signal, QTimer, QThread
from PySide6.QtGui import QFont, QTextCursor, QPixmap, QIcon

try:
    from config import FONT_FAMILY
except ImportError:
    FONT_FAMILY = "Segoe UI"

try:
    from widgets.chat_bubble import ChatBubble
except ImportError:
    # Fallback if chat_bubble is not available
    ChatBubble = None


class AgentWindow(QWidget):
    """
    Main agent interaction window.
    
    Features:
    - Chat interface with agent conversation
    - Workspace selector and management
    - Tool execution status and history
    - Real-time updates for tool calls and responses
    - Integration with existing GGUF Loader patterns
    """
    
    # Signals
    message_sent = Signal(str, str)  # message, session_id
    workspace_changed = Signal(str)  # workspace_path
    window_closed = Signal()
    session_created = Signal(str)    # session_id
    
    def __init__(self, addon_instance: Any):
        super().__init__()
        
        # Store reference to addon
        self.addon = addon_instance
        
        # Setup logging
        self._logger = logging.getLogger(__name__)
        
        # Agent state
        self._current_session_id: Optional[str] = None
        self._current_workspace: Optional[Path] = None
        self._conversation_history: List[Dict[str, Any]] = []
        self._is_generating = False
        self._tool_execution_history: List[Dict[str, Any]] = []
        
        # Streaming state
        self._current_streaming_message: Optional[QLabel] = None
        self._current_process_step: Optional[str] = None
        self._streaming_buffer: str = ""
        
        # UI components
        self._workspace_selector: Optional[QComboBox] = None
        self._chat_scroll: Optional[QScrollArea] = None
        self._chat_container: Optional[QWidget] = None
        self._chat_layout: Optional[QVBoxLayout] = None
        self._input_field: Optional[QTextEdit] = None
        self._send_btn: Optional[QPushButton] = None
        self._stop_btn: Optional[QPushButton] = None
        self._tool_status_list: Optional[QListWidget] = None
        self._progress_bar: Optional[QProgressBar] = None
        
        # Setup window
        self._setup_window()
        self._setup_ui()
        self._connect_signals()
        
        # Initialize with default workspace
        self._initialize_default_workspace()
    
    def _setup_window(self):
        """Setup window properties."""
        self.setWindowTitle("🤖 Agentic Chatbot")
        
        # Set window flags for proper behavior
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.CustomizeWindowHint |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint
        )
        
        # Set size
        self.resize(900, 700)
        self.setMinimumSize(600, 500)
        
        # Apply modern styling following existing patterns
        self.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QTextEdit {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 10px;
                font-size: 13px;
            }
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
            QLabel {
                color: #333;
                font-size: 12px;
            }
            QComboBox {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 8px;
                font-size: 13px;
            }
            QListWidget {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
                font-size: 12px;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #ddd;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
    
    def _setup_ui(self):
        """Setup the user interface with workspace selector, chat area, and tool status."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)
        
        # Header with title and model status
        header_layout = QHBoxLayout()
        
        title = QLabel("🤖 Agentic Chatbot")
        title.setFont(QFont(FONT_FAMILY, 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #0078d4; padding: 5px;")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Model status indicator
        self.model_status_label = QLabel("⚪ Model: Not loaded")
        self.model_status_label.setStyleSheet("color: #666; font-size: 12px; padding: 5px;")
        header_layout.addWidget(self.model_status_label)
        
        # Add refresh button for model status
        refresh_btn = QPushButton("🔄")
        refresh_btn.setToolTip("Refresh model status")
        refresh_btn.setMaximumWidth(30)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        refresh_btn.clicked.connect(self._refresh_model_status)
        header_layout.addWidget(refresh_btn)
        
        main_layout.addLayout(header_layout)
        
        # Workspace selector section
        workspace_group = QGroupBox("Workspace")
        workspace_layout = QVBoxLayout(workspace_group)
        
        workspace_selector_layout = QHBoxLayout()
        
        self._workspace_selector = QComboBox()
        self._workspace_selector.setEditable(True)
        self._workspace_selector.setPlaceholderText("Select or enter workspace path...")
        workspace_selector_layout.addWidget(self._workspace_selector, stretch=1)
        
        browse_btn = QPushButton("📁 Browse")
        browse_btn.clicked.connect(self._browse_workspace)
        workspace_selector_layout.addWidget(browse_btn)
        
        create_session_btn = QPushButton("🚀 Start Session")
        create_session_btn.clicked.connect(self._create_session)
        workspace_selector_layout.addWidget(create_session_btn)
        
        workspace_layout.addLayout(workspace_selector_layout)
        
        # Session status
        self.session_status_label = QLabel("📍 No active session")
        self.session_status_label.setStyleSheet("color: #666; font-size: 11px; padding: 2px;")
        workspace_layout.addWidget(self.session_status_label)
        
        main_layout.addWidget(workspace_group)
        
        # Main content area with splitter
        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left side - Chat area
        chat_widget = self._create_chat_area()
        content_splitter.addWidget(chat_widget)
        
        # Right side - Tool status and history
        tool_widget = self._create_tool_status_area()
        content_splitter.addWidget(tool_widget)
        
        # Set splitter proportions (70% chat, 30% tools)
        content_splitter.setSizes([700, 300])
        content_splitter.setStretchFactor(0, 1)
        content_splitter.setStretchFactor(1, 0)
        
        main_layout.addWidget(content_splitter, stretch=1)
        
        # Progress bar for tool execution
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 4px;
                text-align: center;
                font-size: 11px;
            }
            QProgressBar::chunk {
                background-color: #0078d4;
                border-radius: 3px;
            }
        """)
        main_layout.addWidget(self._progress_bar)
    
    def _create_chat_area(self) -> QWidget:
        """Create the chat area with message history and input."""
        chat_widget = QWidget()
        chat_layout = QVBoxLayout(chat_widget)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.setSpacing(10)
        
        # Chat display area with scroll
        self._chat_scroll = QScrollArea()
        self._chat_scroll.setWidgetResizable(True)
        self._chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._chat_scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #ddd;
                border-radius: 8px;
                background-color: white;
            }
        """)
        
        # Container for chat bubbles
        self._chat_container = QWidget()
        self._chat_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._chat_layout = QVBoxLayout(self._chat_container)
        self._chat_layout.setContentsMargins(10, 10, 10, 10)
        self._chat_layout.setSpacing(8)
        self._chat_layout.addStretch()  # Push messages to top
        
        self._chat_scroll.setWidget(self._chat_container)
        chat_layout.addWidget(self._chat_scroll, stretch=1)
        
        # Input area
        input_frame = QFrame()
        input_frame.setStyleSheet("background-color: transparent;")
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(8)
        
        # Input field
        self._input_field = QTextEdit()
        self._input_field.setPlaceholderText("Type your message to the agent...")
        self._input_field.setMaximumHeight(120)
        self._input_field.setMinimumHeight(80)
        self._input_field.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)
        input_layout.addWidget(self._input_field)
        
        # Button row
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        
        # Clear button
        clear_btn = QPushButton("🗑️ Clear")
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                padding: 8px 15px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        clear_btn.clicked.connect(self._clear_chat)
        button_layout.addWidget(clear_btn)
        
        # Stop button (hidden by default)
        self._stop_btn = QPushButton("⏹ Stop")
        self._stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                padding: 8px 15px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        self._stop_btn.clicked.connect(self._stop_generation)
        self._stop_btn.hide()
        button_layout.addWidget(self._stop_btn)
        
        button_layout.addStretch()
        
        # Send button
        self._send_btn = QPushButton("🚀 Send")
        self._send_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
        """)
        self._send_btn.clicked.connect(self._send_message)
        button_layout.addWidget(self._send_btn)
        
        input_layout.addLayout(button_layout)
        chat_layout.addWidget(input_frame)
        
        # Enable Enter to send, Shift+Enter for new line
        self._input_field.installEventFilter(self)
        
        return chat_widget
    
    def _create_tool_status_area(self) -> QWidget:
        """Create the tool status and execution history area."""
        tool_widget = QWidget()
        tool_layout = QVBoxLayout(tool_widget)
        tool_layout.setContentsMargins(0, 0, 0, 0)
        tool_layout.setSpacing(10)
        
        # Tool status section
        status_group = QGroupBox("🔧 Tool Status")
        status_layout = QVBoxLayout(status_group)
        
        # Available tools indicator
        self.tools_status_label = QLabel("⚪ Tools: Not initialized")
        self.tools_status_label.setStyleSheet("color: #666; font-size: 11px;")
        status_layout.addWidget(self.tools_status_label)
        
        # Current tool execution
        self.current_tool_label = QLabel("💤 Idle")
        self.current_tool_label.setStyleSheet("color: #666; font-size: 11px;")
        status_layout.addWidget(self.current_tool_label)
        
        # Current process step
        self.current_step_label = QLabel("⏸️ Ready")
        self.current_step_label.setStyleSheet("color: #666; font-size: 11px;")
        status_layout.addWidget(self.current_step_label)
        
        tool_layout.addWidget(status_group)
        
        # Tool execution history
        history_group = QGroupBox("📋 Tool History")
        history_layout = QVBoxLayout(history_group)
        
        self._tool_status_list = QListWidget()
        self._tool_status_list.setMaximumHeight(200)
        self._tool_status_list.setStyleSheet("""
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
            }
        """)
        history_layout.addWidget(self._tool_status_list)
        
        # Clear history button
        clear_history_btn = QPushButton("🗑️ Clear History")
        clear_history_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        clear_history_btn.clicked.connect(self._clear_tool_history)
        history_layout.addWidget(clear_history_btn)
        
        tool_layout.addWidget(history_group)
        
        # Workspace info
        workspace_group = QGroupBox("📁 Workspace Info")
        workspace_layout = QVBoxLayout(workspace_group)
        
        self.workspace_info_label = QLabel("No workspace selected")
        self.workspace_info_label.setWordWrap(True)
        self.workspace_info_label.setStyleSheet("color: #666; font-size: 11px;")
        workspace_layout.addWidget(self.workspace_info_label)
        
        tool_layout.addWidget(workspace_group)
        
        tool_layout.addStretch()
        
        return tool_widget
    
    def _connect_signals(self):
        """Connect signals from addon components."""
        try:
            self._logger.debug("Connecting signals...")
            
            if self.addon and hasattr(self.addon, 'gguf_app'):
                self._logger.debug("Addon and gguf_app available")
                
                # Connect to model status
                if hasattr(self.addon.gguf_app, 'model_loaded'):
                    self.addon.gguf_app.model_loaded.connect(self._on_model_loaded)
                    self._logger.debug("Connected to model_loaded signal")
                else:
                    self._logger.warning("gguf_app has no model_loaded signal")
                
                # Connect to addon signals
                if hasattr(self.addon, 'tool_call_executed'):
                    self.addon.tool_call_executed.connect(self._on_tool_executed)
                    self._logger.debug("Connected to tool_call_executed signal")
                
                if hasattr(self.addon, 'agent_session_created'):
                    self.addon.agent_session_created.connect(self._on_session_created)
                    self._logger.debug("Connected to agent_session_created signal")
                
                # Connect to agent loop signals if available
                agent_loop = self.addon.get_agent_loop()
                if agent_loop:
                    agent_loop.tool_call_requested.connect(self._on_tool_call_requested)
                    agent_loop.tool_result_received.connect(self._on_tool_result_received)
                    agent_loop.response_generated.connect(self._on_response_generated)
                    agent_loop.error_occurred.connect(self._on_agent_error)
                    agent_loop.turn_completed.connect(self._on_turn_completed)
                    
                    # Connect to streaming handler signals for real-time updates
                    if hasattr(agent_loop, 'streaming_handler'):
                        streaming_handler = agent_loop.streaming_handler
                        streaming_handler.token_received.connect(self._on_token_received)
                        streaming_handler.chunk_received.connect(self._on_chunk_received)
                        streaming_handler.streaming_started.connect(self._on_streaming_started)
                        streaming_handler.streaming_finished.connect(self._on_streaming_finished)
                        streaming_handler.streaming_error.connect(self._on_streaming_error)
                        streaming_handler.process_step_started.connect(self._on_process_step_started)
                        streaming_handler.process_step_completed.connect(self._on_process_step_completed)
                        streaming_handler.reasoning_chunk_received.connect(self._on_reasoning_chunk_received)
                        streaming_handler.tool_call_detected.connect(self._on_tool_call_detected)
                        streaming_handler.tool_execution_started.connect(self._on_tool_execution_started)
                        streaming_handler.tool_execution_completed.connect(self._on_tool_execution_completed)
                        self._logger.debug("Connected to streaming handler signals")
                    
                    self._logger.debug("Connected to agent loop signals")
                else:
                    self._logger.warning("No agent loop available for signal connection")
            else:
                self._logger.warning("No addon or gguf_app available for signal connection")
            
            # Connect workspace selector
            if self._workspace_selector:
                self._workspace_selector.currentTextChanged.connect(self._on_workspace_changed)
                self._logger.debug("Connected workspace selector signal")
            
            # IMPORTANT: Check model status immediately after connecting signals
            # This handles the case where model was loaded before agent window was created
            self._logger.debug("Performing initial model status check...")
            self._update_model_status()
                
        except Exception as e:
            self._logger.error(f"Error connecting signals: {e}")
            import traceback
            self._logger.error(f"Signal connection traceback: {traceback.format_exc()}")
    
    def _initialize_default_workspace(self):
        """Initialize with default workspace options."""
        try:
            # Add common workspace paths
            default_workspaces = [
                "./agent_workspace",
                "./workspace",
                "./projects",
                str(Path.home() / "agent_workspace"),
                str(Path.home() / "Documents" / "agent_workspace")
            ]
            
            for workspace in default_workspaces:
                self._workspace_selector.addItem(workspace)
            
            # Set default selection
            self._workspace_selector.setCurrentText("./agent_workspace")
            
            # Update model status
            self._update_model_status()
            
            # Set up periodic model status check to handle cases where model is loaded
            # after agent window is created
            self._model_check_timer = QTimer()
            self._model_check_timer.timeout.connect(self._periodic_model_check)
            self._model_check_timer.start(2000)  # Check every 2 seconds
            
        except Exception as e:
            self._logger.error(f"Error initializing default workspace: {e}")
    
    def _periodic_model_check(self):
        """Periodically check model status to catch late model loading."""
        try:
            # Only check if we think no model is loaded
            current_text = self.model_status_label.text()
            if "Not loaded" in current_text or "⚪" in current_text or "🔴" in current_text:
                self._update_model_status()
                
                # If model is now detected, we can reduce the frequency of checks
                new_text = self.model_status_label.text()
                if "Ready" in new_text or "🟢" in new_text:
                    self._logger.debug("Model detected during periodic check - reducing check frequency")
                    self._model_check_timer.setInterval(10000)  # Check every 10 seconds instead
                    
        except Exception as e:
            self._logger.debug(f"Error in periodic model check: {e}")
    
    def _browse_workspace(self):
        """Open file dialog to browse for workspace directory."""
        try:
            dialog = QFileDialog()
            workspace_path = dialog.getExistingDirectory(
                self,
                "Select Workspace Directory",
                str(Path.home()),
                QFileDialog.Option.ShowDirsOnly
            )
            
            if workspace_path:
                self._workspace_selector.setCurrentText(workspace_path)
                
        except Exception as e:
            self._logger.error(f"Error browsing workspace: {e}")
            self._add_system_message(f"❌ Error browsing workspace: {e}")
    
    def _create_session(self):
        """Create a new agent session with selected workspace."""
        try:
            workspace_path = self._workspace_selector.currentText().strip()
            if not workspace_path:
                self._add_system_message("⚠️ Please select a workspace directory first.")
                return
            
            # Validate workspace path
            workspace = Path(workspace_path)
            if not workspace.exists():
                try:
                    workspace.mkdir(parents=True, exist_ok=True)
                    self._add_system_message(f"📁 Created workspace directory: {workspace}")
                except Exception as e:
                    self._add_system_message(f"❌ Failed to create workspace: {e}")
                    return
            
            # Create session through addon
            if self.addon and hasattr(self.addon, 'create_agent_session'):
                session_id = self.addon.create_agent_session(str(workspace))
                if session_id:
                    self._current_session_id = session_id
                    self._current_workspace = workspace
                    self._update_session_status(session_id, str(workspace))
                    self._add_system_message(f"🚀 Started agent session: {session_id[:8]}...")
                    self.session_created.emit(session_id)
                else:
                    self._add_system_message("❌ Failed to create agent session")
            else:
                self._add_system_message("❌ Agent addon not available")
                
        except Exception as e:
            self._logger.error(f"Error creating session: {e}")
            self._add_system_message(f"❌ Error creating session: {e}")
    
    def _send_message(self):
        """Send message to the agent."""
        try:
            message = self._input_field.toPlainText().strip()
            
            if not message:
                return
            
            if not self._current_session_id:
                self._add_system_message("⚠️ Please create an agent session first.")
                return
            
            # Check if model is available
            model_loaded = self._is_model_loaded()
            
            if not model_loaded:
                self._add_system_message("⚠️ Please load a model first in the main window.")
                return
            
            # Disable input while processing
            self._set_generating_state(True)
            
            # Display user message
            self._add_user_message(message)
            
            # Clear input
            self._input_field.clear()
            
            # Send message to agent loop through addon
            try:
                agent_loop = self.addon.get_agent_loop()
                if agent_loop:
                    # Set session for agent loop
                    agent_loop.set_session(self._current_session_id, str(self._current_workspace))
                    # Process message
                    agent_loop.process_user_message(message)
                else:
                    self._add_system_message("❌ Agent loop not available")
                    self._set_generating_state(False)
                    return
            except Exception as e:
                self._logger.error(f"Error sending message to agent loop: {e}")
                self._add_system_message(f"❌ Error sending message: {e}")
                self._set_generating_state(False)
                return
            
            # Emit signal for message processing
            self.message_sent.emit(message, self._current_session_id)
            
            # Add to conversation history
            self._conversation_history.append({
                "role": "user",
                "content": message,
                "timestamp": self._get_timestamp()
            })
            
            # Show processing indicator with streaming support
            self._add_system_message("🤔 Agent is analyzing your request...")
            
            # Create streaming message placeholder
            self._streaming_buffer = ""
            self._current_streaming_message = self._create_streaming_message()
            
        except Exception as e:
            self._logger.error(f"Error sending message: {e}")
            self._add_system_message(f"❌ Error sending message: {e}")
            self._set_generating_state(False)
    
    def _stop_generation(self):
        """Stop the current agent processing."""
        try:
            # Stop agent loop processing
            agent_loop = self.addon.get_agent_loop()
            if agent_loop and agent_loop.is_processing():
                agent_loop.stop_processing()
            
            self._set_generating_state(False)
            self._add_system_message("⏹ Processing stopped")
            
        except Exception as e:
            self._logger.error(f"Error stopping generation: {e}")
            self._set_generating_state(False)
    
    def _clear_chat(self):
        """Clear chat history."""
        try:
            # Remove all widgets except the stretch
            while self._chat_layout.count() > 1:
                item = self._chat_layout.takeAt(0)
                if item and item.widget():
                    item.widget().deleteLater()
            
            self._conversation_history.clear()
            self._add_system_message("🗑️ Chat cleared")
            
        except Exception as e:
            self._logger.error(f"Error clearing chat: {e}")
    
    def _clear_tool_history(self):
        """Clear tool execution history."""
        try:
            self._tool_status_list.clear()
            self._tool_execution_history.clear()
            self._add_tool_status("🗑️ Tool history cleared", "info")
            
        except Exception as e:
            self._logger.error(f"Error clearing tool history: {e}")
    
    def _add_user_message(self, message: str):
        """Add user message to chat display (right side)."""
        try:
            msg_container = QWidget()
            msg_layout = QHBoxLayout(msg_container)
            msg_layout.setContentsMargins(5, 2, 5, 2)
            msg_layout.setSpacing(0)
            
            # Add spacer for right alignment
            spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            msg_layout.addItem(spacer)
            
            if ChatBubble:
                bubble = ChatBubble(message, is_user=True)
                bubble.setStyleSheet("""
                    QFrame {
                        background-color: #0078d4;
                        border-radius: 15px;
                        margin: 2px;
                    }
                    QLabel {
                        color: white;
                        font-size: 13px;
                        padding: 10px 14px;
                    }
                """)
                msg_layout.addWidget(bubble, stretch=2)
            else:
                label = QLabel(message)
                label.setWordWrap(True)
                label.setStyleSheet("""
                    background-color: #0078d4;
                    color: white;
                    padding: 10px 14px;
                    border-radius: 15px;
                    font-size: 13px;
                """)
                msg_layout.addWidget(label, stretch=2)
            
            # Insert before the stretch at the end
            self._chat_layout.insertWidget(self._chat_layout.count() - 1, msg_container)
            self._scroll_to_bottom()
            
        except Exception as e:
            self._logger.error(f"Error adding user message: {e}")
    
    def _add_agent_message(self, message: str):
        """Add agent message to chat display (left side)."""
        try:
            msg_container = QWidget()
            msg_layout = QHBoxLayout(msg_container)
            msg_layout.setContentsMargins(5, 2, 5, 2)
            msg_layout.setSpacing(0)
            
            if ChatBubble:
                bubble = ChatBubble(message, is_user=False)
                bubble.setStyleSheet("""
                    QFrame {
                        background-color: #e9ecef;
                        border-radius: 15px;
                        margin: 2px;
                    }
                    QLabel {
                        color: #333;
                        font-size: 13px;
                        padding: 10px 14px;
                    }
                """)
                msg_layout.addWidget(bubble, stretch=2)
            else:
                label = QLabel(message)
                label.setWordWrap(True)
                label.setStyleSheet("""
                    background-color: #e9ecef;
                    color: #333;
                    padding: 10px 14px;
                    border-radius: 15px;
                    font-size: 13px;
                """)
                msg_layout.addWidget(label, stretch=2)
            
            # Add spacer for left alignment
            spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            msg_layout.addItem(spacer)
            
            # Insert before the stretch at the end
            self._chat_layout.insertWidget(self._chat_layout.count() - 1, msg_container)
            self._scroll_to_bottom()
            
        except Exception as e:
            self._logger.error(f"Error adding agent message: {e}")
    
    def _add_system_message(self, message: str):
        """Add system message to chat display (centered)."""
        try:
            msg_container = QWidget()
            msg_layout = QHBoxLayout(msg_container)
            msg_layout.setContentsMargins(0, 0, 0, 0)
            msg_layout.addStretch()
            
            label = QLabel(message)
            label.setStyleSheet("""
                color: #6c757d;
                font-size: 11px;
                font-style: italic;
                padding: 5px;
            """)
            msg_layout.addWidget(label)
            msg_layout.addStretch()
            
            # Insert before the stretch at the end
            self._chat_layout.insertWidget(self._chat_layout.count() - 1, msg_container)
            self._scroll_to_bottom()
            
        except Exception as e:
            self._logger.error(f"Error adding system message: {e}")
    
    def _add_tool_call_message(self, tool_name: str, parameters: Dict[str, Any], result: Dict[str, Any]):
        """Add tool call visualization to chat display."""
        try:
            msg_container = QWidget()
            msg_layout = QVBoxLayout(msg_container)
            msg_layout.setContentsMargins(10, 5, 10, 5)
            
            # Tool call header
            header_layout = QHBoxLayout()
            
            tool_icon = QLabel("🔧")
            tool_icon.setStyleSheet("font-size: 16px;")
            header_layout.addWidget(tool_icon)
            
            tool_label = QLabel(f"Tool: {tool_name}")
            tool_label.setStyleSheet("font-weight: bold; color: #0078d4;")
            header_layout.addWidget(tool_label)
            
            header_layout.addStretch()
            
            status = result.get("status", "unknown")
            status_color = "#28a745" if status == "success" else "#dc3545"
            status_label = QLabel(f"Status: {status}")
            status_label.setStyleSheet(f"color: {status_color}; font-weight: bold;")
            header_layout.addWidget(status_label)
            
            msg_layout.addLayout(header_layout)
            
            # Tool details in a frame
            details_frame = QFrame()
            details_frame.setStyleSheet("""
                QFrame {
                    background-color: #f8f9fa;
                    border: 1px solid #dee2e6;
                    border-radius: 8px;
                    padding: 8px;
                }
            """)
            details_layout = QVBoxLayout(details_frame)
            
            # Parameters (if any)
            if parameters:
                params_text = f"Parameters: {self._format_dict_for_display(parameters)}"
                params_label = QLabel(params_text)
                params_label.setWordWrap(True)
                params_label.setStyleSheet("font-size: 11px; color: #666;")
                details_layout.addWidget(params_label)
            
            # Result
            if "result" in result:
                result_text = f"Result: {self._format_result_for_display(result['result'])}"
                result_label = QLabel(result_text)
                result_label.setWordWrap(True)
                result_label.setStyleSheet("font-size: 11px; color: #333;")
                details_layout.addWidget(result_label)
            
            # Error (if any)
            if "error" in result and result["error"]:
                error_label = QLabel(f"Error: {result['error']}")
                error_label.setWordWrap(True)
                error_label.setStyleSheet("font-size: 11px; color: #dc3545;")
                details_layout.addWidget(error_label)
            
            msg_layout.addWidget(details_frame)
            
            # Insert before the stretch at the end
            self._chat_layout.insertWidget(self._chat_layout.count() - 1, msg_container)
            self._scroll_to_bottom()
            
        except Exception as e:
            self._logger.error(f"Error adding tool call message: {e}")
    
    def _add_tool_status(self, message: str, status_type: str = "info"):
        """Add tool status message to the tool history list."""
        try:
            timestamp = self._get_timestamp()
            
            # Create list item
            item = QListWidgetItem()
            
            # Set icon based on status type
            if status_type == "success":
                icon_text = "✅"
                color = "#28a745"
            elif status_type == "error":
                icon_text = "❌"
                color = "#dc3545"
            elif status_type == "running":
                icon_text = "⚙️"
                color = "#0078d4"
            else:
                icon_text = "ℹ️"
                color = "#6c757d"
            
            item_text = f"{icon_text} {timestamp} - {message}"
            item.setText(item_text)
            
            # Add to list
            self._tool_status_list.addItem(item)
            
            # Scroll to bottom
            self._tool_status_list.scrollToBottom()
            
            # Limit history size
            if self._tool_status_list.count() > 100:
                self._tool_status_list.takeItem(0)
                
        except Exception as e:
            self._logger.error(f"Error adding tool status: {e}")
    
    def _scroll_to_bottom(self):
        """Scroll chat display to bottom."""
        QTimer.singleShot(100, lambda: self._chat_scroll.verticalScrollBar().setValue(
            self._chat_scroll.verticalScrollBar().maximum()
        ))
    
    def _set_generating_state(self, is_generating: bool):
        """Set the UI state for generation/processing."""
        try:
            self._is_generating = is_generating
            
            # Update input controls
            self._input_field.setEnabled(not is_generating)
            self._send_btn.setEnabled(not is_generating and self._is_model_loaded())
            
            # Show/hide stop button
            if is_generating:
                self._send_btn.hide()
                self._stop_btn.show()
                self._progress_bar.setVisible(True)
                self._progress_bar.setRange(0, 0)  # Indeterminate progress
            else:
                self._stop_btn.hide()
                self._send_btn.show()
                self._progress_bar.setVisible(False)
                self._input_field.setFocus()
                
        except Exception as e:
            self._logger.error(f"Error setting generating state: {e}")
    
    def _refresh_model_status(self):
        """Manually refresh model status - useful for debugging."""
        try:
            self._logger.info("Manually refreshing model status...")
            self._update_model_status()
            
            # Also check if we can access the model directly for debugging
            if self.addon and hasattr(self.addon, 'gguf_app'):
                if hasattr(self.addon.gguf_app, 'model'):
                    model = self.addon.gguf_app.model
                    self._logger.info(f"Direct model check - model: {model}, type: {type(model)}")
                    if model is not None:
                        self._add_system_message(f"🔍 Model detected: {type(model).__name__}")
                    else:
                        self._add_system_message("🔍 Model is None")
                else:
                    self._logger.info("Direct model check - no model attribute")
                    self._add_system_message("🔍 No model attribute found")
            else:
                self._logger.info("Direct model check - no gguf_app")
                self._add_system_message("🔍 No gguf_app found")
                
        except Exception as e:
            self._logger.error(f"Error refreshing model status: {e}")
            self._add_system_message(f"❌ Error checking model: {e}")
    
    def _update_model_status(self):
        """Update model status indicator."""
        try:
            model_loaded = self._is_model_loaded()
            
            if model_loaded:
                self.model_status_label.setText("🟢 Model: Ready")
                self.model_status_label.setStyleSheet("color: #28a745; font-size: 12px; padding: 5px;")
                self._send_btn.setEnabled(not self._is_generating)
                self._logger.debug("Model status updated: Ready")
            else:
                self.model_status_label.setText("🔴 Model: Not loaded")
                self.model_status_label.setStyleSheet("color: #dc3545; font-size: 12px; padding: 5px;")
                self._send_btn.setEnabled(False)
                self._logger.debug("Model status updated: Not loaded")
                
        except Exception as e:
            self._logger.error(f"Error updating model status: {e}")
            self.model_status_label.setText("⚠️ Model: Error")
            self.model_status_label.setStyleSheet("color: #ffc107; font-size: 12px; padding: 5px;")
    
    def _update_session_status(self, session_id: str, workspace_path: str):
        """Update session status display."""
        try:
            short_id = session_id[:8] if session_id else "unknown"
            self.session_status_label.setText(f"🟢 Session: {short_id}...")
            self.session_status_label.setStyleSheet("color: #28a745; font-size: 11px; padding: 2px;")
            
            # Update workspace info
            workspace_info = f"Path: {workspace_path}\nSession: {short_id}..."
            self.workspace_info_label.setText(workspace_info)
            
            # Update tools status
            if self.addon and hasattr(self.addon, '_tool_registry') and self.addon._tool_registry:
                available_tools = self.addon._tool_registry.get_available_tools()
                self.tools_status_label.setText(f"🟢 Tools: {len(available_tools)} available")
                self.tools_status_label.setStyleSheet("color: #28a745; font-size: 11px;")
            
        except Exception as e:
            self._logger.error(f"Error updating session status: {e}")
    
    def _is_model_loaded(self) -> bool:
        """Check if model is loaded in the main app."""
        try:
            if not self.addon:
                self._logger.debug("No addon available")
                return False
            
            if not hasattr(self.addon, 'gguf_app'):
                self._logger.debug("Addon has no gguf_app attribute")
                return False
            
            gguf_app = self.addon.gguf_app
            if not gguf_app:
                self._logger.debug("gguf_app is None")
                return False
            
            if not hasattr(gguf_app, 'model'):
                self._logger.debug("gguf_app has no model attribute")
                return False
            
            model = gguf_app.model
            if model is None:
                self._logger.debug("Model is None")
                return False
            
            # Check for different model types
            model_type = type(model).__name__
            
            # Real llama-cpp-python model (check this first)
            if model_type == 'Llama':
                self._logger.debug("Real Llama model detected")
                return True
            
            # Mock object for testing (check after Llama to handle mocks with Llama name)
            if hasattr(model, '_mock_name') or 'Mock' in str(type(model)):
                self._logger.debug("Mock model detected")
                return True
            
            # Check for common model methods
            if hasattr(model, '__call__') or hasattr(model, 'generate') or hasattr(model, '__iter__'):
                self._logger.debug(f"Model with expected methods detected: {model_type}")
                return True
            
            # If it's not None and we can't identify it, assume it's loaded
            self._logger.debug(f"Unknown model type detected, assuming loaded: {model_type}")
            return True
            
        except Exception as e:
            self._logger.debug(f"Exception in _is_model_loaded: {e}")
            return False
    
    def _get_timestamp(self) -> str:
        """Get formatted timestamp."""
        from datetime import datetime
        return datetime.now().strftime("%H:%M:%S")
    
    def _format_dict_for_display(self, data: Dict[str, Any]) -> str:
        """Format dictionary for display in UI."""
        try:
            if not data:
                return "{}"
            
            items = []
            for key, value in data.items():
                if isinstance(value, str) and len(value) > 50:
                    value = value[:47] + "..."
                items.append(f"{key}: {value}")
            
            return "{" + ", ".join(items) + "}"
        except Exception:
            return str(data)
    
    def _format_result_for_display(self, result: Any) -> str:
        """Format result for display in UI."""
        try:
            if isinstance(result, str):
                return result[:200] + "..." if len(result) > 200 else result
            elif isinstance(result, dict):
                return self._format_dict_for_display(result)
            else:
                result_str = str(result)
                return result_str[:200] + "..." if len(result_str) > 200 else result_str
        except Exception:
            return str(result)
    
    # Signal handlers
    def _on_model_loaded(self, model):
        """Handle model loaded signal from main app."""
        try:
            self._logger.info(f"Model loaded signal received: {model}")
            self._update_model_status()
            self._add_system_message("🟢 Model loaded - agent ready")
            
            # Stop the frequent model checking timer since model is now loaded
            if hasattr(self, '_model_check_timer'):
                self._model_check_timer.setInterval(10000)  # Reduce to every 10 seconds
                
        except Exception as e:
            self._logger.error(f"Error handling model loaded: {e}")
    
    def _on_tool_executed(self, result: Dict[str, Any]):
        """Handle tool execution result from addon."""
        try:
            tool_name = result.get("tool_name", "unknown")
            status = result.get("status", "unknown")
            
            # Update current tool status
            if status == "success":
                self.current_tool_label.setText("✅ Tool completed")
                self.current_tool_label.setStyleSheet("color: #28a745; font-size: 11px;")
                self._add_tool_status(f"Tool '{tool_name}' completed successfully", "success")
            else:
                self.current_tool_label.setText("❌ Tool failed")
                self.current_tool_label.setStyleSheet("color: #dc3545; font-size: 11px;")
                error = result.get("error", "Unknown error")
                self._add_tool_status(f"Tool '{tool_name}' failed: {error}", "error")
            
            # Add tool call to chat if we have the parameters
            if "parameters" in result:
                self._add_tool_call_message(tool_name, result["parameters"], result)
            
            # Reset to idle after a delay
            QTimer.singleShot(3000, lambda: self._reset_tool_status())
            
        except Exception as e:
            self._logger.error(f"Error handling tool executed: {e}")
    
    def _on_session_created(self, session_id: str):
        """Handle session created signal from addon."""
        try:
            self._add_system_message(f"🚀 Agent session created: {session_id[:8]}...")
        except Exception as e:
            self._logger.error(f"Error handling session created: {e}")
    
    def _on_workspace_changed(self, workspace_path: str):
        """Handle workspace selector change."""
        try:
            if workspace_path and workspace_path != self._current_workspace:
                self.workspace_changed.emit(workspace_path)
        except Exception as e:
            self._logger.error(f"Error handling workspace changed: {e}")
    
    def _reset_tool_status(self):
        """Reset tool status to idle."""
        try:
            self.current_tool_label.setText("💤 Idle")
            self.current_tool_label.setStyleSheet("color: #666; font-size: 11px;")
        except Exception as e:
            self._logger.error(f"Error resetting tool status: {e}")
    
    # Public methods for external control
    def add_agent_response(self, response: str):
        """Add agent response to chat display."""
        try:
            # Remove "thinking" message if present
            self._remove_last_system_message()
            
            # Add agent response
            self._add_agent_message(response)
            
            # Add to conversation history
            self._conversation_history.append({
                "role": "assistant",
                "content": response,
                "timestamp": self._get_timestamp()
            })
            
            # Reset generating state
            self._set_generating_state(False)
            
        except Exception as e:
            self._logger.error(f"Error adding agent response: {e}")
    
    def show_tool_execution(self, tool_name: str, parameters: Dict[str, Any]):
        """Show tool execution in progress."""
        try:
            self.current_tool_label.setText(f"⚙️ Running: {tool_name}")
            self.current_tool_label.setStyleSheet("color: #0078d4; font-size: 11px;")
            self._add_tool_status(f"Executing tool: {tool_name}", "running")
            
        except Exception as e:
            self._logger.error(f"Error showing tool execution: {e}")
    
    def _remove_last_system_message(self):
        """Remove the last system message (like 'thinking...')."""
        try:
            # This is a simplified version - in practice you'd need to track message types
            count = self._chat_layout.count()
            if count > 1:
                item = self._chat_layout.itemAt(count - 2)
                if item and item.widget():
                    widget = item.widget()
                    # Check if it's a system message by looking for italic style
                    if hasattr(widget, 'layout'):
                        layout = widget.layout()
                        if layout and layout.count() > 0:
                            for i in range(layout.count()):
                                child_item = layout.itemAt(i)
                                if child_item and child_item.widget():
                                    child_widget = child_item.widget()
                                    if isinstance(child_widget, QLabel):
                                        style = child_widget.styleSheet()
                                        if "font-style: italic" in style:
                                            self._chat_layout.removeWidget(widget)
                                            widget.deleteLater()
                                            return
        except Exception as e:
            self._logger.debug(f"Could not remove last system message: {e}")
    
    def eventFilter(self, obj, event):
        """Event filter for Enter to send, Shift+Enter for new line."""
        if obj == self._input_field and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
                if event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
                    # Shift+Enter: insert new line (default behavior)
                    return False
                else:
                    # Plain Enter: send message
                    self._send_message()
                    return True
        return super().eventFilter(obj, event)
    
    def closeEvent(self, event):
        """Handle window close event."""
        try:
            # Stop model check timer
            if hasattr(self, '_model_check_timer') and self._model_check_timer:
                self._model_check_timer.stop()
                self._model_check_timer = None
            
            self.window_closed.emit()
            super().closeEvent(event)
        except Exception as e:
            self._logger.error(f"Error handling close event: {e}")
            super().closeEvent(event)
    
    # Additional signal handlers for agent loop integration
    def _on_tool_call_requested(self, tool_call: dict):
        """Handle tool call requested from agent loop."""
        try:
            tool_name = tool_call.get('tool', 'unknown')
            self.show_tool_execution(tool_name, tool_call.get('parameters', {}))
        except Exception as e:
            self._logger.error(f"Error handling tool call requested: {e}")
    
    def _on_tool_result_received(self, tool_result: dict):
        """Handle tool result received from agent loop."""
        try:
            tool_name = tool_result.get('tool_name', 'unknown')
            status = tool_result.get('status', 'unknown')
            
            if status == "success":
                self.current_tool_label.setText("✅ Tool completed")
                self.current_tool_label.setStyleSheet("color: #28a745; font-size: 11px;")
                self._add_tool_status(f"Tool '{tool_name}' completed successfully", "success")
            else:
                self.current_tool_label.setText("❌ Tool failed")
                self.current_tool_label.setStyleSheet("color: #dc3545; font-size: 11px;")
                error = tool_result.get("error", "Unknown error")
                self._add_tool_status(f"Tool '{tool_name}' failed: {error}", "error")
            
            # Add tool call to chat
            parameters = tool_result.get("parameters", {})
            self._add_tool_call_message(tool_name, parameters, tool_result)
            
            # Reset to idle after a delay
            QTimer.singleShot(3000, lambda: self._reset_tool_status())
            
        except Exception as e:
            self._logger.error(f"Error handling tool result received: {e}")
    
    def _on_response_generated(self, response: str):
        """Handle response generated from agent loop."""
        try:
            self.add_agent_response(response)
        except Exception as e:
            self._logger.error(f"Error handling response generated: {e}")
    
    def _on_agent_error(self, error_message: str):
        """Handle error from agent loop."""
        try:
            self._add_system_message(f"❌ Agent error: {error_message}")
            self._set_generating_state(False)
        except Exception as e:
            self._logger.error(f"Error handling agent error: {e}")
    
    def _on_turn_completed(self, turn_data: dict):
        """Handle turn completed from agent loop."""
        try:
            self._logger.debug("Agent turn completed")
            # Turn completion is already handled by response_generated signal
        except Exception as e:
            self._logger.error(f"Error handling turn completed: {e}")
    
    # Streaming signal handlers
    def _on_token_received(self, token: str):
        """Handle token received from streaming handler."""
        try:
            # Add token to streaming buffer
            self._streaming_buffer += token
            
            # Update current streaming message if it exists
            if self._current_streaming_message:
                self._current_streaming_message.setText(self._streaming_buffer)
                self._scroll_to_bottom()
                
        except Exception as e:
            self._logger.error(f"Error handling token received: {e}")
    
    def _on_chunk_received(self, chunk_data: dict):
        """Handle chunk received from streaming handler."""
        try:
            chunk_type = chunk_data.get("chunk_type", "unknown")
            content = chunk_data.get("content", "")
            
            if chunk_type == "reasoning":
                self._add_reasoning_message(content)
            elif chunk_type == "process_step":
                step_name = chunk_data.get("metadata", {}).get("step_name", "unknown")
                self._update_process_step(step_name, content)
                
        except Exception as e:
            self._logger.error(f"Error handling chunk received: {e}")
    
    def _on_streaming_started(self, stream_type: str):
        """Handle streaming started."""
        try:
            self._logger.debug(f"Streaming started: {stream_type}")
            
            # Create streaming message placeholder
            self._streaming_buffer = ""
            self._current_streaming_message = self._create_streaming_message()
            
            # Update UI state
            self._set_generating_state(True)
            
        except Exception as e:
            self._logger.error(f"Error handling streaming started: {e}")
    
    def _on_streaming_finished(self, stream_type: str):
        """Handle streaming finished."""
        try:
            self._logger.debug(f"Streaming finished: {stream_type}")
            
            # Finalize streaming message
            if self._current_streaming_message and self._streaming_buffer:
                # Convert streaming message to final agent message
                final_text = self._streaming_buffer.strip()
                if final_text:
                    # Remove the streaming message
                    if self._current_streaming_message.parent():
                        self._chat_layout.removeWidget(self._current_streaming_message.parent())
                        self._current_streaming_message.parent().deleteLater()
                    
                    # Add as final agent message
                    self._add_agent_message(final_text)
            
            # Reset streaming state
            self._current_streaming_message = None
            self._streaming_buffer = ""
            self._set_generating_state(False)
            
        except Exception as e:
            self._logger.error(f"Error handling streaming finished: {e}")
    
    def _on_streaming_error(self, error_message: str):
        """Handle streaming error."""
        try:
            self._add_system_message(f"❌ Streaming error: {error_message}")
            self._set_generating_state(False)
            
            # Reset streaming state
            self._current_streaming_message = None
            self._streaming_buffer = ""
            
        except Exception as e:
            self._logger.error(f"Error handling streaming error: {e}")
    
    def _on_process_step_started(self, step_name: str, description: str):
        """Handle process step started."""
        try:
            self._current_process_step = step_name
            self.current_step_label.setText(f"⚙️ {description}")
            self.current_step_label.setStyleSheet("color: #0078d4; font-size: 11px;")
            
            # Add process step to tool history
            self._add_tool_status(f"Step: {description}", "running")
            
        except Exception as e:
            self._logger.error(f"Error handling process step started: {e}")
    
    def _on_process_step_completed(self, step_name: str):
        """Handle process step completed."""
        try:
            if self._current_process_step == step_name:
                self.current_step_label.setText("✅ Step completed")
                self.current_step_label.setStyleSheet("color: #28a745; font-size: 11px;")
                
                # Reset to ready after a delay
                QTimer.singleShot(2000, lambda: self._reset_step_status())
            
        except Exception as e:
            self._logger.error(f"Error handling process step completed: {e}")
    
    def _on_reasoning_chunk_received(self, reasoning_text: str):
        """Handle reasoning chunk received."""
        try:
            # Add reasoning as a special message type
            self._add_reasoning_message(reasoning_text)
            
        except Exception as e:
            self._logger.error(f"Error handling reasoning chunk received: {e}")
    
    def _on_tool_call_detected(self, tool_info: dict):
        """Handle tool call detected."""
        try:
            tool_name = tool_info.get("tool_name", "unknown")
            self._add_system_message(f"🔧 Tool call detected: {tool_name}")
            
        except Exception as e:
            self._logger.error(f"Error handling tool call detected: {e}")
    
    def _on_tool_execution_started(self, tool_name: str, parameters: dict):
        """Handle tool execution started."""
        try:
            self.show_tool_execution(tool_name, parameters)
            
        except Exception as e:
            self._logger.error(f"Error handling tool execution started: {e}")
    
    def _on_tool_execution_completed(self, tool_name: str, result: dict):
        """Handle tool execution completed."""
        try:
            status = result.get("status", "unknown")
            
            if status == "success":
                self.current_tool_label.setText("✅ Tool completed")
                self.current_tool_label.setStyleSheet("color: #28a745; font-size: 11px;")
                self._add_tool_status(f"Tool '{tool_name}' completed successfully", "success")
            else:
                self.current_tool_label.setText("❌ Tool failed")
                self.current_tool_label.setStyleSheet("color: #dc3545; font-size: 11px;")
                error = result.get("error", "Unknown error")
                self._add_tool_status(f"Tool '{tool_name}' failed: {error}", "error")
            
            # Add tool call to chat
            parameters = result.get("parameters", {})
            self._add_tool_call_message(tool_name, parameters, result)
            
            # Reset to idle after a delay
            QTimer.singleShot(3000, lambda: self._reset_tool_status())
            
        except Exception as e:
            self._logger.error(f"Error handling tool execution completed: {e}")
    
    # Helper methods for streaming UI
    def _create_streaming_message(self) -> QLabel:
        """Create a streaming message widget."""
        try:
            msg_container = QWidget()
            msg_layout = QHBoxLayout(msg_container)
            msg_layout.setContentsMargins(5, 2, 5, 2)
            msg_layout.setSpacing(0)
            
            # Create streaming label
            streaming_label = QLabel("🤔 Thinking...")
            streaming_label.setWordWrap(True)
            streaming_label.setStyleSheet("""
                background-color: #f8f9fa;
                color: #333;
                padding: 10px 14px;
                border-radius: 15px;
                border: 2px dashed #0078d4;
                font-size: 13px;
            """)
            msg_layout.addWidget(streaming_label, stretch=2)
            
            # Add spacer for left alignment
            spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            msg_layout.addItem(spacer)
            
            # Insert before the stretch at the end
            self._chat_layout.insertWidget(self._chat_layout.count() - 1, msg_container)
            self._scroll_to_bottom()
            
            return streaming_label
            
        except Exception as e:
            self._logger.error(f"Error creating streaming message: {e}")
            return None
    
    def _add_reasoning_message(self, reasoning_text: str):
        """Add reasoning message to chat display."""
        try:
            msg_container = QWidget()
            msg_layout = QHBoxLayout(msg_container)
            msg_layout.setContentsMargins(5, 2, 5, 2)
            msg_layout.setSpacing(0)
            
            # Reasoning icon
            icon_label = QLabel("🧠")
            icon_label.setStyleSheet("font-size: 16px; padding: 5px;")
            msg_layout.addWidget(icon_label)
            
            # Reasoning text
            reasoning_label = QLabel(f"Reasoning: {reasoning_text}")
            reasoning_label.setWordWrap(True)
            reasoning_label.setStyleSheet("""
                background-color: #fff3cd;
                color: #856404;
                padding: 8px 12px;
                border-radius: 12px;
                border-left: 4px solid #ffc107;
                font-size: 12px;
                font-style: italic;
            """)
            msg_layout.addWidget(reasoning_label, stretch=2)
            
            # Add spacer for left alignment
            spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            msg_layout.addItem(spacer)
            
            # Insert before the stretch at the end
            self._chat_layout.insertWidget(self._chat_layout.count() - 1, msg_container)
            self._scroll_to_bottom()
            
        except Exception as e:
            self._logger.error(f"Error adding reasoning message: {e}")
    
    def _update_process_step(self, step_name: str, description: str):
        """Update the current process step display."""
        try:
            self.current_step_label.setText(f"⚙️ {description}")
            self.current_step_label.setStyleSheet("color: #0078d4; font-size: 11px;")
            
        except Exception as e:
            self._logger.error(f"Error updating process step: {e}")
    
    def _reset_step_status(self):
        """Reset step status to ready."""
        try:
            self.current_step_label.setText("⏸️ Ready")
            self.current_step_label.setStyleSheet("color: #666; font-size: 11px;")
        except Exception as e:
            self._logger.error(f"Error resetting step status: {e}")