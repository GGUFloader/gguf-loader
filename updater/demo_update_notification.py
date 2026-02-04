"""
Demo script to show the update notification banner
This creates a simple window with the update notification
"""
import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel
from PySide6.QtCore import Qt
from widgets.update_notification import UpdateNotificationManager

class DemoWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Update Notification Demo")
        self.setMinimumSize(800, 400)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # Add update notification manager
        self.update_manager = UpdateNotificationManager(self)
        layout.addWidget(self.update_manager)
        
        # Add some content
        content = QLabel(
            "This is a demo of the update notification system.\n\n"
            "The blue banner above shows what users will see when\n"
            "a new version is available.\n\n"
            "Try clicking the buttons to see how they work!"
        )
        content.setAlignment(Qt.AlignCenter)
        content.setStyleSheet("""
            QLabel {
                font-size: 16px;
                padding: 40px;
                color: #64748b;
            }
        """)
        layout.addWidget(content, 1)
        
        # Show demo notification
        self.show_demo_notification()
    
    def show_demo_notification(self):
        """Show a demo update notification"""
        demo_update_info = {
            'available': True,
            'current_version': '2.0.1',
            'latest_version': '2.1.0',
            'download_url': 'https://github.com/GGUFloader/gguf-loader/releases/download/v2.1.0/GGUFLoader_v2.1.0.exe',
            'release_url': 'https://github.com/GGUFloader/gguf-loader/releases/tag/v2.1.0',
            'release_notes': 'Demo release notes...'
        }
        self.update_manager.show_update_notification(demo_update_info)

def main():
    app = QApplication(sys.argv)
    window = DemoWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
