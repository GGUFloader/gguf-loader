"""
Feedback Dialog Widget - Allows users to send feedback via email
Uses web service API for seamless sending without user configuration
"""
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QTextEdit, QLineEdit, QPushButton, QComboBox,
    QMessageBox, QProgressBar
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont

from config import FONT_FAMILY


class EmailSenderThread(QThread):
    """Background thread for sending emails via web service"""
    success = Signal()
    error = Signal(str)
    
    def __init__(self, endpoint_url, subject, message, user_email, feedback_type):
        super().__init__()
        self.endpoint_url = endpoint_url
        self.subject = subject
        self.message = message
        self.user_email = user_email
        self.feedback_type = feedback_type
    
    def run(self):
        """Send email via web service in background thread"""
        try:
            # Prepare data
            data = {
                'email': self.user_email,
                'subject': self.subject,
                'message': self.message,
                'feedback_type': self.feedback_type,
                '_subject': self.subject  # FormSpree specific
            }
            
            # Convert to JSON
            json_data = json.dumps(data).encode('utf-8')
            
            # Create request
            request = Request(
                self.endpoint_url,
                data=json_data,
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                }
            )
            
            # Send request
            with urlopen(request, timeout=10) as response:
                if response.status in (200, 201):
                    self.success.emit()
                else:
                    self.error.emit(f"Server returned status {response.status}")
                    
        except Exception as e:
            self.error.emit(str(e))


class FeedbackDialog(QDialog):
    """Dialog for collecting and sending user feedback"""
    
    def __init__(self, parent=None, endpoint_url=None):
        super().__init__(parent)
        self.endpoint_url = endpoint_url or "https://formspree.io/f/YOUR_FORM_ID"
        self.email_thread = None
        
        self.setWindowTitle("Send Feedback")
        self.setMinimumSize(500, 450)
        self.setModal(True)
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the feedback dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("📧 Send Feedback")
        title.setFont(QFont(FONT_FAMILY, 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Description
        desc = QLabel("We'd love to hear from you! Share your thoughts, report bugs, or suggest features.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(desc)
        
        # Feedback type
        type_layout = QHBoxLayout()
        type_label = QLabel("Type:")
        type_label.setMinimumWidth(80)
        self.feedback_type = QComboBox()
        self.feedback_type.addItems([
            "General Feedback",
            "Bug Report",
            "Feature Request",
            "Question",
            "Other"
        ])
        type_layout.addWidget(type_label)
        type_layout.addWidget(self.feedback_type)
        layout.addLayout(type_layout)
        
        # User email (REQUIRED for response)
        email_layout = QHBoxLayout()
        email_label = QLabel("Your Email:")
        email_label.setMinimumWidth(80)
        self.user_email = QLineEdit()
        self.user_email.setPlaceholderText("your.email@example.com")
        email_layout.addWidget(email_label)
        email_layout.addWidget(self.user_email)
        layout.addLayout(email_layout)
        
        # Email hint
        email_hint = QLabel("💡 We'll use this to respond to your feedback")
        email_hint.setStyleSheet("color: #666; font-size: 10px; font-style: italic;")
        layout.addWidget(email_hint)
        
        # Message
        message_label = QLabel("Message:")
        layout.addWidget(message_label)
        
        self.message_text = QTextEdit()
        self.message_text.setPlaceholderText("Tell us what's on your mind...")
        self.message_text.setMinimumHeight(150)
        self.message_text.setFont(QFont(FONT_FAMILY, 12))
        layout.addWidget(self.message_text)
        
        # Progress bar (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: #666; font-size: 10px; font-style: italic;")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setMinimumSize(100, 35)
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        self.send_btn = QPushButton("Send Feedback")
        self.send_btn.setMinimumSize(120, 35)
        self.send_btn.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
        self.send_btn.clicked.connect(self.send_feedback)
        button_layout.addWidget(self.send_btn)
        
        layout.addLayout(button_layout)
    
    def send_feedback(self):
        """Send feedback using web service"""
        # Validate message
        message = self.message_text.toPlainText().strip()
        if not message:
            QMessageBox.warning(
                self,
                "Empty Message",
                "Please enter a message before sending."
            )
            return
        
        # Validate email
        user_email = self.user_email.text().strip()
        if not user_email:
            QMessageBox.warning(
                self,
                "Email Required",
                "Please enter your email address so we can respond to your feedback."
            )
            return
        
        # Basic email validation
        if '@' not in user_email or '.' not in user_email:
            QMessageBox.warning(
                self,
                "Invalid Email",
                "Please enter a valid email address."
            )
            return
        
        feedback_type = self.feedback_type.currentText()
        subject = f"[GGUF Loader Feedback] {feedback_type}"
        
        # Send via web service
        self.send_via_web_service(subject, message, user_email, feedback_type)
    
    def send_via_web_service(self, subject, message, user_email, feedback_type):
        """Send email via web service (FormSpree, etc.)"""
        # Disable buttons during send
        self.send_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Sending your feedback...")
        
        # Create and start email thread
        self.email_thread = EmailSenderThread(
            self.endpoint_url,
            subject,
            message,
            user_email,
            feedback_type
        )
        self.email_thread.success.connect(self.on_send_success)
        self.email_thread.error.connect(self.on_send_error)
        self.email_thread.start()
    
    def on_send_success(self):
        """Handle successful email send"""
        self.progress_bar.setVisible(False)
        self.status_label.setText("")
        self.send_btn.setEnabled(True)
        self.cancel_btn.setEnabled(True)
        
        QMessageBox.information(
            self,
            "Success! 🎉",
            "Thank you for your feedback! We've received your message and will respond soon."
        )
        self.accept()
    
    def on_send_error(self, error_msg):
        """Handle email send error"""
        self.progress_bar.setVisible(False)
        self.status_label.setText("")
        self.send_btn.setEnabled(True)
        self.cancel_btn.setEnabled(True)
        
        QMessageBox.critical(
            self,
            "Send Failed",
            f"Failed to send feedback:\n{error_msg}\n\n"
            "Please check your internet connection and try again."
        )
