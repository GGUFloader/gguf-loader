# config.py - Enhanced for Persian Language Support
import os
from pathlib import Path

# Add these near the top of config.py
DEFAULT_SYSTEM_PROMPT = "bilingual_assistant"
DEFAULT_PRESET = "balanced_persian"

# Application Configuration
WINDOW_TITLE = "GGUF Loader"  # AI Chat App in Persian
APP_NAME_EN = "AI Chat App"
APP_VERSION = "1.0.0"
WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 700
WINDOW_SIZE = (1200, 900)  # Fixed: was missing comma between values
MIN_WINDOW_SIZE = (800, 500)  # Fixed: was missing comma between values

# --- GPU and Context Configuration ---
GPU_OPTIONS = ["CPU Only", "GPU Accelerated"]
DEFAULT_GPU_MODE = False  # CPU only by default (GPU disabled)
DEFAULT_CONTEXT_SIZES = ["512", "1024", "2048", "4096", "8192", "16384", "32768"]
DEFAULT_CONTEXT_INDEX = 6  # 32768 context (index 6 in the list above)
SYSTEM_MESSAGE = "You are a helpful AI assistant."

# Model Configuration
MODEL_PATH = "models/DeepSeek-R1-0528-Qwen3-8B-Q4_K_M.gguf"
MODEL_TYPE = "deepseek_r1"
MAX_CONTEXT_LENGTH = 32768  # Set to 32K context
MAX_TOKENS = 2048

# Persian Language Settings
PERSIAN_SETTINGS = {
    "font_family": "Vazir, Tahoma, Arial",  # Persian-friendly fonts
    "font_size": 16,
    "text_direction": "rtl",  # Right-to-left for Persian
    "enable_reshaping": True,  # For proper Persian character rendering
    "enable_bidi": True,  # Bidirectional text support
    "fallback_font": "Arial Unicode MS"
}

# Language Detection Patterns
LANGUAGE_PATTERNS = {
    "persian_ranges": [
        (0x0600, 0x06FF),  # Arabic/Persian
        (0x0750, 0x077F),  # Arabic Supplement
        (0xFB50, 0xFDFF),  # Arabic Presentation Forms-A
        (0xFE70, 0xFEFF)  # Arabic Presentation Forms-B
    ],
    "persian_threshold": 0.3,  # Minimum ratio to consider text as Persian
    "mixed_threshold": 0.1  # Minimum ratio to consider text as mixed
}

# Persian System Prompts with Descriptions
PERSIAN_SYSTEM_PROMPTS = {
    "helpful_assistant": {
        "name_fa": "دستیار مفید",
        "name_en": "Helpful Assistant",
        "prompt": "شما یک دستیار هوشمند هستید. به همان زبان سوال کاربر پاسخ دهید و پاسخ‌ها را واضح و مختصر ارائه کنید.",
        "description_fa": "دستیار عمومی برای پاسخ به سوالات متنوع",
        "params": {"temperature": 0.7, "top_p": 0.9, "max_tokens": 20000}
    },
    "creative_writer": {
        "name_fa": "نویسنده خلاق",
        "name_en": "Creative Writer",
        "prompt": "شما یک نویسنده خلاق هستید. به زبان روان و ساده بنویسید و کمک کنید.",
        "description_fa": "کمک در نوشتن خلاقانه و ادبی",
        "params": {"temperature": 0.8, "top_p": 0.95, "max_tokens": 20000}
    },
    "code_expert": {
        "name_fa": "متخصص برنامه‌نویسی",
        "name_en": "Programming Expert",
        "prompt": "شما یک برنامه‌نویس با تجربه هستید. کدهای ساده و قابل فهم ارائه دهید.",
        "description_fa": "کمک در برنامه‌نویسی و توسعه نرم‌افزار",
        "params": {"temperature": 0.3, "top_p": 0.8, "max_tokens": 20000}
    },
    "persian_literature": {
        "name_fa": "استاد ادبیات فارسی",
        "name_en": "Persian Literature Master",
        "prompt": "شما متخصص ادبیات فارسی هستید و به سوالات ادبی پاسخ می‌دهید.",
        "description_fa": "تخصص در ادبیات کلاسیک و معاصر فارسی",
        "params": {"temperature": 0.7, "top_p": 0.9, "max_tokens": 2000}
    },
    "translator": {
        "name_fa": "مترجم حرفه‌ای",
        "name_en": "Professional Translator",
        "prompt": "شما یک مترجم حرفه‌ای فارسی و انگلیسی هستید و ترجمه‌های دقیق ارائه می‌دهید.",
        "description_fa": "ترجمه دقیق بین فارسی و انگلیسی",
        "params": {"temperature": 0.5, "top_p": 0.8, "max_tokens": 20000}
    },
    "history_expert": {
        "name_fa": "متخصص تاریخ ایران",
        "name_en": "Iranian History Expert",
        "prompt": "شما متخصص تاریخ و فرهنگ ایران هستید و پاسخ‌های دقیق می‌دهید.",
        "description_fa": "تخصص در تاریخ و فرهنگ ایران",
        "params": {"temperature": 0.4, "top_p": 0.8, "max_tokens": 20000}
    },
    "math_tutor": {
        "name_fa": "معلم ریاضی",
        "name_en": "Math Tutor",
        "prompt": "شما معلم ریاضی هستید و مسائل را ساده و کوتاه توضیح می‌دهید.",
        "description_fa": "آموزش ریاضی قدم به قدم",
        "params": {"temperature": 0.2, "top_p": 0.7, "max_tokens": 20480}
    },
    "science_teacher": {
        "name_fa": "معلم علوم",
        "name_en": "Science Teacher",
        "prompt": "شما معلم علوم هستید و مفاهیم علمی را ساده بیان می‌کنید.",
        "description_fa": "آموزش علوم طبیعی و فیزیک",
        "params": {"temperature": 0.4, "top_p": 0.8, "max_tokens": 20480}
    }
}
# English System Prompts (for comparison/fallback)
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

# Bilingual System Prompts
BILINGUAL_SYSTEM_PROMPTS = {
    "bilingual_assistant": {
        "name_fa": "دستیار دوزبانه",
        "name_en": "Bilingual Assistant",
        "prompt": """You are a bilingual AI assistant fluent in both Persian and English.
شما یک دستیار هوشمند دوزبانه هستید که به فارسی و انگلیسی مسلط هستید.

Instructions:
- Respond in the same language as the user's question.
- For Persian questions, respond in Persian.
- For English questions, respond in English.
- For mixed language, use the dominant language.
- Keep answers clear and concise.
- Avoid unnecessary repetition and do not over-explain.
- Stay on topic and be culturally sensitive.
""",
        "params": {
            "temperature": 0.7,
            "top_p": 0.9,
            "max_tokens": 2048
        }
    }
}



# Generation Parameters Optimized for Persian
PERSIAN_GENERATION_PRESETS = {
    "balanced_persian": {
        "temperature": 0.9,
        "top_p": 0.9,
        "top_k": 50,
        "repeat_penalty": 1.1,
        "max_tokens": 30720,
        "description_fa": "متعادل برای استفاده عمومی"
    },
    "creative_persian": {
        "temperature": 0.8,
        "top_p": 0.95,
        "top_k": 100,
        "repeat_penalty": 1.05,
        "max_tokens": 40960,
        "description_fa": "خلاقانه برای نوشتن ادبی"
    },
    "precise_persian": {
        "temperature": 0.3,
        "top_p": 0.8,
        "top_k": 40,
        "repeat_penalty": 1.05,
        "max_tokens": 40960,
        "description_fa": "دقیق برای سوالات فنی"
    },
    "literary_persian": {
        "temperature": 0.75,
        "top_p": 0.9,
        "top_k": 60,
        "repeat_penalty": 1.08,
        "max_tokens": 40960,
        "description_fa": "مخصوص ادبیات و شعر"
    }
}

# DeepSeek-R1 Specific Optimizations for Persian
DEEPSEEK_PERSIAN_CONFIG = {
    # Removed reasoning prompts and output_format.reasoning_instruction to avoid loops
    "persian_specific_params": {
        "temperature": 0.6,
        "top_p": 0.85,
        "top_k": 45,
        "repeat_penalty": 1.12,
        "frequency_penalty": 0.1,
        "presence_penalty": 0.05
    }
    # You can add other config values as needed but avoid adding reasoning instructions here
}

# Persian Text Processing
PERSIAN_TEXT_CONFIG = {
    "normalization": {
        "convert_arabic_chars": True,  # Convert ي to ی, ك to ک
        "fix_persian_punctuation": True,
        "normalize_zwnj": True,  # Zero Width Non-Joiner
        "fix_persian_numbers": False  # Keep Arabic numerals for compatibility
    },
    "rendering": {
        "use_harfbuzz": True,  # Better text shaping
        "enable_ligatures": True,
        "kashida_justification": False,  # Disable for better readability
        "line_breaking": "persian"
    }
}

# UI Localization
UI_STRINGS = {
    "fa": {
        "chat_title": "گفتگو با هوش مصنوعی",
        "send_button": "ارسال",
        "clear_chat": "پاک کردن گفتگو",
        "settings": "تنظیمات",
        "model_settings": "تنظیمات مدل",
        "language": "زبان",
        "prompt_placeholder": "پیام خود را بنویسید...",
        "thinking": "در حال تفکر...",
        "generating": "در حال تولید پاسخ...",
        "error": "خطا",
        "retry": "تلاش مجدد",
        "copy": "کپی",
        "copied": "کپی شد!",
        "new_chat": "گفتگوی جدید",
        "save_chat": "ذخیره گفتگو",  # Fixed: was "ذخیره" (missing character)
        "load_chat": "بارگیری گفتگو",
        "export_chat": "خروجی گفتگو",
        "system_prompt": "دستورالعمل سیستم",
        "temperature": "خلاقیت",
        "max_tokens": "حداکثر توکن",
        "model_not_found": "مدل یافت نشد",
        "loading_model": "در حال بارگیری مدل...",
        "model_loaded": "مدل بارگیری شد",
        "characters": "کاراکتر",
        "words": "کلمه",
        "tokens_estimate": "تخمین توکن"
    },
    "en": {
        "chat_title": "AI Chat",
        "send_button": "Send",
        "clear_chat": "Clear Chat",
        "settings": "Settings",
        "model_settings": "Model Settings",
        "language": "Language",
        "prompt_placeholder": "Type your message...",
        "thinking": "Thinking...",
        "generating": "Generating response...",
        "error": "Error",
        "retry": "Retry",
        "copy": "Copy",
        "copied": "Copied!",
        "new_chat": "New Chat",
        "save_chat": "Save Chat",
        "load_chat": "Load Chat",
        "export_chat": "Export Chat",
        "system_prompt": "System Prompt",
        "temperature": "Temperature",
        "max_tokens": "Max Tokens",
        "model_not_found": "Model not found",
        "loading_model": "Loading model...",
        "model_loaded": "Model loaded",
        "characters": "Characters",
        "words": "Words",
        "tokens_estimate": "Tokens estimate"
    }
}

# Persian Keyboard Shortcuts
PERSIAN_SHORTCUTS = {
    "send_message": "Ctrl+Enter",
    "new_chat": "Ctrl+N",
    "clear_chat": "Ctrl+L",
    "toggle_rtl": "Ctrl+Shift+R",
    "persian_mode": "Ctrl+Shift+P",
    "english_mode": "Ctrl+Shift+E"
}

# Export/Import Settings
EXPORT_SETTINGS = {
    "default_format": "json",
    "include_metadata": True,
    "include_system_prompts": True,
    "compress_exports": False,
    "max_export_size": 10 * 1024 * 1024,  # 10MB
    "export_formats": ["json", "txt", "md", "html"]
}

# Performance Settings
PERFORMANCE_CONFIG = {
    "max_chat_history": 1000,  # Maximum messages to keep in memory
    "auto_save_interval": 300,  # Auto-save every 5 minutes (seconds)
    "lazy_loading": True,
    "virtual_scrolling": True,
    "debounce_typing": 300,  # ms
    "chunk_size": 512,  # For streaming responses
    "max_concurrent_requests": 1
}

# Style Constants
FONT_FAMILY = "Vazirmatn, Segoe UI, Arial"
FONT_SIZE = 16
BUBBLE_FONT_SIZE = 18

# Chat bubble sizing
CHAT_BUBBLE_MIN_WIDTH = 600
CHAT_BUBBLE_MAX_WIDTH = 1600
CHAT_BUBBLE_FONT_SIZE = 14
CHAT_BUBBLE_LINE_HEIGHT = 1.4

# Color Schemes
COLOR_SCHEMES = {
    "default": {
        "primary": "#2563eb",
        "secondary": "#64748b",
        "accent": "#0ea5e9",
        "background": "#ffffff",
        "surface": "#f8fafc",
        "text_primary": "#1e293b",
        "text_secondary": "#64748b",
        "border": "#e2e8f0",
        "user_bubble": "#2563eb",
        "assistant_bubble": "#f1f5f9",
        "user_text": "#ffffff",
        "assistant_text": "#1e293b"
    },
    "dark": {
        "primary": "#3b82f6",
        "secondary": "#6b7280",
        "accent": "#06b6d4",
        "background": "#0f172a",
        "surface": "#1e293b",
        "text_primary": "#e2e8f0",
        "text_secondary": "#cbd5e1",
        "border": "#334155",
        "user_bubble": "#3b82f6",
        "assistant_bubble": "#1e293b",
        "user_text": "#ffffff",
        "assistant_text": "#e2e8f0"
    },
    "persian_classic": {
        "primary": "#dc2626",
        "secondary": "#7c2d12",
        "accent": "#ea580c",
        "background": "#fefce8",
        "surface": "#fef3c7",
        "text_primary": "#451a03",
        "text_secondary": "#92400e",
        "border": "#fbbf24",
        "user_bubble": "#dc2626",
        "assistant_bubble": "#fef3c7",
        "user_text": "#ffffff",
        "assistant_text": "#451a03"
    }
}

# Development and Debug Settings
DEBUG_CONFIG = {
    "enable_debug": False,
    "log_level": "INFO",
    "show_token_count": True,
    "show_generation_time": True,
    "show_model_stats": False,
    "enable_profiling": False,
    "log_file": "persian_ai_chat.log"
}

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


# Get current configuration based on language preference
def get_current_config(language="fa"):
    """Get configuration for specified language"""
    if language == "fa":
        return {
            "ui_strings": UI_STRINGS["fa"],
            "system_prompts": PERSIAN_SYSTEM_PROMPTS,
            "generation_presets": PERSIAN_GENERATION_PRESETS,
            "text_config": PERSIAN_TEXT_CONFIG,
            "deepseek_config": DEEPSEEK_PERSIAN_CONFIG
        }
    else:
        return {
            "ui_strings": UI_STRINGS["en"],
            "system_prompts": ENGLISH_SYSTEM_PROMPTS,
            "generation_presets": PERSIAN_GENERATION_PRESETS,  # Can be used for both
            "text_config": {},
            "deepseek_config": {}
        }


# Language detection utility
def detect_language(text):
    """Detect if text is primarily Persian, English, or mixed"""
    if not text:
        return "en"

    persian_chars = 0
    total_chars = len(text)

    for char in text:
        char_code = ord(char)
        for start, end in LANGUAGE_PATTERNS["persian_ranges"]:
            if start <= char_code <= end:
                persian_chars += 1
                break

    persian_ratio = persian_chars / total_chars if total_chars > 0 else 0

    if persian_ratio >= LANGUAGE_PATTERNS["persian_threshold"]:
        return "fa"
    elif persian_ratio >= LANGUAGE_PATTERNS["mixed_threshold"]:
        return "mixed"
    else:
        return "en"


def get_persian_config():
    """Get Persian-specific configuration settings"""
    config = {
        "persian_literature_prompt": PERSIAN_SYSTEM_PROMPTS["persian_literature"]["prompt"],
        "literary_persian_params": PERSIAN_GENERATION_PRESETS["literary_persian"],
        "persian_specific_params": DEEPSEEK_PERSIAN_CONFIG["persian_specific_params"],
        "normalization_settings": PERSIAN_TEXT_CONFIG["normalization"],
        "thinking_ui": UI_STRINGS["fa"]["thinking"]
    }
    return config


# Initialize directories on import
ensure_directories()