# config.py - Application configuration
from pathlib import Path

# Application Configuration
WINDOW_TITLE = "GGUF Loader"
WINDOW_SIZE = (1200, 900)
MIN_WINDOW_SIZE = (800, 500)

# --- GPU and Context Configuration ---
DEFAULT_CONTEXT_SIZES = ["512", "1024", "2048", "4096", "8192", "16384", "32768"]

# Generation
MAX_TOKENS = 2048
# Thinking models spend thousands of tokens reasoning before the answer;
# the chat budget must cover thought + answer or generation dies mid-think.
CHAT_MAX_TOKENS = 16384

# Chat sampling defaults. Low temperature matches Ollama's baked-in
# recommendations for small instruct models (e.g. LiquidAI LFM2.5 ships
# temp 0.2 / top_k 80 / repeat 1.05): at 0.7+ such models spiral into
# unclosed <think> loops until the context window fills.
CHAT_TEMPERATURE = 0.2
CHAT_TOP_K = 80
CHAT_TOP_P = 0.9
CHAT_MIN_P = 0.0
CHAT_REPEAT_PENALTY = 1.05


# --- Pinned single-model build identity ---
# This build is optimized for exactly one model (Gemma 4 12B Q4_K_M).
# Shown in the app-level version banner and the first-launch compatibility
# dialog; the load gate rejects any other GGUF (see api/routes/model.py).
APP_NAME = "GGUF Loader"
PINNED_MODEL_LABEL = "Gemma 4 12B Q4_K_M"
PINNED_TAGLINE = "Optimized for Gemma 4 12B Q4_K_M"
PINNED_ARCH = "gemma4"
PINNED_QUANT = "Q4_K_M"
PINNED_SIZE = "12B"
# Community GGUF source for the pinned model (bartowski quantization,
# matches the Q4_K_M load gate). Used by the in-app download option.
PINNED_MODEL_FILENAME = "gemma-4-12B-it-Q4_K_M.gguf"
PINNED_MODEL_URL = (
    "https://huggingface.co/bartowski/gemma-4-12B-it-GGUF/resolve/main/"
    + PINNED_MODEL_FILENAME
)


# Style Constants
FONT_FAMILY = "Vazirmatn, Segoe UI, Arial"
BUBBLE_FONT_SIZE = 18

# Chat bubble sizing
CHAT_BUBBLE_FONT_SIZE = 14

# File paths - will be initialized by get_paths()
PATHS = {}


def get_paths():
    """Get paths using resource manager for proper deployment handling"""
    from ggufloader.resource_manager import (
        get_resource_path, find_config_dir, find_cache_dir, find_logs_dir,
        get_user_data_dir, get_deployment_info,
    )

    # For installed/frozen deployments, models/chats/exports live in the
    # per-user data dir - never inside site-packages (may be read-only).
    if get_deployment_info()['deployment_type'] in ('pyinstaller', 'frozen', 'installed_package'):
        data_root = Path(get_user_data_dir())
        return {
            "models": data_root / "models",
            "chats": data_root / "chats",
            "exports": data_root / "exports",
            "logs": Path(find_logs_dir()),
            "config": Path(find_config_dir()),
            "cache": Path(find_cache_dir())
        }

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
