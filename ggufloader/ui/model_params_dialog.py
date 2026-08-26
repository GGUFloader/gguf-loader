"""Per-model chat parameter dialog (C1-lite).

Edits the override entry in config/model_params.json for the currently
loaded model and re-applies it immediately. "Reset" removes the entry so
the auto-detected family profile applies again.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QDoubleSpinBox, QFormLayout, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout,
)

from ggufloader.core.llm.model_params import (
    clear_model_override, load_model_params, set_model_override,
)


class ModelParamsDialog(QDialog):
    """Sampling + system-prompt overrides for one loaded model."""

    def __init__(self, parent, model_path: str, current_params: dict,
                 current_system_prompt: str | None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Model Params — {Path(model_path).name}")
        self.setMinimumWidth(420)
        self.model_path = model_path

        saved = load_model_params(model_path)
        effective = dict(current_params)
        effective.update(saved)

        form = QFormLayout()
        form.setSpacing(8)

        self.temperature = QDoubleSpinBox(); self._rng(self.temperature, 0.0, 2.0, 0.05)
        self.top_p = QDoubleSpinBox(); self._rng(self.top_p, 0.05, 1.0, 0.01)
        self.min_p = QDoubleSpinBox(); self._rng(self.min_p, 0.0, 1.0, 0.01)
        self.top_k = QSpinBox(); self.top_k.setRange(0, 200)
        self.repeat_penalty = QDoubleSpinBox(); self._rng(self.repeat_penalty, 0.5, 2.0, 0.01)
        self.max_tokens = QSpinBox(); self.max_tokens.setRange(64, 65536); self.max_tokens.setSingleStep(256)

        self.temperature.setValue(float(effective.get("temperature", 0.2)))
        self.top_p.setValue(float(effective.get("top_p", 0.9)))
        self.min_p.setValue(float(effective.get("min_p", 0.0)))
        self.top_k.setValue(int(effective.get("top_k", 80)))
        self.repeat_penalty.setValue(float(effective.get("repeat_penalty", 1.05)))
        self.max_tokens.setValue(int(effective.get("max_tokens", 16384)))

        form.addRow("Temperature", self.temperature)
        form.addRow("Top-P", self.top_p)
        form.addRow("Min-P", self.min_p)
        form.addRow("Top-K", self.top_k)
        form.addRow("Repeat penalty", self.repeat_penalty)
        form.addRow("Max tokens", self.max_tokens)

        # Greedy mode: when temperature is 0, sampling params are ignored.
        # Disable them to make this clear (GPT4All parity).
        self.temperature.valueChanged.connect(self._on_temperature_changed)
        self._on_temperature_changed(self.temperature.value())

        self.system_prompt = QLineEdit((current_system_prompt or ""))
        self.system_prompt.setPlaceholderText("Leave empty for the default prompt")
        form.addRow("System prompt", self.system_prompt)

        note = QLabel("Saved per model file into config/model_params.json.\n"
                      "Reset removes this model's entry (auto profile applies).")
        note.setObjectName("mutedLabel")
        note.setWordWrap(True)

        save = QPushButton("Save & Apply"); save.setObjectName("primaryButton")
        reset = QPushButton("Reset to family defaults")
        close = QPushButton("Close")

        buttons = QHBoxLayout()
        buttons.addWidget(reset)
        buttons.addStretch(1)
        buttons.addWidget(close)
        buttons.addWidget(save)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        line = QFrame(); line.setFrameShape(QFrame.HLine); line.setObjectName("divider")
        layout.addWidget(line)
        layout.addWidget(note)
        layout.addLayout(buttons)

        save.clicked.connect(self._save_and_apply)
        reset.clicked.connect(self._reset)
        close.clicked.connect(self.reject)

        self._applied: dict = {}
        self._reset_requested = False

    @staticmethod
    def _rng(spin: QDoubleSpinBox, lo: float, hi: float, step: float) -> None:
        spin.setRange(lo, hi)
        spin.setSingleStep(step)
        spin.setDecimals(2)

    def _collect(self) -> dict:
        data = {
            "temperature": round(self.temperature.value(), 3),
            "top_p": round(self.top_p.value(), 3),
            "min_p": round(self.min_p.value(), 3),
            "top_k": int(self.top_k.value()),
            "repeat_penalty": round(self.repeat_penalty.value(), 3),
            "max_tokens": int(self.max_tokens.value()),
        }
        sp = self.system_prompt.text().strip()
        if sp:
            data["system_prompt"] = sp
        return data

    def system_prompt_override(self) -> str:
        return self.system_prompt.text().strip()

    def _save_and_apply(self) -> None:
        data = self._collect()
        set_model_override(self.model_path, data)
        self._applied = data
        self.accept()

    def _on_temperature_changed(self, value: float) -> None:
        """When temp=0 (greedy), sampling knobs are irrelevant - grey them out."""
        is_greedy = value == 0.0
        self.top_p.setEnabled(not is_greedy)
        self.min_p.setEnabled(not is_greedy)
        self.top_k.setEnabled(not is_greedy)

    def _reset(self) -> None:
        clear_model_override(self.model_path)
        self._reset_requested = True
        self.accept()
