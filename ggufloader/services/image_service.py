"""
ImageService - Clipboard image detection and inline display.

Inspired by Aider's clipboard_watcher which detects image paste events
and DeepSeek's MessageImages component for inline image display.

Source: aider/aider/clipboard_watcher.py, deepseek MessageImages
"""

from __future__ import annotations

import base64
import io
import logging
import tempfile
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QMimeData
from PySide6.QtGui import QClipboard, QImage, QPixmap

logger = logging.getLogger(__name__)


class ImageService:
    """Handles image paste from clipboard and image file attachment.

    Usage:
        image = ImageService()
        # Check clipboard for images
        img_data = image.get_clipboard_image()
        # Save image to temp file
        if img_data:
            path = image.save_temp_image(img_data)
    """

    MAX_IMAGE_SIZE = 1024 * 1024  # 1MB limit for base64

    def get_clipboard_image(self) -> Optional[QImage]:
        """Check clipboard for an image and return it.

        Returns:
            QImage from clipboard, or None if no image
        """
        clipboard = QClipboard()
        mime = clipboard.mimeData()

        if mime.hasImage():
            image = clipboard.image()
            if not image.isNull():
                return image

        if mime.hasUrls():
            for url in mime.urls():
                path = url.toLocalFile()
                if path and Path(path).suffix.lower() in (
                    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"
                ):
                    image = QImage(path)
                    if not image.isNull():
                        return image

        return None

    def has_clipboard_image(self) -> bool:
        """Quick check if clipboard contains an image."""
        return self.get_clipboard_image() is not None

    def save_temp_image(self, image: QImage, format: str = "PNG") -> Optional[Path]:
        """Save an image to a temp file.

        Args:
            image: QImage to save
            format: Image format (PNG, JPEG, etc.)

        Returns:
            Path to temp file, or None on failure
        """
        try:
            buf = io.BytesIO()
            image.save(buf, format)
            data = buf.getvalue()

            if len(data) > self.MAX_IMAGE_SIZE:
                # Resize to fit
                image = image.scaledToWidth(
                    min(image.width(), 800),
                    Qt.TransformationMode.SmoothTransformation,
                )
                buf = io.BytesIO()
                image.save(buf, format)
                data = buf.getvalue()

            suffix = f".{format.lower()}"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
                f.write(data)
                return Path(f.name)

        except Exception as e:
            logger.error("Failed to save image: %s", e)
            return None

    def image_to_base64(self, image: QImage, format: str = "PNG") -> Optional[str]:
        """Convert QImage to base64 string.

        Args:
            image: QImage to convert
            format: Image format

        Returns:
            Base64 encoded string, or None on failure
        """
        try:
            buf = io.BytesIO()
            image.save(buf, format)
            return base64.b64encode(buf.getvalue()).decode("utf-8")
        except Exception as e:
            logger.error("Failed to encode image: %s", e)
            return None

    def get_image_info(self, image: QImage) -> dict:
        """Get image metadata.

        Returns:
            Dict with width, height, size, format
        """
        buf = io.BytesIO()
        image.save(buf, "PNG")
        return {
            "width": image.width(),
            "height": image.height(),
            "size_bytes": buf.tell(),
            "format": "PNG",
        }


class ClipboardWatcher:
    """Watches clipboard for image paste events (Aider pattern).

    Signals are not used here since this is a pure Python service.
    Use poll() in a timer loop instead.
    """

    def __init__(self) -> None:
        self._image_service = ImageService()
        self._last_image_hash: Optional[int] = None

    def poll(self) -> Optional[QImage]:
        """Check if a new image was pasted to clipboard.

        Returns:
            New QImage if a new image was detected, None otherwise
        """
        image = self._image_service.get_clipboard_image()
        if image is None:
            return None

        # Check if this is a new image (simple hash check)
        buf = io.BytesIO()
        image.save(buf, "PNG")
        current_hash = hash(buf.getvalue())

        if current_hash != self._last_image_hash:
            self._last_image_hash = current_hash
            return image

        return None
