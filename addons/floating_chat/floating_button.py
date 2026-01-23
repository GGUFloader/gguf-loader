#!/usr/bin/env python3
"""
Floating Chat Button - Draggable floating button like Facebook Messenger

Cross-platform draggable button that stays on top of all windows.
"""

import os
from pathlib import Path

from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import (
    Qt, QPoint, QRect, QPropertyAnimation, QEasingCurve, QTimer, Signal, Property
)
from PySide6.QtGui import (
    QPainter, QColor, QBrush, QPen, QFont, QLinearGradient, 
    QRadialGradient, QPainterPath, QMouseEvent, QPixmap, QIcon
)


class FloatingChatButton(QWidget):
    """
    Facebook Messenger-style floating chat button.
    
    Features:
    - Always stays on top
    - Draggable anywhere on screen
    - Smooth animations
    - Cross-platform compatibility
    - Modern gradient design
    """
    
    # Signals
    clicked = Signal()
    
    def __init__(self):
        super().__init__()
        
        # Button properties
        self._button_size = 60
        self._is_dragging = False
        self._drag_start_position = QPoint()
        self._is_hovered = False
        
        # Animation properties
        self._hover_animation = None
        self._click_animation = None
        self._scale_factor = 1.0
        
        # Load icon
        self._icon_pixmap = self._load_icon()
        
        # Setup window properties
        self._setup_window()
        
        # Setup animations
        self._setup_animations()
        
        # Auto-hide timer (optional feature)
        self._auto_hide_timer = QTimer()
        self._auto_hide_timer.setSingleShot(True)
        self._auto_hide_timer.timeout.connect(self._auto_hide)
    
    def _load_icon(self):
        """Load the float.png file from the project root at highest resolution."""
        try:
            # Try to find float.png in the project root
            # Go up from addons/floating_chat to project root
            current_dir = Path(__file__).parent
            project_root = current_dir.parent.parent
            icon_path = project_root / "float.png"
            
            if icon_path.exists():
                # Load PNG file directly as pixmap
                pixmap = QPixmap(str(icon_path))
                if not pixmap.isNull():
                    print(f"Loaded float.png at size: {pixmap.width()}x{pixmap.height()}")
                    return pixmap
            
            # Fallback: try resource_manager for icon.ico as last resort
            try:
                import sys
                sys.path.insert(0, str(project_root))
                from resource_manager import find_icon
                icon_path = find_icon()
                if icon_path and os.path.exists(icon_path):
                    pixmap = QPixmap(icon_path)
                    if not pixmap.isNull():
                        return pixmap
            except:
                pass
            
        except Exception as e:
            print(f"Could not load icon: {e}")
        
        # Return None if icon couldn't be loaded
        return None
    
    def _setup_window(self):
        """Setup window properties for floating behavior."""
        # Set window flags for always-on-top floating window
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.X11BypassWindowManagerHint  # Linux compatibility
        )
        
        # Set transparent background
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Set fixed size
        self.setFixedSize(self._button_size, self._button_size)
        
        # Enable mouse tracking for hover effects
        self.setMouseTracking(True)
        
        # Set tooltip
        self.setToolTip("Floating Chat - Click to open chat window")
    
    def _setup_animations(self):
        """Setup smooth animations for hover and click effects."""
        # Hover animation
        self._hover_animation = QPropertyAnimation(self, b"scaleFactor")
        self._hover_animation.setDuration(200)
        self._hover_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # Click animation
        self._click_animation = QPropertyAnimation(self, b"scaleFactor")
        self._click_animation.setDuration(150)
        self._click_animation.setEasingCurve(QEasingCurve.Type.OutBounce)
    
    def paintEvent(self, event):
        """Custom paint event - only draw the float.png image with no background."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        # Calculate button rect with scale factor
        center = self.rect().center()
        scaled_size = int(self._button_size * self._scale_factor)
        button_rect = QRect(
            center.x() - scaled_size // 2,
            center.y() - scaled_size // 2,
            scaled_size,
            scaled_size
        )
        
        # Draw only the icon if available, otherwise draw chat icon with background
        if self._icon_pixmap and not self._icon_pixmap.isNull():
            self._draw_icon(painter, button_rect)
        else:
            # Fallback: draw gradient background and chat icon if float.png not found
            if self._is_hovered:
                gradient = QRadialGradient(center, scaled_size // 2)
                gradient.setColorAt(0.0, QColor(0, 150, 255, 240))
                gradient.setColorAt(0.7, QColor(0, 120, 220, 220))
                gradient.setColorAt(1.0, QColor(0, 100, 200, 200))
            else:
                gradient = QRadialGradient(center, scaled_size // 2)
                gradient.setColorAt(0.0, QColor(0, 120, 215, 220))
                gradient.setColorAt(0.7, QColor(0, 100, 190, 200))
                gradient.setColorAt(1.0, QColor(0, 80, 170, 180))
            
            painter.setBrush(QBrush(gradient))
            painter.setPen(QPen(QColor(255, 255, 255, 100), 2))
            painter.drawEllipse(button_rect)
            self._draw_chat_icon(painter, button_rect)
    
    def _draw_icon(self, painter, button_rect):
        """Draw the float.png image filling the entire button area with high quality."""
        # Use the full button size for the icon (100% coverage, no padding)
        icon_size = button_rect.width()
        
        # Calculate icon position (centered)
        icon_x = button_rect.center().x() - icon_size // 2
        icon_y = button_rect.center().y() - icon_size // 2
        icon_rect = QRect(icon_x, icon_y, icon_size, icon_size)
        
        # Scale the icon with highest quality settings
        # KeepAspectRatio ensures the icon isn't distorted
        scaled_pixmap = self._icon_pixmap.scaled(
            icon_size, icon_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        # Center the scaled pixmap if aspect ratio caused size difference
        actual_rect = scaled_pixmap.rect()
        if actual_rect.width() < icon_size or actual_rect.height() < icon_size:
            # Center the smaller dimension
            offset_x = (icon_size - actual_rect.width()) // 2
            offset_y = (icon_size - actual_rect.height()) // 2
            icon_rect = QRect(
                icon_x + offset_x,
                icon_y + offset_y,
                actual_rect.width(),
                actual_rect.height()
            )
        
        # Draw with high quality rendering
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.RenderHint.LosslessImageRendering, True)
        
        # Draw the icon with full opacity - no background
        painter.setOpacity(1.0)
        painter.drawPixmap(icon_rect, scaled_pixmap)
        
        painter.restore()
    
    def _draw_chat_icon(self, painter, button_rect):
        """Draw chat bubble icon in the center of the button."""
        painter.setPen(QPen(QColor(255, 255, 255, 230), 2))
        painter.setBrush(QBrush(QColor(255, 255, 255, 0)))  # Transparent fill
        
        # Calculate icon size and position
        icon_size = button_rect.width() // 3
        icon_x = button_rect.center().x() - icon_size // 2
        icon_y = button_rect.center().y() - icon_size // 2
        
        # Draw speech bubble
        bubble_rect = QRect(icon_x, icon_y, icon_size, int(icon_size * 0.8))
        painter.drawRoundedRect(bubble_rect, 4, 4)
        
        # Draw speech bubble tail
        tail_points = [
            QPoint(bubble_rect.left() + icon_size // 4, bubble_rect.bottom()),
            QPoint(bubble_rect.left() + icon_size // 6, bubble_rect.bottom() + icon_size // 4),
            QPoint(bubble_rect.left() + icon_size // 2, bubble_rect.bottom())
        ]
        
        path = QPainterPath()
        path.moveTo(tail_points[0])
        path.lineTo(tail_points[1])
        path.lineTo(tail_points[2])
        painter.drawPath(path)
        
        # Draw dots inside bubble
        dot_size = 2
        dot_y = bubble_rect.center().y()
        for i in range(3):
            dot_x = bubble_rect.left() + (i + 1) * bubble_rect.width() // 4
            painter.setBrush(QBrush(QColor(255, 255, 255, 200)))
            painter.drawEllipse(dot_x - dot_size // 2, dot_y - dot_size // 2, dot_size, dot_size)
    
    def _draw_shadow(self, painter, button_rect):
        """Draw subtle shadow effect."""
        shadow_offset = 2
        shadow_rect = button_rect.translated(shadow_offset, shadow_offset)
        
        # Create shadow gradient
        shadow_gradient = QRadialGradient(shadow_rect.center(), shadow_rect.width() // 2)
        shadow_gradient.setColorAt(0.0, QColor(0, 0, 0, 30))
        shadow_gradient.setColorAt(1.0, QColor(0, 0, 0, 0))
        
        painter.setBrush(QBrush(shadow_gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(shadow_rect)
    
    def mousePressEvent(self, event):
        """Handle mouse press for dragging and clicking."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            self._drag_start_position = event.globalPosition().toPoint() - self.pos()
            
            # Start click animation
            self._click_animation.setStartValue(self._scale_factor)
            self._click_animation.setEndValue(0.9)
            self._click_animation.start()
            
            event.accept()
    
    def mouseMoveEvent(self, event):
        """Handle mouse move for dragging."""
        if self._is_dragging and event.buttons() == Qt.MouseButton.LeftButton:
            # Calculate new position
            new_pos = event.globalPosition().toPoint() - self._drag_start_position
            
            # Ensure button stays on screen
            screen = QApplication.primaryScreen()
            screen_rect = screen.geometry()
            
            x = max(0, min(new_pos.x(), screen_rect.width() - self.width()))
            y = max(0, min(new_pos.y(), screen_rect.height() - self.height()))
            
            self.move(x, y)
            event.accept()
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release for click detection."""
        if event.button() == Qt.MouseButton.LeftButton:
            was_dragging = self._is_dragging
            self._is_dragging = False
            
            # Restore scale
            self._click_animation.setStartValue(self._scale_factor)
            self._click_animation.setEndValue(1.0)
            self._click_animation.start()
            
            # If we weren't dragging much, treat as click
            if not was_dragging or (event.globalPosition().toPoint() - self._drag_start_position - self.pos()).manhattanLength() < 5:
                self.clicked.emit()
            
            event.accept()
    
    def enterEvent(self, event):
        """Handle mouse enter for hover effects."""
        self._is_hovered = True
        
        # Start hover animation
        self._hover_animation.setStartValue(self._scale_factor)
        self._hover_animation.setEndValue(1.1)
        self._hover_animation.start()
        
        # Cancel auto-hide timer
        self._auto_hide_timer.stop()
        
        self.update()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Handle mouse leave for hover effects."""
        self._is_hovered = False
        
        # Start hover animation (reverse)
        self._hover_animation.setStartValue(self._scale_factor)
        self._hover_animation.setEndValue(1.0)
        self._hover_animation.start()
        
        # Start auto-hide timer (optional)
        # self._auto_hide_timer.start(10000)  # Hide after 10 seconds of no interaction
        
        self.update()
        super().leaveEvent(event)
    
    def _auto_hide(self):
        """Auto-hide the button (optional feature)."""
        # This could fade out the button or move it to screen edge
        # For now, we'll just make it semi-transparent
        self.setWindowOpacity(0.3)
    
    def show(self):
        """Override show to ensure full opacity."""
        self.setWindowOpacity(1.0)
        super().show()
    
    # Property for scale factor animation (Qt Property)
    def getScaleFactor(self):
        return self._scale_factor
    
    def setScaleFactor(self, value):
        self._scale_factor = value
        self.update()
    
    scaleFactor = Property(float, getScaleFactor, setScaleFactor)