"""
Utility functions for the AI chat application
"""
from PySide6.QtGui import QFontDatabase

def detect_persian_text(text: str) -> bool:
    """
    Detect if text contains Persian characters
    Returns True if text is primarily Persian, False otherwise
    """
    if not text.strip():
        return False

    
    persian_chars = 0
    total_chars = 0

    for char in text:
        if char.isalpha():
            total_chars += 1
            # Persian/Arabic Unicode ranges
            if ('\u0600' <= char <= '\u06FF' or  # Arabic
                    '\u0750' <= char <= '\u077F' or  # Arabic Supplement
                    '\uFB50' <= char <= '\uFDFF' or  # Arabic Presentation Forms-A
                    '\uFE70' <= char <= '\uFEFF'):  # Arabic Presentation Forms-B
                persian_chars += 1

    if total_chars == 0:
        return False

    
    # If more than 30% of alphabetic characters are Persian, consider it Persian text
    return (persian_chars / total_chars) > 0.6

def load_fonts():
    """Load application fonts"""
    font_db = QFontDatabase()
    if "Vazirmatn" not in font_db.families():
        print("Warning: Vazirmatn font not found. Falling back to system fonts.")
