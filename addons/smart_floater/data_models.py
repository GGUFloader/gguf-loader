"""
Core data models for the Smart Floating Assistant addon.

This module defines the dataclasses used throughout the addon for
representing text selections, processing results, and UI state.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple


@dataclass
class TextSelection:
    """Represents a text selection captured from any application."""
    content: str
    cursor_position: Tuple[int, int]
    timestamp: datetime
    source_app: str


@dataclass
class ProcessingResult:
    """Represents the result of AI text processing."""
    original_text: str
    processed_text: str
    processing_type: str  # 'summary' or 'comment'
    success: bool
    error_message: Optional[str]
    processing_time: float


@dataclass
class UIState:
    """Represents the current state of the floating UI components."""
    is_button_visible: bool
    is_popup_open: bool
    current_selection: Optional[TextSelection]
    last_result: Optional[ProcessingResult]