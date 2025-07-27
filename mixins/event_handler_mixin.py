"""
Event Handler Mixin - Handles system events and user interactions
"""
from PySide6.QtCore import Qt


class EventHandlerMixin:
    """Mixin class for handling system events and user interactions"""

    def eventFilter(self, obj, event):
        """Handle Enter key press in input field"""
        if obj == self.input_text:
            if event.type() == event.Type.KeyPress:
                if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
                    if not event.modifiers() & Qt.ShiftModifier:
                        self.send_message()
                        return True
        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        """Handle application close event"""
        try:
            # Stop any running generation
            if hasattr(self, 'chat_generator') and self.chat_generator:
                if self.chat_generator.isRunning():
                    self.chat_generator.terminate()
                    self.chat_generator.wait(3000)  # Wait up to 3 seconds

            # Stop model loader if running
            if hasattr(self, 'model_loader') and self.model_loader:
                if self.model_loader.isRunning():
                    self.model_loader.terminate()
                    self.model_loader.wait(3000)

            # Cleanup addons
            if hasattr(self, '_smart_floater_addon'):
                try:
                    self._smart_floater_addon.stop()
                except Exception as e:
                    print(f"Error stopping smart floater addon: {e}")

            event.accept()
        except Exception as e:
            print(f"Error during cleanup: {e}")
            event.accept()