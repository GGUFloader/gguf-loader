#!/usr/bin/env python3
"""
Status Widget for Agentic Chatbot Addon

Displays addon status in the GGUF Loader sidebar following the established pattern.
Shows agent status, workspace information, and provides controls for agent interaction.
"""

import logging
from typing import Optional, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QGroupBox, QProgressBar, QFrame
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

try:
    from config import FONT_FAMILY
except ImportError:
    FONT_FAMILY = "Segoe UI"


class AgenticChatbotStatusWidget(QWidget):
    """
    Status widget for the agentic chatbot addon.
    
    Displays in the GGUF Loader sidebar and provides:
    - Addon status and health indicators
    - Active session information
    - Workspace details
    - Quick action buttons
    - Tool execution status
    """
    
    def __init__(self, addon_instance: Any):
        super().__init__()
        
        self.addon = addon_instance
        self._logger = logging.getLogger(__name__)
        
        # UI components
        self._agent_window: Optional[Any] = None
        self._status_timer: Optional[QTimer] = None
        
        # Setup UI
        self._setup_ui()
        self._connect_signals()
        self._start_status_updates()
        
        # Initial status update
        self._update_status()
    
    def _setup_ui(self):
        """Setup the status widget UI following existing patterns."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)
        
        # Title with icon
        title_layout = QHBoxLayout()
        
        title = QLabel("🤖 Agentic Chatbot")
        title.setFont(QFont(FONT_FAMILY, 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #0078d4; padding: 2px;")
        title_layout.addWidget(title)
        
        title_layout.addStretch()
        
        layout.addLayout(title_layout)
        
        # Status indicators group
        status_group = QGroupBox("Status")
        status_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #ddd;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px 0 4px;
            }
        """)
        status_layout = QVBoxLayout(status_group)
        status_layout.setSpacing(6)
        
        # Addon status
        self.addon_status_label = QLabel("🟡 Starting...")
        self.addon_status_label.setStyleSheet("color: #ffc107; font-size: 12px;")
        status_layout.addWidget(self.addon_status_label)
        
        # Model status
        self.model_status_label = QLabel("⚪ Model: Not loaded")
        self.model_status_label.setStyleSheet("color: #666; font-size: 11px;")
        status_layout.addWidget(self.model_status_label)
        
        # Session status
        self.session_status_label = QLabel("📍 No active session")
        self.session_status_label.setStyleSheet("color: #666; font-size: 11px;")
        status_layout.addWidget(self.session_status_label)
        
        # Tools status
        self.tools_status_label = QLabel("🔧 Tools: Not initialized")
        self.tools_status_label.setStyleSheet("color: #666; font-size: 11px;")
        status_layout.addWidget(self.tools_status_label)
        
        layout.addWidget(status_group)
        
        # Workspace info group
        workspace_group = QGroupBox("Workspace")
        workspace_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #ddd;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px 0 4px;
            }
        """)
        workspace_layout = QVBoxLayout(workspace_group)
        workspace_layout.setSpacing(4)
        
        self.workspace_info_label = QLabel("No workspace selected")
        self.workspace_info_label.setWordWrap(True)
        self.workspace_info_label.setStyleSheet("color: #666; font-size: 10px;")
        workspace_layout.addWidget(self.workspace_info_label)
        
        layout.addWidget(workspace_group)
        
        # Action buttons
        buttons_layout = QVBoxLayout()
        buttons_layout.setSpacing(8)
        
        # Open agent window button
        self.open_window_btn = QPushButton("💬 Open Agent Chat")
        self.open_window_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 12px;
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
        """)
        self.open_window_btn.clicked.connect(self._toggle_agent_window)
        buttons_layout.addWidget(self.open_window_btn)
        
        # Quick workspace button
        self.quick_workspace_btn = QPushButton("📁 Quick Workspace")
        self.quick_workspace_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.quick_workspace_btn.clicked.connect(self._create_quick_workspace)
        buttons_layout.addWidget(self.quick_workspace_btn)
        
        layout.addLayout(buttons_layout)
        
        # Activity indicator
        activity_frame = QFrame()
        activity_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #ddd;
                border-radius: 6px;
                background-color: #f8f9fa;
                padding: 6px;
            }
        """)
        activity_layout = QVBoxLayout(activity_frame)
        activity_layout.setContentsMargins(6, 6, 6, 6)
        activity_layout.setSpacing(4)
        
        activity_title = QLabel("Activity")
        activity_title.setFont(QFont(FONT_FAMILY, 10, QFont.Weight.Bold))
        activity_title.setStyleSheet("color: #333;")
        activity_layout.addWidget(activity_title)
        
        self.activity_label = QLabel("💤 Idle")
        self.activity_label.setStyleSheet("color: #666; font-size: 10px;")
        activity_layout.addWidget(self.activity_label)
        
        # Progress bar for tool execution
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumHeight(4)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 2px;
                background-color: #e9ecef;
            }
            QProgressBar::chunk {
                background-color: #0078d4;
                border-radius: 2px;
            }
        """)
        activity_layout.addWidget(self.progress_bar)
        
        layout.addWidget(activity_frame)
        
        # Description
        desc = QLabel("Autonomous agent with tool-calling capabilities. "
                     "Provides file operations, command execution, and workspace management.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666; font-size: 10px; padding: 4px;")
        layout.addWidget(desc)
        
        layout.addStretch()
    
    def _connect_signals(self):
        """Connect signals from addon components."""
        try:
            if self.addon:
                # Connect to addon signals
                if hasattr(self.addon, 'addon_started'):
                    self.addon.addon_started.connect(self._on_addon_started)
                
                if hasattr(self.addon, 'addon_stopped'):
                    self.addon.addon_stopped.connect(self._on_addon_stopped)
                
                if hasattr(self.addon, 'agent_session_created'):
                    self.addon.agent_session_created.connect(self._on_session_created)
                
                if hasattr(self.addon, 'tool_call_executed'):
                    self.addon.tool_call_executed.connect(self._on_tool_executed)
                
                # Connect to main app signals if available
                if hasattr(self.addon, 'gguf_app') and self.addon.gguf_app:
                    if hasattr(self.addon.gguf_app, 'model_loaded'):
                        self.addon.gguf_app.model_loaded.connect(self._on_model_loaded)
                        
        except Exception as e:
            self._logger.error(f"Error connecting signals: {e}")
    
    def _start_status_updates(self):
        """Start periodic status updates."""
        try:
            self._status_timer = QTimer()
            self._status_timer.timeout.connect(self._update_status)
            self._status_timer.start(5000)  # Update every 5 seconds
        except Exception as e:
            self._logger.error(f"Error starting status updates: {e}")
    
    def _update_status(self):
        """Update all status indicators."""
        try:
            # Update addon status
            if self.addon and self.addon.is_running():
                self.addon_status_label.setText("🟢 Active")
                self.addon_status_label.setStyleSheet("color: #28a745; font-size: 12px;")
                self.open_window_btn.setEnabled(True)
                self.quick_workspace_btn.setEnabled(True)
            else:
                self.addon_status_label.setText("🔴 Inactive")
                self.addon_status_label.setStyleSheet("color: #dc3545; font-size: 12px;")
                self.open_window_btn.setEnabled(False)
                self.quick_workspace_btn.setEnabled(False)
            
            # Update model status
            self._update_model_status()
            
            # Update session status
            self._update_session_status()
            
            # Update tools status
            self._update_tools_status()
            
        except Exception as e:
            self._logger.error(f"Error updating status: {e}")
    
    def _update_model_status(self):
        """Update model status indicator."""
        try:
            if (self.addon and 
                hasattr(self.addon, 'gguf_app') and 
                hasattr(self.addon.gguf_app, 'model') and 
                self.addon.gguf_app.model is not None):
                self.model_status_label.setText("🟢 Model: Ready")
                self.model_status_label.setStyleSheet("color: #28a745; font-size: 11px;")
            else:
                self.model_status_label.setText("🔴 Model: Not loaded")
                self.model_status_label.setStyleSheet("color: #dc3545; font-size: 11px;")
        except Exception as e:
            self._logger.debug(f"Error updating model status: {e}")
    
    def _update_session_status(self):
        """Update session status indicator."""
        try:
            if self.addon and hasattr(self.addon, 'get_active_sessions'):
                active_sessions = self.addon.get_active_sessions()
                if active_sessions:
                    session_count = len(active_sessions)
                    if session_count == 1:
                        session_id = active_sessions[0][:8]
                        self.session_status_label.setText(f"🟢 Session: {session_id}...")
                    else:
                        self.session_status_label.setText(f"🟢 Sessions: {session_count} active")
                    self.session_status_label.setStyleSheet("color: #28a745; font-size: 11px;")
                else:
                    self.session_status_label.setText("📍 No active session")
                    self.session_status_label.setStyleSheet("color: #666; font-size: 11px;")
            else:
                self.session_status_label.setText("📍 No active session")
                self.session_status_label.setStyleSheet("color: #666; font-size: 11px;")
        except Exception as e:
            self._logger.debug(f"Error updating session status: {e}")
    
    def _update_tools_status(self):
        """Update tools status indicator."""
        try:
            if (self.addon and 
                hasattr(self.addon, '_tool_registry') and 
                self.addon._tool_registry):
                available_tools = self.addon._tool_registry.get_available_tools()
                tool_count = len(available_tools)
                self.tools_status_label.setText(f"🟢 Tools: {tool_count} available")
                self.tools_status_label.setStyleSheet("color: #28a745; font-size: 11px;")
            else:
                self.tools_status_label.setText("🔧 Tools: Not initialized")
                self.tools_status_label.setStyleSheet("color: #666; font-size: 11px;")
        except Exception as e:
            self._logger.debug(f"Error updating tools status: {e}")
    
    def _toggle_agent_window(self):
        """Toggle agent window visibility."""
        try:
            if self._agent_window and not self._agent_window.isHidden():
                # Window is open, close it
                self._agent_window.hide()
                self.open_window_btn.setText("💬 Open Agent Chat")
            else:
                # Window is closed or doesn't exist, open it
                self._show_agent_window()
                self.open_window_btn.setText("🔽 Hide Agent Chat")
                
        except Exception as e:
            self._logger.error(f"Error toggling agent window: {e}")
    
    def _show_agent_window(self):
        """Show the agent window."""
        try:
            if not self._agent_window:
                # Import here to avoid circular imports
                from .agent_window import AgentWindow
                self._agent_window = AgentWindow(self.addon)
                
                # Connect window signals
                self._agent_window.window_closed.connect(self._on_agent_window_closed)
                self._agent_window.session_created.connect(self._on_session_created)
            
            self._agent_window.show()
            self._agent_window.raise_()
            self._agent_window.activateWindow()
            
        except Exception as e:
            self._logger.error(f"Error showing agent window: {e}")
    
    def _create_quick_workspace(self):
        """Create a quick workspace and start a session."""
        try:
            import tempfile
            from pathlib import Path
            
            # Create temporary workspace
            temp_dir = tempfile.mkdtemp(prefix="agent_workspace_")
            workspace_path = Path(temp_dir)
            
            # Create session
            if self.addon and hasattr(self.addon, 'create_agent_session'):
                session_id = self.addon.create_agent_session(str(workspace_path))
                if session_id:
                    self.workspace_info_label.setText(f"Quick workspace:\n{workspace_path.name}")
                    self._show_agent_window()
                else:
                    self._logger.error("Failed to create quick workspace session")
            
        except Exception as e:
            self._logger.error(f"Error creating quick workspace: {e}")
    
    def _set_activity(self, activity: str, show_progress: bool = False):
        """Set current activity indicator."""
        try:
            self.activity_label.setText(activity)
            
            if show_progress:
                self.progress_bar.setVisible(True)
                self.progress_bar.setRange(0, 0)  # Indeterminate progress
            else:
                self.progress_bar.setVisible(False)
                
        except Exception as e:
            self._logger.error(f"Error setting activity: {e}")
    
    # Signal handlers
    def _on_addon_started(self):
        """Handle addon started signal."""
        try:
            self._update_status()
        except Exception as e:
            self._logger.error(f"Error handling addon started: {e}")
    
    def _on_addon_stopped(self):
        """Handle addon stopped signal."""
        try:
            self._update_status()
            if self._agent_window:
                self._agent_window.close()
                self._agent_window = None
        except Exception as e:
            self._logger.error(f"Error handling addon stopped: {e}")
    
    def _on_model_loaded(self, model):
        """Handle model loaded signal."""
        try:
            self._update_model_status()
        except Exception as e:
            self._logger.error(f"Error handling model loaded: {e}")
    
    def _on_session_created(self, session_id: str):
        """Handle session created signal."""
        try:
            self._update_session_status()
            short_id = session_id[:8] if session_id else "unknown"
            self._set_activity(f"🚀 Session: {short_id}...")
            
            # Reset activity after delay
            QTimer.singleShot(3000, lambda: self._set_activity("💤 Idle"))
            
        except Exception as e:
            self._logger.error(f"Error handling session created: {e}")
    
    def _on_tool_executed(self, result):
        """Handle tool execution result."""
        try:
            tool_name = result.get("tool_name", "unknown")
            status = result.get("status", "unknown")
            
            if status == "success":
                self._set_activity(f"✅ Tool: {tool_name}")
            else:
                self._set_activity(f"❌ Tool: {tool_name}")
            
            # Reset activity after delay
            QTimer.singleShot(3000, lambda: self._set_activity("💤 Idle"))
            
        except Exception as e:
            self._logger.error(f"Error handling tool executed: {e}")
    
    def _on_agent_window_closed(self):
        """Handle agent window closed signal."""
        try:
            self.open_window_btn.setText("💬 Open Agent Chat")
        except Exception as e:
            self._logger.error(f"Error handling agent window closed: {e}")
    
    def is_agent_window_visible(self) -> bool:
        """Check if agent window is visible."""
        try:
            return self._agent_window is not None and not self._agent_window.isHidden()
        except Exception:
            return False
    
    def closeEvent(self, event):
        """Handle widget close event."""
        try:
            # Stop status timer
            if self._status_timer:
                self._status_timer.stop()
                self._status_timer = None
            
            # Close agent window
            if self._agent_window:
                self._agent_window.close()
                self._agent_window = None
            
            super().closeEvent(event)
            
        except Exception as e:
            self._logger.error(f"Error handling close event: {e}")
            super().closeEvent(event)