"""
Agentic Chatbot Addon for GGUF Loader
"""

def register(parent=None):
    """
    Register function called by the GGUF Loader addon system.
    
    Args:
        parent: Parent widget (GGUF Loader main window)
        
    Returns:
        QWidget: Status widget for the addon sidebar, or None for background addons
    """
    # Import here to avoid circular imports
    from .main import register as _register
    return _register(parent)

__all__ = ['register']