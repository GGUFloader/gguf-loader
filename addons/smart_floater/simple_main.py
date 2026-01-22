"""
Dead simple floating assistant - no bullshit, just works.
Now with threaded AI processing and visual progress indicator.
"""

import sys
import time
from PySide6.QtWidgets import (QApplication, QPushButton, QDialog, QVBoxLayout, QTextEdit, 
                               QHBoxLayout, QLabel, QWidget, QProgressBar, QFrame)
from PySide6.QtCore import QTimer, Qt, QThread, Signal, QObject
from PySide6.QtGui import QCursor, QPainter, QColor, QPen
import pyautogui
import pyperclip


class AIProcessingWorker(QThread):
    """Worker thread for AI processing to prevent UI freezing."""
    
    # Signals
    progress_update = Signal(str, int)  # message, percentage
    processing_complete = Signal(str)   # result text
    processing_error = Signal(str)      # error message
    
    def __init__(self, model, prompt, action, max_tokens, temperature, top_p):
        super().__init__()
        self.model = model
        self.prompt = prompt
        self.action = action
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.is_cancelled = False
    
    def cancel(self):
        """Cancel the processing."""
        self.is_cancelled = True
    
    def run(self):
        """Run the AI processing in a separate thread."""
        try:
            if self.is_cancelled:
                return
            
            # Emit progress updates
            self.progress_update.emit("🤖 Initializing AI processing...", 10)
            time.sleep(0.1)  # Small delay for visual feedback
            
            if self.is_cancelled:
                return
            
            self.progress_update.emit("🧠 Analyzing text...", 30)
            time.sleep(0.1)
            
            if self.is_cancelled:
                return
            
            self.progress_update.emit("⚡ Generating response...", 50)
            
            # Process with GGUF model
            response = self.model(
                self.prompt,
                max_tokens=self.max_tokens,
                stream=False,
                temperature=self.temperature,
                top_p=self.top_p,
                repeat_penalty=1.1,
                top_k=40,
                stop=["</s>", "Human:", "User:", "\n\n\n", "Original message:", "Text to comment on:"]
            )
            
            if self.is_cancelled:
                return
            
            self.progress_update.emit("✨ Finalizing response...", 80)
            time.sleep(0.1)
            
            # Extract text from response
            if isinstance(response, dict) and 'choices' in response:
                result_text = response['choices'][0].get('text', '').strip()
            elif isinstance(response, str):
                result_text = response.strip()
            else:
                result_text = str(response).strip()
            
            if self.is_cancelled:
                return
            
            self.progress_update.emit("🔧 Cleaning up response...", 90)
            
            # Clean up the result
            if result_text:
                # Remove any prompt echoing
                cleanup_phrases = [
                    "Summary:", "Comment:", "Write a suitable reply:", 
                    "Write your response:", "Reply:", "Response:",
                    "Clear explanation:", "Explanation:"
                ]
                
                for phrase in cleanup_phrases:
                    if phrase in result_text:
                        result_text = result_text.split(phrase)[-1].strip()
                
                # Remove common AI response prefixes
                prefixes_to_remove = [
                    "Here's a ", "Here is a ", "I'd be happy to ",
                    "I would ", "Let me ", "Sure, here's "
                ]
                
                for prefix in prefixes_to_remove:
                    if result_text.lower().startswith(prefix.lower()):
                        result_text = result_text[len(prefix):].strip()
                
                if not self.is_cancelled:
                    self.progress_update.emit("✅ Complete!", 100)
                    time.sleep(0.2)
                    self.processing_complete.emit(result_text)
            else:
                if not self.is_cancelled:
                    self.processing_error.emit("❌ No response generated. Try again.")
                
        except Exception as e:
            if not self.is_cancelled:
                self.processing_error.emit(f"❌ Error processing with AI model:\n{str(e)}\n\nMake sure a compatible GGUF model is loaded.")


class ProgressIndicator(QWidget):
    """Custom circular progress indicator widget."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(60, 60)
        self.progress = 0
        self.message = "Processing..."
        
        # Animation timer
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.update)
        self.animation_angle = 0
    
    def set_progress(self, progress, message=""):
        """Set progress percentage and message."""
        self.progress = progress
        if message:
            self.message = message
        self.update()
    
    def start_animation(self):
        """Start the spinning animation."""
        self.animation_timer.start(50)  # Update every 50ms
    
    def stop_animation(self):
        """Stop the spinning animation."""
        self.animation_timer.stop()
    
    def paintEvent(self, event):
        """Paint the progress indicator."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Clear background
        painter.fillRect(self.rect(), QColor(240, 240, 240))
        
        # Draw outer circle
        painter.setPen(QPen(QColor(200, 200, 200), 3))
        painter.drawEllipse(5, 5, 50, 50)
        
        # Draw progress arc
        if self.progress > 0:
            painter.setPen(QPen(QColor(0, 120, 212), 4))
            start_angle = -90 * 16  # Start from top
            span_angle = int((self.progress / 100) * 360 * 16)
            painter.drawArc(5, 5, 50, 50, start_angle, span_angle)
        
        # Draw spinning indicator if progress is 0 or animating
        if self.progress == 0 or self.animation_timer.isActive():
            painter.setPen(QPen(QColor(0, 120, 212), 3))
            self.animation_angle = (self.animation_angle + 10) % 360
            start_angle = self.animation_angle * 16
            span_angle = 60 * 16  # 60 degree arc
            painter.drawArc(8, 8, 44, 44, start_angle, span_angle)
        
        # Draw percentage text
        if self.progress > 0:
            painter.setPen(QColor(60, 60, 60))
            painter.drawText(self.rect(), Qt.AlignCenter, f"{self.progress}%")


class SimpleFloatingAssistant:
    def __init__(self, gguf_app):
        self.gguf_app = gguf_app
        self.button = None
        self.popup = None
        self.selected_text = ""
        self.model = None  # Store model reference directly
        
        # Threading for AI processing
        self.processing_worker = None
        self.is_processing = False
        
        # Initialize clipboard tracking
        try:
            self.last_clipboard = pyperclip.paste()
        except:
            self.last_clipboard = ""
        
        # Button persistence tracking
        self.button_show_time = 0
        self.button_should_stay = False
        
        # Connect to model loading signals
        self.connect_to_model_signals()
        
        # Timer to check for text selection
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_selection)
        self.timer.start(300)  # Check every 300ms - balance between responsiveness and performance
    
    def connect_to_model_signals(self):
        """Connect to model loading signals from the main app."""
        try:
            # Connect to the main app's model_loaded signal
            if hasattr(self.gguf_app, 'model_loaded'):
                self.gguf_app.model_loaded.connect(self.on_model_loaded)
                print("✅ Connected to main app model_loaded signal")
            
            # Connect to the main app's model_unloaded signal
            if hasattr(self.gguf_app, 'model_unloaded'):
                self.gguf_app.model_unloaded.connect(self.on_model_unloaded)
                print("✅ Connected to main app model_unloaded signal")
            
            # Also try to connect to ai_chat model_loaded signal for redundancy
            if hasattr(self.gguf_app, 'ai_chat') and hasattr(self.gguf_app.ai_chat, 'model_loaded'):
                self.gguf_app.ai_chat.model_loaded.connect(self.on_model_loaded)
                print("✅ Connected to ai_chat model_loaded signal")
            
            # Check if model is already loaded
            if hasattr(self.gguf_app, 'model') and self.gguf_app.model:
                print("✅ Model already loaded, storing reference")
                self.model = self.gguf_app.model
                
        except Exception as e:
            print(f"❌ Error connecting to model signals: {e}")
    
    def on_model_loaded(self, model):
        """Handle model loaded event."""
        self.model = model
        print(f"✅ Addon received model: {type(model)}")
        print(f"   Model methods: {[m for m in dir(model) if not m.startswith('_')][:10]}")  # First 10 methods
    
    def on_model_unloaded(self):
        """Handle model unloaded event."""
        self.model = None
        print("✅ Addon notified about model unloading")
    
    def check_selection(self):
        """Check if text is currently selected (without copying)."""
        try:
            # TEMPORARILY DISABLED - This was interfering with Ctrl key shortcuts
            # The pyautogui.hotkey('ctrl', 'c') was sending global Ctrl+C every 500ms
            # which was blocking normal Ctrl+V, Ctrl+C usage in text inputs
            return
            
            # Save current clipboard content
            original_clipboard = pyperclip.paste()
            
            # Temporarily copy selection to check if text is selected
            pyautogui.hotkey('ctrl', 'c')
            
            # Small delay to let clipboard update
            QTimer.singleShot(50, lambda: self._process_selection_check(original_clipboard))
            
        except:
            pass
    
    def _process_selection_check(self, original_clipboard):
        """Process the selection check and restore clipboard."""
        try:
            # Get what was copied
            current_selection = pyperclip.paste()
            
            # Check if we got new selected text
            if (current_selection != original_clipboard and 
                current_selection and 
                len(current_selection.strip()) > 3 and
                len(current_selection) < 5000):
                
                # We have selected text!
                if current_selection.strip() != self.selected_text:
                    self.selected_text = current_selection.strip()
                    self.show_button()
                    self.button_show_time = 0  # Reset timer
                    self.button_should_stay = True
            else:
                # No text selected - but don't hide immediately
                # Only hide after button has been shown for a while
                if self.button_should_stay:
                    self.button_show_time += 1
                    
                    # Hide after 10 checks (about 3 seconds)
                    if self.button_show_time > 10:
                        self.hide_button()
                        self.button_should_stay = False
                        self.button_show_time = 0
            
            # Always restore original clipboard immediately
            pyperclip.copy(original_clipboard)
            
        except:
            # Always try to restore clipboard even if there's an error
            try:
                pyperclip.copy(original_clipboard)
            except:
                pass
    
    def _capture_selected_text_for_popup(self):
        """Capture the currently selected text when user clicks the button."""
        try:
            # TEMPORARILY DISABLED - This was interfering with Ctrl key shortcuts
            # The pyautogui.hotkey('ctrl', 'c') was sending global Ctrl+C
            # which was blocking normal Ctrl+V, Ctrl+C usage in text inputs
            self.selected_text = "Text selection temporarily disabled to fix Ctrl+V issue"
            return
            
            # Save current clipboard
            original_clipboard = pyperclip.paste()
            
            # Copy the selected text
            pyautogui.hotkey('ctrl', 'c')
            
            # Small delay
            import time
            time.sleep(0.1)
            
            # Get the selected text
            selected = pyperclip.paste()
            
            # Update our selected text if we got something new
            if selected and selected != original_clipboard:
                self.selected_text = selected.strip()
            
            # Restore original clipboard
            pyperclip.copy(original_clipboard)
            
        except:
            pass
    
    def show_button(self):
        """Show floating button near cursor."""
        if self.button:
            self.button.close()
        
        self.button = QPushButton("✨")
        self.button.setFixedSize(40, 40)
        self.button.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.button.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                border: none;
                border-radius: 20px;
                color: white;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
        """)
        
        # Position near cursor
        pos = QCursor.pos()
        self.button.move(pos.x() + 10, pos.y() - 50)
        self.button.clicked.connect(self.show_popup)
        self.button.show()
        
        # Reset persistence tracking
        self.button_show_time = 0
        self.button_should_stay = True
    
    def hide_button(self):
        """Hide button."""
        if self.button:
            self.button.close()
            self.button = None
        
        # Reset persistence tracking
        self.button_should_stay = False
        self.button_show_time = 0
    
    def show_popup(self):
        """Show popup with text processing options."""
        if self.popup:
            self.popup.close()
        
        # Capture the selected text fresh when button is clicked
        self._capture_selected_text_for_popup()
        
        self.popup = QDialog()
        self.popup.setWindowTitle("AI Assistant")
        self.popup.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.popup.resize(500, 450)
        
        layout = QVBoxLayout(self.popup)
        
        # Show selected text
        layout.addWidget(QLabel("Selected Text:"))
        text_area = QTextEdit()
        text_area.setPlainText(self.selected_text)
        text_area.setMaximumHeight(80)
        text_area.setReadOnly(True)
        text_area.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        text_area.setContextMenuPolicy(Qt.DefaultContextMenu)
        layout.addWidget(text_area)
        
        # First row of buttons
        btn_layout = QHBoxLayout()
        
        self.summarize_btn = QPushButton("Summarize")
        self.summarize_btn.clicked.connect(lambda: self.process_text("summarize"))
        btn_layout.addWidget(self.summarize_btn)
        
        self.clarify_btn = QPushButton("Clarify")
        self.clarify_btn.clicked.connect(lambda: self.process_text("clarify"))
        btn_layout.addWidget(self.clarify_btn)
        
        self.reply_btn = QPushButton("Write Reply")
        self.reply_btn.clicked.connect(lambda: self.process_text("reply"))
        btn_layout.addWidget(self.reply_btn)
        
        # Second row of buttons
        btn_layout2 = QHBoxLayout()
        
        self.comment_btn = QPushButton("Comment")
        self.comment_btn.clicked.connect(lambda: self.process_text("comment"))
        btn_layout2.addWidget(self.comment_btn)
        
        # Cancel button (initially hidden)
        self.cancel_btn = QPushButton("❌ Cancel")
        self.cancel_btn.clicked.connect(self.cancel_processing)
        self.cancel_btn.setVisible(False)
        btn_layout2.addWidget(self.cancel_btn)
        
        # Debug button
        debug_btn = QPushButton("🔍 Debug Model")
        debug_btn.clicked.connect(self.debug_model)
        btn_layout2.addWidget(debug_btn)
        
        layout.addLayout(btn_layout)
        layout.addLayout(btn_layout2)
        
        # Progress area (initially hidden)
        self.progress_frame = QFrame()
        self.progress_frame.setFrameStyle(QFrame.StyledPanel)
        self.progress_frame.setVisible(False)
        progress_layout = QHBoxLayout(self.progress_frame)
        
        # Progress indicator
        self.progress_indicator = ProgressIndicator()
        progress_layout.addWidget(self.progress_indicator)
        
        # Progress info
        progress_info_layout = QVBoxLayout()
        self.progress_label = QLabel("Processing...")
        self.progress_label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        self.progress_label.setStyleSheet("font-weight: bold; color: #0078d4;")
        progress_info_layout.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_info_layout.addWidget(self.progress_bar)
        
        progress_layout.addLayout(progress_info_layout)
        layout.addWidget(self.progress_frame)
        
        # Result area
        layout.addWidget(QLabel("Result:"))
        self.result_area = QTextEdit()
        self.result_area.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        self.result_area.setContextMenuPolicy(Qt.DefaultContextMenu)
        layout.addWidget(self.result_area)
        
        # Copy result button
        self.copy_btn = QPushButton("Copy Result")
        self.copy_btn.clicked.connect(self.copy_result)
        self.copy_btn.setEnabled(False)
        layout.addWidget(self.copy_btn)
        
        self.popup.show()
        self.hide_button()
    
    def process_text(self, action):
        """Process text with AI using threaded processing to prevent UI freezing."""
        try:
            # Check if already processing
            if self.is_processing:
                return
            
            model = self.get_model()
            if not model:
                self.result_area.setText("❌ Error: No AI model loaded in GGUF Loader\n\nPlease load a GGUF model first!")
                return
            
            # Set processing state
            self.is_processing = True
            self._set_buttons_enabled(False)
            self._show_progress(True)
            
            # Clear result area
            self.result_area.clear()
            
            # Create appropriate prompt based on action
            if action == "summarize":
                prompt = f"""You are a summarization expert. Create a clear and concise summary of the following text. Your summary should:

- Capture only the main points and key information
- Be significantly shorter than the original text
- Use clear, simple language
- Focus on facts and core concepts
- Avoid adding your own opinions or interpretations
- Be complete but concise

Text to summarize:
{self.selected_text}

Summary:"""
            elif action == "clarify":
                prompt = f"""You are an expert teacher and concept clarifier. Help explain and clarify the following text, especially if it's from a book or educational material. Your explanation should:

- Break down complex concepts into simple, understandable terms
- Explain any difficult vocabulary or technical terms
- Provide context and background information when helpful
- Use analogies or examples to make concepts clearer
- Organize the explanation in a logical, easy-to-follow manner
- Help the reader truly understand the material

Text to clarify:
{self.selected_text}

Clear explanation:"""
            elif action == "reply":
                prompt = f"""You are a professional communication assistant. Write a thoughtful, appropriate reply to the following message/email/comment. The reply should be:

- Professional and courteous in tone
- Directly address the main points raised
- Be helpful and constructive
- Match the formality level of the original message
- Be concise but complete
- Ready to use as-is (no need for further editing)

Original message/text:
{self.selected_text}

Write a suitable reply:"""
            else:  # comment
                prompt = f"""You are a helpful assistant that writes thoughtful responses. Write a constructive comment or response about the following text that:

- Shows understanding of the content
- Adds value to the discussion
- Is respectful and professional
- Can be used as a reply in emails, social media, or forums
- Is engaging and helpful

Text to comment on:
{self.selected_text}

Write your response:"""
            
            # Adjust parameters based on action type
            if action == "reply":
                max_tokens = 400
                temperature = 0.6
                top_p = 0.85
            elif action == "comment":
                max_tokens = 350
                temperature = 0.75
                top_p = 0.9
            elif action == "clarify":
                max_tokens = 500
                temperature = 0.7
                top_p = 0.9
            else:  # summarize
                max_tokens = 200
                temperature = 0.4
                top_p = 0.75
            
            # Create and start worker thread
            self.processing_worker = AIProcessingWorker(
                model, prompt, action, max_tokens, temperature, top_p
            )
            
            # Connect signals
            self.processing_worker.progress_update.connect(self._on_progress_update)
            self.processing_worker.processing_complete.connect(self._on_processing_complete)
            self.processing_worker.processing_error.connect(self._on_processing_error)
            self.processing_worker.finished.connect(self._on_worker_finished)
            
            # Start processing
            self.processing_worker.start()
            self.progress_indicator.start_animation()
            
        except Exception as e:
            self._on_processing_error(f"❌ Unexpected error: {str(e)}")
    
    def cancel_processing(self):
        """Cancel the current AI processing."""
        if self.processing_worker and self.processing_worker.isRunning():
            self.processing_worker.cancel()
            self.processing_worker.quit()
            self.processing_worker.wait(1000)  # Wait up to 1 second
        
        self._reset_processing_state()
        self.result_area.setText("❌ Processing cancelled by user.")
    
    def _set_buttons_enabled(self, enabled):
        """Enable or disable processing buttons."""
        if hasattr(self, 'summarize_btn'):
            self.summarize_btn.setEnabled(enabled)
            self.clarify_btn.setEnabled(enabled)
            self.reply_btn.setEnabled(enabled)
            self.comment_btn.setEnabled(enabled)
            self.cancel_btn.setVisible(not enabled)
    
    def _show_progress(self, show):
        """Show or hide progress indicator."""
        if hasattr(self, 'progress_frame'):
            self.progress_frame.setVisible(show)
            if show:
                self.progress_bar.setValue(0)
                self.progress_label.setText("Starting AI processing...")
                self.progress_indicator.set_progress(0, "Initializing...")
    
    def _on_progress_update(self, message, percentage):
        """Handle progress updates from worker thread."""
        if hasattr(self, 'progress_bar'):
            self.progress_bar.setValue(percentage)
            self.progress_label.setText(message)
            self.progress_indicator.set_progress(percentage, message)
    
    def _on_processing_complete(self, result_text):
        """Handle successful processing completion."""
        self.result_area.setText(result_text)
        self.copy_btn.setEnabled(True)
        self._reset_processing_state()
    
    def _on_processing_error(self, error_message):
        """Handle processing errors."""
        self.result_area.setText(error_message)
        self._reset_processing_state()
    
    def _on_worker_finished(self):
        """Handle worker thread completion."""
        self.processing_worker = None
    
    def _reset_processing_state(self):
        """Reset the processing state and UI."""
        self.is_processing = False
        self._set_buttons_enabled(True)
        self._show_progress(False)
        self.progress_indicator.stop_animation()
    
    def get_model(self):
        """Get the loaded model using the proper backend access."""
        try:
            # First try our stored model reference
            if self.model:
                print("✅ Using stored model reference")
                return self.model
            
            print(f"🔍 Debugging model access:")
            print(f"   gguf_app type: {type(self.gguf_app)}")
            
            # Use the proper get_model_backend() method first
            if hasattr(self.gguf_app, 'get_model_backend'):
                backend = self.gguf_app.get_model_backend()
                print(f"   get_model_backend(): {backend}")
                if backend:
                    print("✅ Found model via get_model_backend()")
                    self.model = backend  # Store it for future use
                    return backend
            
            # Fallback to direct model access
            if hasattr(self.gguf_app, 'model'):
                print(f"   gguf_app.model: {self.gguf_app.model}")
                if self.gguf_app.model:
                    print("✅ Found model via gguf_app.model")
                    self.model = self.gguf_app.model  # Store it
                    return self.gguf_app.model
            
            # Last resort: try ai_chat directly
            if hasattr(self.gguf_app, 'ai_chat'):
                print(f"   ai_chat: {self.gguf_app.ai_chat}")
                if hasattr(self.gguf_app.ai_chat, 'model'):
                    print(f"   ai_chat.model: {self.gguf_app.ai_chat.model}")
                    if self.gguf_app.ai_chat.model:
                        print("✅ Found model via ai_chat.model")
                        self.model = self.gguf_app.ai_chat.model  # Store it
                        return self.gguf_app.ai_chat.model
            
            print("❌ No model found anywhere")
            return None
        except Exception as e:
            print(f"❌ Error getting model: {e}")
            return None
    
    def debug_model(self):
        """Debug model access for troubleshooting."""
        model = self.get_model()
        if model:
            self.result_area.setText(f"✅ Model found!\nType: {type(model)}\nMethods: {[m for m in dir(model) if not m.startswith('_')]}")
        else:
            self.result_area.setText("❌ No model found. Check console for debug info.")
    
    def copy_result(self):
        """Copy result to clipboard."""
        result = self.result_area.toPlainText()
        pyperclip.copy(result)
        self.copy_btn.setText("Copied!")
        QTimer.singleShot(2000, lambda: self.copy_btn.setText("Copy Result"))
    
    def stop(self):
        """Stop the assistant."""
        # Stop any running processing
        if self.processing_worker and self.processing_worker.isRunning():
            self.processing_worker.cancel()
            self.processing_worker.quit()
            self.processing_worker.wait(2000)  # Wait up to 2 seconds
        
        self.timer.stop()
        if self.button:
            self.button.close()
        if self.popup:
            self.popup.close()
        
        # Disconnect signals
        try:
            if hasattr(self.gguf_app, 'model_loaded'):
                self.gguf_app.model_loaded.disconnect(self.on_model_loaded)
                print("✅ Disconnected from main app model_loaded signal")
            if hasattr(self.gguf_app, 'model_unloaded'):
                self.gguf_app.model_unloaded.disconnect(self.on_model_unloaded)
                print("✅ Disconnected from main app model_unloaded signal")
            if hasattr(self.gguf_app, 'ai_chat') and hasattr(self.gguf_app.ai_chat, 'model_loaded'):
                self.gguf_app.ai_chat.model_loaded.disconnect(self.on_model_loaded)
                print("✅ Disconnected from ai_chat model_loaded signal")
        except Exception as e:
            print(f"⚠️ Error disconnecting signals: {e}")


# Simple status widget for the addon
class SmartFloaterStatusWidget:
    def __init__(self, addon_instance):
        from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QTextEdit
        
        self.addon = addon_instance
        self.widget = QWidget()
        self.widget.setWindowTitle("Smart Floating Assistant")
        
        layout = QVBoxLayout(self.widget)
        
        # Status info
        layout.addWidget(QLabel("🤖 Smart Floating Assistant"))
        layout.addWidget(QLabel("Status: Running in background"))
        layout.addWidget(QLabel(""))
        layout.addWidget(QLabel("How to use:"))
        layout.addWidget(QLabel("1. Select text anywhere on your screen"))
        layout.addWidget(QLabel("2. Click the ✨ button that appears"))
        layout.addWidget(QLabel("3. Choose an action:"))
        layout.addWidget(QLabel("   • Summarize - Get a concise summary"))
        layout.addWidget(QLabel("   • Clarify - Explain complex concepts"))
        layout.addWidget(QLabel("   • Write Reply - Generate a professional reply"))
        layout.addWidget(QLabel("   • Comment - Write a thoughtful response"))
        layout.addWidget(QLabel(""))
        
        # Test button
        test_btn = QPushButton("🧪 Test Model Connection")
        test_btn.clicked.connect(self.test_model)
        layout.addWidget(test_btn)
        
        # Result area
        self.result_area = QTextEdit()
        self.result_area.setMaximumHeight(100)
        self.result_area.setReadOnly(True)
        self.result_area.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        self.result_area.setContextMenuPolicy(Qt.DefaultContextMenu)
        layout.addWidget(self.result_area)
        
        # Stop/Start buttons
        button_layout = QHBoxLayout()
        
        stop_btn = QPushButton("⏹️ Stop")
        stop_btn.clicked.connect(self.stop_addon)
        button_layout.addWidget(stop_btn)
        
        start_btn = QPushButton("▶️ Start")
        start_btn.clicked.connect(self.start_addon)
        button_layout.addWidget(start_btn)
        
        layout.addLayout(button_layout)
    
    def test_model(self):
        """Test if the model is accessible."""
        model = self.addon.get_model()
        if model:
            self.result_area.setText(f"✅ Model connected!\nType: {type(model).__name__}")
        else:
            self.result_area.setText("❌ No model found. Load a GGUF model first.")
    
    def stop_addon(self):
        """Stop the addon monitoring."""
        self.addon.timer.stop()
        self.result_area.setText("⏹️ Monitoring stopped")
    
    def start_addon(self):
        """Start the addon monitoring."""
        self.addon.timer.start()
        self.result_area.setText("▶️ Monitoring started")


# Simple registration function
def register(parent=None):
    """Register the simple floating assistant."""
    try:
        print(f"🔧 Register called with parent: {type(parent)}")
        
        # Stop existing addon if running
        if hasattr(parent, '_simple_floater') and parent._simple_floater:
            parent._simple_floater.stop()
        
        # Create and start simple addon
        addon = SimpleFloatingAssistant(parent)
        parent._simple_floater = addon
        
        print("✅ Simple Floating Assistant started!")
        
        # Return a status widget for the addon panel
        status_widget = SmartFloaterStatusWidget(addon)
        return status_widget.widget
        
    except Exception as e:
        print(f"❌ Failed to start simple addon: {e}")
        return None
        return None