"""
AI response generation functionality with English support only
"""
from PySide6.QtCore import QThread, Signal
from config import (
    MAX_TOKENS,
    ENGLISH_SYSTEM_PROMPTS
)

class ChatGenerator(QThread):
    """Thread for generating AI responses in English"""
    token_received = Signal(str)  # New token
    finished = Signal()  # Generation complete
    error = Signal(str)  # Error occurred

    def __init__(self, model, prompt: str, chat_history: list,
                 max_tokens: int = MAX_TOKENS + 30000,
                 system_prompt_name: str = "assistant",
                 temperature: float = 0.7,
                 top_p: float = 0.9,
                 repeat_penalty: float = 1.1,
                 top_k: int = 40):
        super().__init__()
        self.model = model
        self.raw_prompt = prompt
        self.chat_history = chat_history
        self.max_tokens = max_tokens
        self.stop_generation = False
        self.system_prompt_name = system_prompt_name

        # Generation parameters
        self.temperature = temperature
        self.top_p = top_p
        self.repeat_penalty = repeat_penalty
        self.top_k = top_k

        # Build system prompt
        self.system_prompt = self.build_system_prompt()
        self.full_prompt = self.format_full_prompt()

        # Stop tokens for English
        self.stop_tokens = [
            "<|im_end|>", "</s>", "user:", "assistant:", "###",
            "\nHuman:", "\nUser:", "Human:", "User:"
        ]

    def build_system_prompt(self):
        """Construct system prompt for English"""
        if self.system_prompt_name in ENGLISH_SYSTEM_PROMPTS:
            return ENGLISH_SYSTEM_PROMPTS[self.system_prompt_name]["prompt"]
        else:
            # Fallback to default assistant prompt
            return "You are a helpful AI assistant. Answer questions clearly and concisely."

    def format_full_prompt(self):
        """Format complete prompt with history"""
        # Start with system prompt
        formatted = self.system_prompt + "\n\n"
        formatted += "Answer clearly and concisely.\n\n"

        # Add conversation history
        for msg in self.chat_history:
            role = msg.get('role', 'user')
            content = msg.get('content', '')

            if role == 'user':
                formatted += f"User: {content}\n"
            elif role == 'assistant':
                formatted += f"Assistant: {content}\n"

        # Add current prompt
        formatted += f"User: {self.raw_prompt}\nAssistant: "

        return formatted

    def run(self):
        try:
            if not self.model:
                self.error.emit("No model loaded")
                return

            # Generate response with streaming
            stream = self.model(
                self.full_prompt,
                max_tokens=self.max_tokens,
                stream=True,
                stop=self.stop_tokens,
                temperature=self.temperature,
                top_p=self.top_p,
                repeat_penalty=self.repeat_penalty,
                top_k=self.top_k
            )

            response_text = ""
            for token_data in stream:
                if self.stop_generation:
                    break

                token = token_data.get('choices', [{}])[0].get('text', '')
                if token:
                    response_text += token

                    # Stop if we encounter stop patterns
                    if any(stop in response_text.lower() for stop in self.stop_tokens):
                        break

                    self.token_received.emit(token)

            self.finished.emit()

        except Exception as e:
            self.error.emit(f"Generation error: {str(e)}")

    def stop(self):
        self.stop_generation = True