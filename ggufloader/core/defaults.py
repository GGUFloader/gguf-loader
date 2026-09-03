"""Canonical defaults — the single table of performance constants.

Every module in the app must import its load/sampling/stops defaults from
here instead of declaring magic numbers. If a default ever needs to change,
it changes in exactly one place.

Reference rig this was tuned against: Gemma-8 Q4_K_M on 8 GB VRAM /
32 GB RAM (must generalize to arbitrary user models).
"""

# Context / batch -----------------------------------------------------------
DEFAULT_CTX = 8192
CTX_OPTIONS = (2048, 4096, 8192, 16384, 32768)
N_BATCH_DEFAULT = 512

# Sampling ------------------------------------------------------------------
TEMP_ACTION = 0.2        # tool-call/planning decisions: near-greedy
TEMP_ANSWER = 0.6        # final prose answers: mild creativity
MAX_TOKENS_CHAT = 4096
MAX_TOKENS_AGENT_ACTION = 2048
MAX_TOKENS_AGENT_ANSWER = 4096

# Memory headroom -----------------------------------------------------------
VRAM_HEADROOM = 0.85     # usable fraction of VRAM for model+KV
RAM_HEADROOM = 0.8       # usable fraction of RAM for model+KV
CUDA_RESERVE_GB = 1.0    # VRAM reserved for CUDA context / activations

# Stop tokens ---------------------------------------------------------------
# Unified across chat, agent, and both UIs. Never add bare lowercase
# "user:" / "assistant:" markers here — they truncate mid-word in prose.
STOP_TOKENS_UNIFIED = [
    "<|im_end|>", "<|endoftext|>", "<|eot_id|>", "</s>",
    "<|end_of_text|>", "<|return|>",
    "<end_of_turn>", "<start_of_turn>",
]
