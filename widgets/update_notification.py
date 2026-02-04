"""
Update Notification Widget
Displays a banner when a new version is available
"""
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QLabel, QPushButton, 
                               QFrame, QProgressBar, QVBoxLayout, QMessageBox)
from PySide6.QtCore import Qt, Signal, QTimer, QThread
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtCore import QUrl
import logging

logger = logging.getLogger(__name__)


class UpdateThread(QThread):
    """Thread for downloading and applying updates"""
    progress = Signal(str, int)  # message, percentage
    finished = Signal(bool)  # success
    
    def __init__(self, updater, version):
        super().__init__()
        self.updater = updater
        self.version = version
    
    def run(self):
        """Run the update process"""
        try:
            success = self.updater.download_update(
                self.version,
                progress_callback=self._on_progress
            )
            self.finished.emit(success)
        except Exception as e:
            logger.error(f"Update thread error: {e}")
            self.finished.emit(False)
    
    def _on_progress(self, message: str, percentage: int):
        """Handle progress updates"""
        self.progress.emit(message, percentage)

class UpdateNotificationBanner(QFrame):
    """Banner widget that shows update notifications"""
    
    closed = Signal()
    update_started = Signal()
    
    def __init__(self, update_info: dict, parent=None):
        super().__init__(parent)
        self.update_info = update_info
        self.update_thread = None
        self.is_updating = False
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the notification banner UI"""
        self.setObjectName("updateBanner")
        self.setFrameShape(QFrame.StyledPanel)
        
        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(15, 10, 15, 10)
        self.main_layout.setSpacing(10)
        
        # Top row with message and buttons
        top_layout = QHBoxLayout()
        top_layout.setSpacing(15)
        
        # Icon/emoji
        icon_label = QLabel("🎉")
        icon_label.setStyleSheet("font-size: 24px;")
        top_layout.addWidget(icon_label)
        
        # Message
        current_ver = self.update_info.get('current_version', 'Unknown')
        latest_ver = self.update_info.get('latest_version', 'Unknown')
        
        self.message_label = QLabel(
            f"<b>New version available!</b> "
            f"v{current_ver} → v{latest_ver}"
        )
        self.message_label.setWordWrap(True)
        font = self.message_label.font()
        font.setPointSize(10)
        self.message_label.setFont(font)
        top_layout.addWidget(self.message_label, 1)
        
        # Auto-update button (primary action)
        self.auto_update_btn = QPushButton("🚀 Update Now")
        self.auto_update_btn.setCursor(Qt.PointingHandCursor)
        self.auto_update_btn.clicked.connect(self._start_auto_update)
        self.auto_update_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #059669;
            }
            QPushButton:pressed {
                background-color: #047857;
            }
            QPushButton:disabled {
                background-color: #9ca3af;
            }
        """)
        top_layout.addWidget(self.auto_update_btn)
        
        # Manual download button
        download_btn = QPushButton("Download Manually")
        download_btn.setCursor(Qt.PointingHandCursor)
        download_btn.clicked.connect(self._open_download)
        download_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton:pressed {
                background-color: #1e40af;
            }
        """)
        top_layout.addWidget(download_btn)
        
        # View release notes button
        notes_btn = QPushButton("Release Notes")
        notes_btn.setCursor(Qt.PointingHandCursor)
        notes_btn.clicked.connect(self._show_release_notes)
        notes_btn.setStyleSheet("""
            QPushButton {
                background-color: #64748b;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #475569;
            }
            QPushButton:pressed {
                background-color: #334155;
            }
        """)
        top_layout.addWidget(notes_btn)
        
        # Close button
        close_btn = QPushButton("✕")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFixedSize(30, 30)
        close_btn.clicked.connect(self._close_banner)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #64748b;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #1e293b;
                background-color: #f1f5f9;
                border-radius: 4px;
            }
        """)
        top_layout.addWidget(close_btn)
        
        self.main_layout.addLayout(top_layout)
        
        # Progress bar (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #e2e8f0;
                border-radius: 4px;
                text-align: center;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #10b981;
                border-radius: 2px;
            }
        """)
        self.progress_bar.hide()
        self.main_layout.addWidget(self.progress_bar)
        
        # Style the banner
        self.setStyleSheet("""
            #updateBanner {
                background-color: #dbeafe;
                border: 2px solid #3b82f6;
                border-radius: 8px;
            }
        """)
        
    def _start_auto_update(self):
        """Start the automatic update process"""
        if self.is_updating:
            return
        
        # Confirm with user
        reply = QMessageBox.question(
            self,
            "Confirm Update",
            f"Update to version {self.update_info.get('latest_version')}?\n\n"
            "The application will:\n"
            "1. Download only changed files\n"
            "2. Create a backup\n"
            "3. Apply the update\n"
            "4. Restart automatically\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        self.is_updating = True
        self.auto_update_btn.setEnabled(False)
        self.auto_update_btn.setText("Updating...")
        self.progress_bar.show()
        self.progress_bar.setValue(0)
        self.update_started.emit()
        
        # Import and create updater
        try:
            from updater.auto_updater import AutoUpdater
            
            current_version = self.update_info.get('current_version')
            latest_version = self.update_info.get('latest_version')
            
            updater = AutoUpdater(current_version)
            
            # Create and start update thread
            self.update_thread = UpdateThread(updater, latest_version)
            self.update_thread.progress.connect(self._on_update_progress)
            self.update_thread.finished.connect(self._on_update_finished)
            self.update_thread.start()
            
        except Exception as e:
            logger.error(f"Failed to start update: {e}")
            QMessageBox.critical(
                self,
                "Update Error",
                f"Failed to start update:\n{str(e)}"
            )
            self.is_updating = False
            self.auto_update_btn.setEnabled(True)
            self.auto_update_btn.setText("🚀 Update Now")
            self.progress_bar.hide()
    
    def _on_update_progress(self, message: str, percentage: int):
        """Handle update progress"""
        self.progress_bar.setValue(percentage)
        self.progress_bar.setFormat(f"{message} - {percentage}%")
        self.message_label.setText(f"<b>{message}</b>")
    
    def _on_update_finished(self, success: bool):
        """Handle update completion"""
        self.is_updating = False
        
        if success:
            # Show success message
            reply = QMessageBox.information(
                self,
                "Update Complete",
                "Update installed successfully!\n\n"
                "The application will now restart.",
                QMessageBox.Ok
            )
            
            # Restart application
            try:
                from updater.auto_updater import AutoUpdater
                updater = AutoUpdater(self.update_info.get('current_version'))
                updater.restart_application()
            except Exception as e:
                logger.error(f"Failed to restart: {e}")
                QMessageBox.warning(
                    self,
                    "Restart Required",
                    "Please restart the application manually to complete the update."
                )
        else:
            # Show error message
            QMessageBox.critical(
                self,
                "Update Failed",
                "Failed to install update.\n\n"
                "Your files have been restored from backup.\n"
                "You can try again or download manually."
            )
            self.auto_update_btn.setEnabled(True)
            self.auto_update_btn.setText("🚀 Update Now")
            self.progress_bar.hide()
    
    def _open_download(self):
        """Open the download URL in browser"""
        download_url = self.update_info.get('download_url')
        if download_url:
            QDesktopServices.openUrl(QUrl(download_url))
            logger.info(f"Opened download URL: {download_url}")
        
    def _show_release_notes(self):
        """Open release notes in browser"""
        release_url = self.update_info.get('release_url')
        if release_url:
            QDesktopServices.openUrl(QUrl(release_url))
            logger.info(f"Opened release notes: {release_url}")
    
    def _close_banner(self):
        """Close the banner"""
        if self.is_updating:
            reply = QMessageBox.question(
                self,
                "Update in Progress",
                "An update is currently in progress.\n\n"
                "Are you sure you want to cancel?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
            
            if self.update_thread and self.update_thread.isRunning():
                self.update_thread.terminate()
                self.update_thread.wait()
        
        self.closed.emit()
        self.deleteLater()


class UpdateNotificationManager(QWidget):
    """Manages update notifications in the application"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.banner = None
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the manager UI"""
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.hide()  # Hidden by default
        
    def show_update_notification(self, update_info: dict):
        """
        Show update notification banner
        
        Args:
            update_info: Dictionary with update information
        """
        if not update_info or not update_info.get('available'):
            return
            
        # Remove existing banner if any
        if self.banner:
            self.banner.deleteLater()
            
        # Create new banner
        self.banner = UpdateNotificationBanner(update_info, self)
        self.banner.closed.connect(self._on_banner_closed)
        self.layout.addWidget(self.banner)
        
        # Show the widget
        self.show()
        logger.info("Update notification displayed")
        
    def _on_banner_closed(self):
        """Handle banner close event"""
        self.hide()
        logger.info("Update notification closed")
