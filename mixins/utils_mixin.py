"""
Utils Mixin - Utility functions and helper methods
"""
from PySide6.QtCore import QTimer


class UtilsMixin:
    """Mixin class for utility functions and helper methods"""

    def scroll_to_bottom(self):
        """Scroll chat to bottom"""
        QTimer.singleShot(50, lambda: self.chat_scroll.verticalScrollBar().setValue(
            self.chat_scroll.verticalScrollBar().maximum()
        ))
    
    def show_feedback_dialog(self):
        """Show the feedback dialog"""
        from widgets.feedback_dialog import FeedbackDialog
        
        # Load endpoint URL from config
        endpoint_url = self.load_feedback_endpoint()
        
        # Show dialog
        dialog = FeedbackDialog(self, endpoint_url)
        dialog.exec()
    
    def load_feedback_endpoint(self):
        """Load feedback endpoint URL from config file"""
        import json
        from pathlib import Path
        
        config_file = Path("feedback_config.json")
        
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    return config.get('endpoint_url', 'https://formspree.io/f/YOUR_FORM_ID')
            except Exception as e:
                print(f"Error loading feedback config: {e}")
        
        # Return default - YOU MUST REPLACE THIS WITH YOUR ACTUAL FORMSPREE URL
        return "https://formspree.io/f/YOUR_FORM_ID"