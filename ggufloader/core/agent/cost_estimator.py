"""
CostEstimator - Track token usage and estimate costs per model.

Pattern from: Aider's cost display + DeepSeek's StatsLine.
Since GGUFLoader runs local models, costs are estimated from:
1. Local GPU/CPU inference (electricity cost estimate)
2. Comparison with equivalent API pricing
3. Token throughput metrics

Features:
- Per-session token counting (input + output)
- Cost estimation for local inference
- API price comparison for equivalent models
- Throughput tracking (tokens/second)
- Session cost summary
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional


# API pricing for popular models (per 1M tokens)
# Used for comparison: "this would cost $X on the API"
API_PRICING = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00},
    "deepseek-chat": {"input": 0.14, "output": 0.28},
    "deepseek-reasoner": {"input": 0.55, "output": 2.19},
    "llama-3-70b": {"input": 0.88, "output": 0.88},
    "llama-3-8b": {"input": 0.05, "output": 0.05},
    "qwen-72b": {"input": 0.90, "output": 0.90},
}

# Electricity cost estimate (USD per kWh, US average)
ELECTRICITY_COST_PER_KWH = 0.12

# GPU power consumption estimates (watts)
GPU_POWER = {
    "rtx_4060": 115,
    "rtx_4070": 200,
    "rtx_4080": 320,
    "rtx_4090": 450,
    "rtx_3060": 170,
    "rtx_3070": 220,
    "rtx_3080": 320,
    "rtx_3090": 350,
    "a100": 400,
    "h100": 700,
}


class CostEstimator:
    """Track token usage and estimate costs.

    Usage:
        estimator = CostEstimator()
        estimator.start_session("mistral-7b")

        # After each LLM call
        estimator.record_call(input_tokens=500, output_tokens=200)

        # Get summary
        print(estimator.summary())
    """

    def __init__(self) -> None:
        self._model_name: str = ""
        self._session_start: float = 0
        self._calls: list[Dict[str, Any]] = []
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_generation_ms = 0
        self._gpu_name: Optional[str] = None

    def start_session(self, model_name: str, gpu_name: str = None) -> None:
        """Start a new cost tracking session."""
        self._model_name = model_name
        self._gpu_name = gpu_name
        self._session_start = time.monotonic()
        self._calls.clear()
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_generation_ms = 0

    def record_call(
        self,
        input_tokens: int = 0,
        output_tokens: int = 0,
        generation_ms: int = 0,
    ) -> None:
        """Record a single LLM call."""
        self._total_input_tokens += input_tokens
        self._total_output_tokens += output_tokens
        self._total_generation_ms += generation_ms

        self._calls.append({
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "generation_ms": generation_ms,
            "timestamp": time.time(),
        })

    def estimate_electricity_cost(self) -> float:
        """Estimate electricity cost for local inference.

        Returns estimated cost in USD.
        """
        if self._gpu_name:
            gpu_power = GPU_POWER.get(self._gpu_name.lower().replace(" ", "_"), 200)
        else:
            gpu_power = 200  # default estimate

        # Energy = power × time
        hours = self._total_generation_ms / (1000 * 3600)
        kwh = (gpu_power * hours) / 1000
        return kwh * ELECTRICITY_COST_PER_KWH

    def estimate_api_cost(self, api_model: str = None) -> Optional[Dict[str, float]]:
        """Estimate what this would cost on a cloud API.

        Args:
            api_model: API model name for pricing lookup.
                      If None, tries to match from model_name.

        Returns:
            {"input_cost": float, "output_cost": float, "total": float}
            or None if no pricing available.
        """
        # Try to match model name to API pricing
        pricing = None
        if api_model and api_model in API_PRICING:
            pricing = API_PRICING[api_model]
        else:
            # Fuzzy match
            model_lower = self._model_name.lower()
            for name, price in API_PRICING.items():
                if name.replace("-", "") in model_lower.replace("-", ""):
                    pricing = price
                    break

        if not pricing:
            return None

        input_cost = (self._total_input_tokens / 1_000_000) * pricing["input"]
        output_cost = (self._total_output_tokens / 1_000_000) * pricing["output"]
        return {
            "input_cost": round(input_cost, 6),
            "output_cost": round(output_cost, 6),
            "total": round(input_cost + output_cost, 6),
            "api_model": api_model or "matched",
        }

    def get_throughput(self) -> Dict[str, float]:
        """Get token throughput metrics."""
        total_tokens = self._total_input_tokens + self._total_output_tokens
        if self._total_generation_ms <= 0:
            return {"tokens_per_second": 0, "ms_per_token": 0}

        tps = total_tokens / (self._total_generation_ms / 1000)
        ms_per_token = self._total_generation_ms / max(total_tokens, 1)
        return {
            "tokens_per_second": round(tps, 1),
            "ms_per_token": round(ms_per_token, 2),
        }

    def summary(self) -> Dict[str, Any]:
        """Get full cost summary."""
        total_tokens = self._total_input_tokens + self._total_output_tokens
        throughput = self.get_throughput()
        electricity = self.estimate_electricity_cost()
        api_cost = self.estimate_api_cost()
        elapsed = time.monotonic() - self._session_start if self._session_start else 0

        return {
            "model": self._model_name,
            "gpu": self._gpu_name,
            "session_duration_s": round(elapsed, 1),
            "total_calls": len(self._calls),
            "input_tokens": self._total_input_tokens,
            "output_tokens": self._total_output_tokens,
            "total_tokens": total_tokens,
            "total_generation_ms": self._total_generation_ms,
            "throughput": throughput,
            "electricity_cost_usd": round(electricity, 6),
            "api_cost_comparison": api_cost,
            "savings_vs_api": round(api_cost["total"] - electricity, 6) if api_cost else None,
        }

    def format_summary(self) -> str:
        """Format a human-readable summary."""
        s = self.summary()
        lines = [
            f"Model: {s['model']}",
            f"Tokens: {s['input_tokens']} in / {s['output_tokens']} out ({s['total_tokens']} total)",
            f"Calls: {s['total_calls']}",
            f"Throughput: {s['throughput']['tokens_per_second']} tok/s",
            f"Electricity: ${s['electricity_cost_usd']:.4f}",
        ]
        if s["api_cost_comparison"]:
            api = s["api_cost_comparison"]
            lines.append(f"API equivalent: ${api['total']:.4f} ({api['api_model']})")
            if s["savings_vs_api"] is not None:
                lines.append(f"You saved: ${s['savings_vs_api']:.4f}")
        return "\n".join(lines)
