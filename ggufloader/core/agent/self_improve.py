"""
SelfImprove - Learn from corrections and feedback to improve agent behavior.

Pattern from: Aider's learning + ChatGPT's custom instructions evolution.
Tracks patterns in user corrections to:
1. Avoid repeating the same mistakes
2. Adapt to user preferences
3. Learn project-specific conventions
4. Improve tool usage patterns

The system maintains a feedback loop:
- Agent makes a decision
- User corrects or approves
- Pattern is extracted and stored
- Future similar decisions use the learned pattern
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class Correction:
    """A single user correction."""

    def __init__(self, context: str, agent_action: str, correct_action: str,
                 category: str = "general", explanation: str = "") -> None:
        self.context = context
        self.agent_action = agent_action
        self.correct_action = correct_action
        self.category = category
        self.explanation = explanation
        self.timestamp = time.time()
        self.times_applied = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "context": self.context,
            "agent_action": self.agent_action,
            "correct_action": self.correct_action,
            "category": self.category,
            "explanation": self.explanation,
            "timestamp": self.timestamp,
            "times_applied": self.times_applied,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Correction":
        c = cls(
            context=data.get("context", ""),
            agent_action=data.get("agent_action", ""),
            correct_action=data.get("correct_action", ""),
            category=data.get("category", "general"),
            explanation=data.get("explanation", ""),
        )
        c.timestamp = data.get("timestamp", 0)
        c.times_applied = data.get("times_applied", 0)
        return c


class LearnedPreference:
    """A user preference learned from behavior."""

    def __init__(self, key: str, value: str, confidence: float = 0.5) -> None:
        self.key = key
        self.value = value
        self.confidence = confidence
        self.observation_count = 0
        self.last_observed = time.time()

    def observe(self) -> None:
        self.observation_count += 1
        self.last_observed = time.time()
        # Increase confidence with more observations (cap at 1.0)
        self.confidence = min(1.0, self.confidence + 0.1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "confidence": round(self.confidence, 2),
            "observations": self.observation_count,
        }


class SelfImprove:
    """Learn from user corrections and improve agent behavior.

    Usage:
        improve = SelfImprove(workspace_path)

        # Record a correction
        improve.record_correction(
            context="Editing main.py",
            agent_action="Used os.remove()",
            correct_action="Used pathlib.Path.unlink()",
            category="style",
            explanation="This project prefers pathlib over os"
        )

        # Get advice for current context
        advice = improve.get_advice("editing Python files")

        # Learn from implicit feedback
        improve.observe_preference("code_style", "pathlib")
    """

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self._data_file = workspace / ".ggufloader-learning.json"
        self._corrections: List[Correction] = []
        self._preferences: Dict[str, LearnedPreference] = {}
        self._patterns: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if not self._data_file.exists():
            return
        try:
            data = json.loads(self._data_file.read_text(encoding="utf-8"))
            self._corrections = [Correction.from_dict(c) for c in data.get("corrections", [])]
            for p in data.get("preferences", []):
                pref = LearnedPreference(p["key"], p["value"], p.get("confidence", 0.5))
                pref.observation_count = p.get("observations", 0)
                self._preferences[p["key"]] = pref
            self._patterns = data.get("patterns", [])
        except Exception as e:
            logger.warning("Failed to load learning data: %s", e)

    def _save(self) -> None:
        try:
            data = {
                "version": 1,
                "corrections": [c.to_dict() for c in self._corrections],
                "preferences": [p.to_dict() for p in self._preferences.values()],
                "patterns": self._patterns,
            }
            self._data_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error("Failed to save learning data: %s", e)

    def record_correction(self, context: str, agent_action: str,
                          correct_action: str, category: str = "general",
                          explanation: str = "") -> None:
        """Record a user correction."""
        correction = Correction(context, agent_action, correct_action,
                               category, explanation)
        self._corrections.append(correction)

        # Extract pattern from correction
        self._extract_pattern(correction)

        # Keep only last 200 corrections
        if len(self._corrections) > 200:
            self._corrections = self._corrections[-200:]

        self._save()
        logger.info("Recorded correction: %s → %s", agent_action, correct_action)

    def observe_preference(self, key: str, value: str) -> None:
        """Observe a user preference from behavior."""
        if key in self._preferences:
            pref = self._preferences[key]
            if pref.value == value:
                pref.observe()
            else:
                # New value observed, update if more confident
                pref.value = value
                pref.observe()
        else:
            self._preferences[key] = LearnedPreference(key, value, 0.3)
        self._save()

    def get_advice(self, context: str) -> str:
        """Get advice based on learned corrections and preferences.

        Returns a string the agent can use to improve its decisions.
        """
        advice_parts = []

        # Find relevant corrections
        context_lower = context.lower()
        relevant = [
            c for c in self._corrections
            if any(word in c.context.lower() or word in c.category
                   for word in context_lower.split())
        ]

        if relevant:
            advice_parts.append("Based on past corrections:")
            for c in relevant[-5:]:  # last 5 relevant
                advice_parts.append(f"- Instead of '{c.agent_action}', do '{c.correct_action}'")
                if c.explanation:
                    advice_parts.append(f"  Reason: {c.explanation}")

        # Find relevant preferences
        relevant_prefs = [
            p for p in self._preferences.values()
            if p.confidence > 0.5 and any(
                word in p.key.lower() for word in context_lower.split()
            )
        ]

        if relevant_prefs:
            advice_parts.append("User preferences:")
            for p in relevant_prefs[:5]:
                advice_parts.append(f"- {p.key}: {p.value} (confidence: {p.confidence:.0%})")

        return "\n".join(advice_parts) if advice_parts else ""

    def get_correction_for(self, action: str) -> Optional[Correction]:
        """Find a correction that matches the given action."""
        action_lower = action.lower()
        for c in reversed(self._corrections):
            if c.agent_action.lower() in action_lower or action_lower in c.agent_action.lower():
                c.times_applied += 1
                self._save()
                return c
        return None

    def _extract_pattern(self, correction: Correction) -> None:
        """Extract a reusable pattern from a correction."""
        pattern = {
            "trigger": correction.agent_action,
            "replacement": correction.correct_action,
            "category": correction.category,
            "count": 1,
        }

        # Check if similar pattern exists
        for existing in self._patterns:
            if (existing["trigger"].lower() == pattern["trigger"].lower() or
                    existing["replacement"].lower() == pattern["replacement"].lower()):
                existing["count"] += 1
                return

        self._patterns.append(pattern)
        # Keep top 100 patterns
        if len(self._patterns) > 100:
            self._patterns.sort(key=lambda p: -p["count"])
            self._patterns = self._patterns[:100]

    def get_patterns(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get learned patterns sorted by frequency."""
        return sorted(self._patterns, key=lambda p: -p["count"])[:limit]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "corrections": len(self._corrections),
            "preferences": len(self._preferences),
            "patterns": len(self._patterns),
            "total_applications": sum(c.times_applied for c in self._corrections),
            "categories": list(set(c.category for c in self._corrections)),
        }

    def clear(self) -> None:
        self._corrections.clear()
        self._preferences.clear()
        self._patterns.clear()
        self._save()
