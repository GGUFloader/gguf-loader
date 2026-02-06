"""
Agent Mode Mixin - Handles agent mode functionality in main chat window
"""
import logging
from pathlib import Path
from typing import Optional
from PySide6.QtWidgets import QFileDialog, QLabel, QWidget, QHBoxLayout
from PySide6.QtCore import Qt


class AgentModeMixin:
    """Mixin class for handling agent mode functionality"""

    def toggle_agent_mode_button(self, checked: bool):
        """Toggle agent mode on/off from button click"""
        self.toggle_agent_mode(checked)
        
        # Update button text
        if hasattr(self, 'agent_mode_btn'):
            if checked:
                self.agent_mode_btn.setText("🤖 Agent Mode: ON")
            else:
                self.agent_mode_btn.setText("🤖 Agent Mode: OFF")

    def toggle_agent_mode(self, enabled: bool):
        """Toggle agent mode on/off"""
        try:
            if not hasattr(self, '_logger'):
                self._logger = logging.getLogger(__name__)
            
            self.agent_mode_enabled = enabled
            
            # Show/hide workspace controls
            if hasattr(self, 'workspace_label'):
                self.workspace_label.setVisible(enabled)
            if hasattr(self, 'workspace_combo'):
                self.workspace_combo.setVisible(enabled)
            if hasattr(self, 'workspace_browse_btn'):
                self.workspace_browse_btn.setVisible(enabled)
            if hasattr(self, 'agent_status_label'):
                self.agent_status_label.setVisible(enabled)
            
            if enabled:
                self._update_agent_status("🟡 Initializing...")
                self._initialize_simple_agent()
                if hasattr(self, 'input_text'):
                    self.input_text.setPlaceholderText("Type your message to the agent...")
            else:
                self._update_agent_status("⚪ Ready")
                self.simple_agent = None
                self.agent_workspace_path = None
                if hasattr(self, 'input_text'):
                    self.input_text.setPlaceholderText("Type your message here...")
                    
        except Exception as e:
            self._logger.error(f"Error toggling agent mode: {e}")
            self._update_agent_status("❌ Error")

    def browse_workspace(self):
        """Browse for workspace directory"""
        try:
            dialog = QFileDialog()
            workspace_path = dialog.getExistingDirectory(
                self, "Select Workspace Directory", str(Path.home()),
                QFileDialog.Option.ShowDirsOnly
            )
            
            if workspace_path:
                self.workspace_combo.setCurrentText(workspace_path)
                if self.agent_mode_enabled:
                    self._initialize_simple_agent()
                    
        except Exception as e:
            self._logger.error(f"Error browsing workspace: {e}")

    def _initialize_simple_agent(self):
        """Initialize simple agent"""
        try:
            workspace_path = self.workspace_combo.currentText().strip()
            if not workspace_path:
                self._update_agent_status("⚠️ No workspace")
                return
            
            workspace = Path(workspace_path)
            workspace.mkdir(parents=True, exist_ok=True)
            
            if not hasattr(self, 'model') or not self.model:
                self._update_agent_status("❌ No model")
                self._add_agent_system_message("⚠️ Please load a model first")
                return
            
            from core.agent import SimpleAgent
            
            self.simple_agent = SimpleAgent(self.model, str(workspace))
            self.agent_workspace_path = str(workspace)
            
            # Connect all signals
            self.simple_agent.response_generated.connect(self._on_agent_response)
            self.simple_agent.tool_executed.connect(self._on_agent_tool_executed)
            self.simple_agent.error_occurred.connect(self._on_agent_error)
            self.simple_agent.processing_started.connect(self._on_agent_processing_started)
            self.simple_agent.processing_finished.connect(self._on_agent_processing_finished)
            self.simple_agent.status_update.connect(self._on_agent_status_update)
            
            self._update_agent_status("🟢 Ready")
            self._add_agent_system_message(f"🤖 Agent mode activated\n📁 Workspace: {workspace_path}")
                
        except Exception as e:
            self._logger.error(f"Error initializing agent: {e}")
            self._update_agent_status("❌ Error")

    def _update_agent_status(self, status: str):
        """Update agent status label"""
        try:
            if hasattr(self, 'agent_status_label'):
                self.agent_status_label.setText(status)
                if "🟢" in status:
                    self.agent_status_label.setStyleSheet("color: #28a745; font-size: 10px;")
                elif "🟡" in status:
                    self.agent_status_label.setStyleSheet("color: #ffc107; font-size: 10px;")
                elif "❌" in status:
                    self.agent_status_label.setStyleSheet("color: #dc3545; font-size: 10px;")
                else:
                    self.agent_status_label.setStyleSheet("color: #666; font-size: 10px;")
        except Exception as e:
            self._logger.error(f"Error updating status: {e}")

    def _add_agent_system_message(self, message: str):
        """Add system message to chat"""
        try:
            msg_container = QWidget()
            msg_layout = QHBoxLayout(msg_container)
            msg_layout.setContentsMargins(0, 5, 0, 5)
            msg_layout.addStretch()
            
            label = QLabel(message)
            label.setStyleSheet("""
                QLabel {
                    background-color: #e3f2fd;
                    color: #1976d2;
                    padding: 8px 12px;
                    border-radius: 8px;
                    font-size: 11px;
                    border: 1px solid #90caf9;
                }
            """)
            label.setWordWrap(True)
            msg_layout.addWidget(label)
            msg_layout.addStretch()
            
            if hasattr(self, 'chat_layout'):
                self.chat_layout.insertWidget(self.chat_layout.count() - 1, msg_container)
                if hasattr(self, 'scroll_to_bottom'):
                    self.scroll_to_bottom()
                    
        except Exception as e:
            self._logger.error(f"Error adding system message: {e}")

    def send_message_to_agent(self, message: str) -> bool:
        """Send message to agent"""
        try:
            if not self.agent_mode_enabled:
                return False
            
            if not hasattr(self, 'simple_agent') or not self.simple_agent:
                self._add_agent_system_message("⚠️ Agent not initialized")
                return True
            
            # Disable send button during processing
            if hasattr(self, 'send_btn'):
                self.send_btn.setEnabled(False)
            
            # Update status
            self._update_agent_status("🟡 Processing...")
            
            # Process message asynchronously
            self.simple_agent.process_message(message)
            return True
            
        except Exception as e:
            self._logger.error(f"Error sending to agent: {e}")
            self._add_agent_system_message(f"❌ Error: {str(e)[:50]}")
            if hasattr(self, 'send_btn'):
                self.send_btn.setEnabled(True)
            return True
    
    def _on_agent_processing_started(self):
        """Handle agent processing started"""
        try:
            self._update_agent_status("🟡 Processing...")
            if hasattr(self, 'send_btn'):
                self.send_btn.setEnabled(False)
            if hasattr(self, 'input_text'):
                self.input_text.setEnabled(False)
        except Exception as e:
            self._logger.error(f"Error handling processing started: {e}")
    
    def _on_agent_processing_finished(self):
        """Handle agent processing finished"""
        try:
            self._update_agent_status("🟢 Ready")
            if hasattr(self, 'send_btn'):
                self.send_btn.setEnabled(True)
            if hasattr(self, 'input_text'):
                self.input_text.setEnabled(True)
        except Exception as e:
            self._logger.error(f"Error handling processing finished: {e}")
    
    def _on_agent_status_update(self, status_message: str):
        """Handle agent status updates - stream to chat"""
        try:
            # Determine message type and style accordingly
            is_thinking = any(word in status_message.lower() for word in ['thinking', 'thoughts', 'analyzing', 'reading'])
            is_plan = 'plan' in status_message.lower() or 'complete' in status_message.lower()
            is_working = 'focusing' in status_message.lower() or 'working' in status_message.lower()
            is_why = 'why:' in status_message.lower()
            is_result = 'result:' in status_message.lower() or 'update:' in status_message.lower()
            is_next = 'next:' in status_message.lower() or 'moving' in status_message.lower()
            
            # Create message widget
            msg_container = QWidget()
            msg_layout = QHBoxLayout(msg_container)
            msg_layout.setContentsMargins(5, 3, 5, 3)
            
            label = QLabel(status_message)
            label.setWordWrap(True)
            label.setTextFormat(Qt.TextFormat.PlainText)
            
            # Style based on message type
            if is_thinking:
                # Thinking messages - purple/blue
                label.setStyleSheet("""
                    QLabel {
                        background-color: #e8eaf6;
                        color: #3f51b5;
                        padding: 8px 12px;
                        border-radius: 8px;
                        font-size: 12px;
                        font-weight: 500;
                        border-left: 4px solid #3f51b5;
                    }
                """)
            elif is_plan:
                # Plan messages - green
                label.setStyleSheet("""
                    QLabel {
                        background-color: #e8f5e9;
                        color: #2e7d32;
                        padding: 10px 14px;
                        border-radius: 8px;
                        font-size: 12px;
                        font-weight: 600;
                        border-left: 4px solid #4caf50;
                        white-space: pre-wrap;
                    }
                """)
            elif is_working:
                # Working messages - orange
                label.setStyleSheet("""
                    QLabel {
                        background-color: #fff3e0;
                        color: #e65100;
                        padding: 8px 12px;
                        border-radius: 8px;
                        font-size: 12px;
                        font-weight: 500;
                        border-left: 4px solid #ff9800;
                    }
                """)
            elif is_why:
                # Reasoning messages - teal
                label.setStyleSheet("""
                    QLabel {
                        background-color: #e0f2f1;
                        color: #00695c;
                        padding: 8px 12px;
                        border-radius: 8px;
                        font-size: 11px;
                        font-style: italic;
                        border-left: 4px solid #009688;
                    }
                """)
            elif is_result:
                # Result messages - green
                label.setStyleSheet("""
                    QLabel {
                        background-color: #e8f5e9;
                        color: #1b5e20;
                        padding: 8px 12px;
                        border-radius: 8px;
                        font-size: 12px;
                        font-weight: 500;
                        border-left: 4px solid #4caf50;
                    }
                """)
            elif is_next:
                # Next task messages - blue
                label.setStyleSheet("""
                    QLabel {
                        background-color: #e3f2fd;
                        color: #1565c0;
                        padding: 8px 12px;
                        border-radius: 8px;
                        font-size: 11px;
                        border-left: 4px solid #2196f3;
                    }
                """)
            else:
                # Default messages - gray
                label.setStyleSheet("""
                    QLabel {
                        background-color: #f5f5f5;
                        color: #616161;
                        padding: 8px 12px;
                        border-radius: 8px;
                        font-size: 11px;
                        border-left: 4px solid #9e9e9e;
                    }
                """)
            
            msg_layout.addWidget(label)
            
            if hasattr(self, 'chat_layout'):
                self.chat_layout.insertWidget(self.chat_layout.count() - 1, msg_container)
                if hasattr(self, 'scroll_to_bottom'):
                    self.scroll_to_bottom()
        except Exception as e:
            self._logger.error(f"Error displaying status update: {e}")

    def _on_agent_response(self, response: str):
        """Handle agent response"""
        try:
            if hasattr(self, 'add_chat_message'):
                self.add_chat_message(response, is_user=False)
        except Exception as e:
            self._logger.error(f"Error handling response: {e}")

    def _on_agent_tool_executed(self, result: dict):
        """Handle tool execution"""
        try:
            tool_name = result.get('tool_name', 'unknown')
            status = result.get('status', 'unknown')
            
            # Create detailed feedback message
            if status == 'success':
                # Get specific result details
                if tool_name == 'write_file':
                    path = result.get('path', 'file')
                    bytes_written = result.get('bytes_written', 0)
                    message = f"✅ Wrote {bytes_written} bytes to {path}"
                elif tool_name == 'edit_file':
                    path = result.get('path', 'file')
                    operation = result.get('operation', 'edit')
                    changes = result.get('changes_made', 0)
                    message = f"✅ Performed {operation} on {path} ({changes} changes)"
                elif tool_name == 'read_file':
                    message = f"✅ Read file successfully"
                elif tool_name == 'list_directory':
                    items = result.get('result', [])
                    message = f"✅ Listed directory ({len(items)} items)"
                elif tool_name == 'search_files':
                    matches = result.get('total_matches', 0)
                    message = f"✅ Search completed ({matches} matches)"
                else:
                    message = f"✅ {tool_name} completed"
                
                self._add_agent_system_message(message)
            else:
                error = result.get('error', 'Unknown error')
                self._add_agent_system_message(f"❌ {tool_name} failed: {error}")
        except Exception as e:
            self._logger.error(f"Error handling tool: {e}")

    def _on_agent_error(self, error_message: str):
        """Handle agent error"""
        try:
            self._add_agent_system_message(f"❌ Error: {error_message}")
            self._update_agent_status("🟢 Ready")
        except Exception as e:
            self._logger.error(f"Error handling error: {e}")
