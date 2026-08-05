# config.py - Application configuration
from pathlib import Path

# Application Configuration
WINDOW_TITLE = "GGUF Loader"
WINDOW_SIZE = (1200, 900)
MIN_WINDOW_SIZE = (800, 500)

# --- GPU and Context Configuration ---
GPU_OPTIONS = ["CPU Only", "GPU Accelerated"]
DEFAULT_CONTEXT_SIZES = ["512", "1024", "2048", "4096", "8192", "16384", "32768"]

# Generation
MAX_TOKENS = 2048

# English System Prompts
ENGLISH_SYSTEM_PROMPTS = {
    "helpful_assistant": {
        "name": "Helpful Assistant",
        "prompt": "You are a helpful AI assistant. Provide accurate, clear responses and think step by step.",
        "params": {"temperature": 0.7, "top_p": 0.9, "max_tokens": 20480}
    },
    "creative_writer": {
        "name": "Creative Writer",
        "prompt": "You are a creative writing assistant. Help with storytelling and creative content.",
        "params": {"temperature": 0.8, "top_p": 0.95, "max_tokens": 30720}
    }
}

# Style Constants
FONT_FAMILY = "Vazirmatn, Segoe UI, Arial"
BUBBLE_FONT_SIZE = 18

# Chat bubble sizing
CHAT_BUBBLE_FONT_SIZE = 14

# File paths - will be initialized by get_paths()
PATHS = {}


def get_paths():
    """Get paths using resource manager for proper deployment handling"""
    from resource_manager import get_resource_path, find_config_dir, find_cache_dir, find_logs_dir

    return {
        "models": Path(get_resource_path("models")),
        "chats": Path(get_resource_path("chats")),
        "exports": Path(get_resource_path("exports")),
        "logs": Path(find_logs_dir()),
        "config": Path(find_config_dir()),
        "cache": Path(find_cache_dir())
    }


# Ensure directories exist
def ensure_directories():
    """Create necessary directories if they don't exist"""
    global PATHS
    if not PATHS:
        PATHS = get_paths()

    for path in PATHS.values():
        path.mkdir(parents=True, exist_ok=True)


# Initialize directories on import
ensure_directories()
