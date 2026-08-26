"""
Utility functions for the AI chat application
"""

import ctypes
import os
import platform


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


def get_system_ram_bytes() -> int | None:
    """Total physical RAM in bytes, or None when unavailable."""
    try:
        if platform.system() == "Windows":
            class MEMORYSTATUSEX(ctypes.Structure):  # noqa: N801
                _fields_ = [("dwLength", ctypes.c_ulong),
                            ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return int(stat.ullTotalPhys)
        else:
            try:
                import psutil
                return int(psutil.virtual_memory().total)
            except ImportError:
                pass
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            if pages > 0 and page_size > 0:
                return pages * page_size
    except Exception:  # noqa: BLE001 - best-effort probe
        pass
    return None