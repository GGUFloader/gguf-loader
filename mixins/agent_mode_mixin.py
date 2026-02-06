"""
Agent Mode Mixin - Handles agent mode functionality in main chat window
"""
import logging
from pathlib import Path
from PySide6.QtWidgets import QFileDialog, QLabel, QWidget, QHBoxLayout
from PySide6.QtCore import Qt


class AgentModeMixin:
    """Mixin class for handling agent mode functionality"""

    def toggle_agent_mode_button(self, checked: bool):
        self.toggle_agent_mode(checked)
        if hasattr(self, 'agent_mode_btn'):
            self.agent_mode_btn.setText('🤖 Agent Mode: ON' if checked else '🤖 Agent Mode: OFF')

    def toggle_agent_mode(self, enabled: bool):
        try:
            if not hasattr(self, '_logger'):
                self._logger = logging.getLogger(__name__)
            self.agent_mode_enabled = enabled
            if hasattr(self, 'workspace_label'):
                self.workspace_label.setVisible(enabled)
            if hasattr(self, 'workspace_combo'):
                self.workspace_combo.setVisible(enabled)
            if hasattr(self, 'workspace_browse_btn'):
                self.workspace_browse_btn.setVisible(enabled)
            if hasattr(self, 'agent_status_label'):
                self.agent_status_label.setVisible(enabled)
            if enabled:
                self._update_agent_status('🟡 Initializing...')
                self._initialize_simple_agent()
                if hasattr(self, 'input_text'):
                    self.input_text.setPlaceholderText('Type your message to the agent...')
            else:
                self._update_agent_status('⚪ Ready')
                self.simple_agent = None
                if hasattr(self, 'input_text'):
                    self.input_text.setPlaceholderText('Type your message here...')
        except Exception as e:
            self._logger.error(f'Error toggling agent mode: {e}')

    def browse_workspace(self):
        try:
            dialog = QFileDialog()
            workspace_path = dialog.getExistingDirectory(self, 'Select Workspace Directory', str(Path.home()), QFileDialog.Option.ShowDirsOnly)
            if workspace_path:
                self.workspace_combo.setCurrentText(workspace_path)
                if self.agent_mode_enabled:
                    self._initialize_simple_agent()
        except Exception as e:
            self._logger.error(f'Error browsing workspace: {e}')

    def _initialize_simple_agent(self):
        try:
            workspace_path = self.workspace_combo.currentText().strip()
            if not workspace_path:
                self._update_agent_status('⚠️ No workspace')
                return
            workspace = Path(workspace_path)
            workspace.mkdir(parents=True, exist_ok=True)
            if not hasattr(self, 'model') or not self.model:
                self._update_agent_status('❌ No model')
                self._add_agent_system_message('⚠️ Please load a model first')
                return
            from core.agent import SimpleAgent
            self.simple_agent = SimpleAgent(self.model, str(workspace))
            self.simple_agent.response_generated.connect(self._on_agent_response)
            self.simple_agent.tool_executed.connect(self._on_agent_tool_executed)
            self.simple_agent.error_occurred.connect(self._on_agent_error)
            self._update_agent_status('🟢 Ready')
            self._add_agent_system_message(f'🤖 Agent mode activated\n📁 Workspace: {workspace_path}')
        except Exception as e:
            self._logger.error(f'Error initializing agent: {e}')

    def _update_agent_status(self, status: str):
        try:
            if hasattr(self, 'agent_status_label'):
                self.agent_status_label.setText(status)
                if '🟢' in status:
                    self.agent_status_label.setStyleSheet('color: #28a745; font-size: 10px;')
                elif '🟡' in status:
                    self.agent_status_label.setStyleSheet('color: #ffc107; font-size: 10px;')
                elif '❌' in status:
                    self.agent_status_label.setStyleSheet('color: #dc3545; font-size: 10px;')
                else:
                    self.agent_status_label.setStyleSheet('color: #666; font-size: 10px;')
        except Exception as e:
            self._logger.error(f'Error updating status: {e}')

    def _add_agent_system_message(self, message: str):
        try:
            msg_container = QWidget()
            msg_layout = QHBoxLayout(msg_container)
            msg_layout.setContentsMargins(0, 5, 0, 5)
            msg_layout.addStretch()
            label = QLabel(message)
            label.setStyleSheet('QLabel { background-color: #e3f2fd; color: #1976d2; padding: 8px 12px; border-radius: 8px; font-size: 11px; border: 1px solid #90caf9; }')
            label.setWordWrap(True)
            msg_layout.addWidget(label)
            msg_layout.addStretch()
            if hasattr(self, 'chat_layout'):
                self.chat_layout.insertWidget(self.chat_layout.count() - 1, msg_container)
                if hasattr(self, 'scroll_to_bottom'):
                    self.scroll_to_bottom()
        except Exception as e:
            self._logger.error(f'Error adding system message: {e}')

    def send_message_to_agent(self, message: str) -> bool:
        try:
            if not self.agent_mode_enabled:
                return False
            if not hasattr(self, 'simple_agent') or not self.simple_agent:
                self._add_agent_system_message('⚠️ Agent not initialized')
                return True
            self._add_agent_system_message('🤔 Agent is processing...')
            self.simple_agent.process_message(message)
            return True
        except Exception as e:
            self._logger.error(f'Error sending to agent: {e}')
            return True

    def _on_agent_response(self, response: str):
        try:
            if hasattr(self, 'add_chat_message'):
                self.add_chat_message(response, is_user=False)
            if hasattr(self, 'send_btn'):
                self.send_btn.setEnabled(True)
        except Exception as e:
            self._logger.error(f'Error handling response: {e}')

    def _on_agent_tool_executed(self, result: dict):
        try:
            tool_name = result.get('tool_name', 'unknown')
            status = result.get('status', 'unknown')
            if status == 'success':
                self._add_agent_system_message(f'✅ Tool: {tool_name}')
            else:
                self._add_agent_system_message(f'❌ Tool failed: {tool_name}')
        except Exception as e:
            self._logger.error(f'Error handling tool: {e}')

    def _on_agent_error(self, error_message: str):
        try:
            self._add_agent_system_message(f'❌ Error: {error_message}')
            if hasattr(self, 'send_btn'):
                self.send_btn.setEnabled(True)
        except Exception as e:
            self._logger.error(f'Error handling error: {e}')
