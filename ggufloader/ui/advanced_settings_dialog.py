"""Advanced Settings dialog.

Consolidates GPU layer control, model sampling parameters, and LocalDocs
RAG configuration into a single dialog, keeping the main sidebar clean
and focused on model loading and chat sessions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QFrame, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout,
    QWidget, QFileDialog,
)

from ggufloader.config import DEFAULT_CONTEXT_SIZES, FONT_FAMILY


class AdvancedSettingsDialog(QDialog):
    """Consolidated advanced settings: GPU, model params, and RAG."""

    # Signals emitted when settings change
    gpu_layers_changed = Signal(int)
    params_requested = Signal()  # open the per-model params dialog
    rag_toggled = Signal(bool)
    rag_scan_requested = Signal()

    def __init__(self, parent: QWidget, current_config: dict) -> None:
        super().__init__(parent)
        self.setWindowTitle("Advanced Settings")
        self.setMinimumSize(520, 600)
        self._config = current_config
        self._build_ui()
        self._load_values()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # ---- GPU Configuration ----
        gpu_group = QGroupBox("GPU Configuration")
        gpu_layout = QFormLayout(gpu_group)
        gpu_layout.setSpacing(10)

        self.gpu_layers_spin = QSpinBox()
        self.gpu_layers_spin.setRange(0, 128)
        self.gpu_layers_spin.setValue(128)
        self.gpu_layers_spin.setSpecialValueText("Auto (all layers)")
        self.gpu_layers_spin.setToolTip(
            "Number of transformer layers to offload to GPU.\n"
            "0 = CPU only, Auto = offload all layers.\n"
            "Lower values use less VRAM but are slower."
        )
        self.gpu_layers_spin.setMinimumHeight(32)
        gpu_layout.addRow("GPU Layers:", self.gpu_layers_spin)

        self.memory_estimate_label = QLabel("")
        self.memory_estimate_label.setWordWrap(True)
        self.memory_estimate_label.setObjectName("mutedLabel")
        gpu_layout.addRow("Memory:", self.memory_estimate_label)

        layout.addWidget(gpu_group)

        # ---- Model Parameters ----
        params_group = QGroupBox("Model Parameters")
        params_layout = QVBoxLayout(params_group)
        params_layout.setSpacing(8)

        params_form = QFormLayout()
        params_form.setSpacing(8)

        self.temperature = QDoubleSpinBox()
        self._rng(self.temperature, 0.0, 2.0, 0.05)
        self.temperature.setToolTip("Higher = more creative, lower = more focused")
        params_form.addRow("Temperature:", self.temperature)

        self.top_p = QDoubleSpinBox()
        self._rng(self.top_p, 0.05, 1.0, 0.01)
        self.top_p.setToolTip("Nucleus sampling threshold")
        params_form.addRow("Top-P:", self.top_p)

        self.min_p = QDoubleSpinBox()
        self._rng(self.min_p, 0.0, 1.0, 0.01)
        self.min_p.setToolTip("Minimum probability threshold")
        params_form.addRow("Min-P:", self.min_p)

        self.top_k = QSpinBox()
        self.top_k.setRange(0, 200)
        self.top_k.setToolTip("Top-K sampling: consider only K most likely tokens")
        params_form.addRow("Top-K:", self.top_k)

        self.repeat_penalty = QDoubleSpinBox()
        self._rng(self.repeat_penalty, 0.5, 2.0, 0.01)
        self.repeat_penalty.setToolTip("Penalize repeated tokens (> 1.0 = penalize)")
        params_form.addRow("Repeat Penalty:", self.repeat_penalty)

        self.max_tokens = QSpinBox()
        self.max_tokens.setRange(64, 65536)
        self.max_tokens.setSingleStep(256)
        self.max_tokens.setToolTip("Maximum tokens to generate per response")
        params_form.addRow("Max Tokens:", self.max_tokens)

        params_layout.addLayout(params_form)

        # Greedy mode indicator
        self.greedy_label = QLabel("⚡ Greedy mode (temp=0): sampling params ignored")
        self.greedy_label.setObjectName("mutedLabel")
        self.greedy_label.setVisible(False)
        params_layout.addWidget(self.greedy_label)

        self.temperature.valueChanged.connect(self._on_temperature_changed)

        # Per-model params button
        params_btn_row = QHBoxLayout()
        self.params_btn = QPushButton("⚙ Per-Model Params...")
        self.params_btn.setToolTip("Open the per-model parameter override dialog")
        self.params_btn.setMinimumHeight(34)
        self.params_btn.clicked.connect(self.params_requested.emit)
        params_btn_row.addWidget(self.params_btn, 1)

        self.reset_params_btn = QPushButton("Reset to Defaults")
        self.reset_params_btn.setMinimumHeight(34)
        self.reset_params_btn.clicked.connect(self._reset_params)
        params_btn_row.addWidget(self.reset_params_btn)
        params_layout.addLayout(params_btn_row)

        layout.addWidget(params_group)

        # ---- LocalDocs (RAG) ----
        rag_group = QGroupBox("LocalDocs (RAG)")
        rag_layout = QVBoxLayout(rag_group)
        rag_layout.setSpacing(8)

        rag_toggle_row = QHBoxLayout()
        self.rag_toggle = QPushButton("📚 LocalDocs: OFF")
        self.rag_toggle.setObjectName("gpuToggle")
        self.rag_toggle.setCheckable(True)
        self.rag_toggle.setMinimumHeight(34)
        self.rag_toggle.setToolTip("Enable RAG: inject relevant document chunks into chat prompts")
        self.rag_toggle.toggled.connect(self._on_rag_toggled)
        rag_toggle_row.addWidget(self.rag_toggle, 1)
        rag_layout.addLayout(rag_toggle_row)

        rag_folder_row = QHBoxLayout()
        self.rag_folder_field = QLineEdit()
        self.rag_folder_field.setPlaceholderText("Document folder path...")
        self.rag_folder_field.setMinimumHeight(30)
        rag_folder_row.addWidget(self.rag_folder_field, 1)
        self.rag_browse_btn = QPushButton("📁")
        self.rag_browse_btn.setMaximumWidth(36)
        self.rag_browse_btn.setMinimumHeight(30)
        self.rag_browse_btn.setToolTip("Browse for document folder")
        self.rag_browse_btn.clicked.connect(self._browse_rag_folder)
        rag_folder_row.addWidget(self.rag_browse_btn)
        rag_layout.addLayout(rag_folder_row)

        rag_action_row = QHBoxLayout()
        self.rag_scan_btn = QPushButton("🔄 Scan & Index")
        self.rag_scan_btn.setMinimumHeight(32)
        self.rag_scan_btn.setEnabled(False)
        self.rag_scan_btn.setToolTip("Scan the folder and index documents for RAG")
        self.rag_scan_btn.clicked.connect(self.rag_scan_requested.emit)
        rag_action_row.addWidget(self.rag_scan_btn, 1)
        rag_layout.addLayout(rag_action_row)

        self.rag_status = QLabel("")
        self.rag_status.setObjectName("mutedLabel")
        self.rag_status.setWordWrap(True)
        rag_layout.addWidget(self.rag_status)

        layout.addWidget(rag_group)

        # ---- Bottom buttons ----
        layout.addStretch()
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setMinimumHeight(36)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    @staticmethod
    def _rng(spin: QDoubleSpinBox, lo: float, hi: float, step: float) -> None:
        spin.setRange(lo, hi)
        spin.setSingleStep(step)
        spin.setDecimals(2)

    # ------------------------------------------------------------------
    # Value loading / saving
    # ------------------------------------------------------------------

    def _load_values(self) -> None:
        """Load current values from the config dict."""
        self.temperature.setValue(float(self._config.get("temperature", 0.2)))
        self.top_p.setValue(float(self._config.get("top_p", 0.9)))
        self.min_p.setValue(float(self._config.get("min_p", 0.0)))
        self.top_k.setValue(int(self._config.get("top_k", 80)))
        self.repeat_penalty.setValue(float(self._config.get("repeat_penalty", 1.05)))
        self.max_tokens.setValue(int(self._config.get("max_tokens", 16384)))

        # GPU layers
        gpu_layers = self._config.get("gpu_layers", 128)
        self.gpu_layers_spin.setValue(gpu_layers)

        # RAG
        rag_enabled = self._config.get("rag_enabled", False)
        self.rag_toggle.setChecked(rag_enabled)
        rag_folder = self._config.get("rag_folder", "")
        self.rag_folder_field.setText(rag_folder)

    def get_values(self) -> dict:
        """Collect all current values into a dict."""
        return {
            "temperature": round(self.temperature.value(), 3),
            "top_p": round(self.top_p.value(), 3),
            "min_p": round(self.min_p.value(), 3),
            "top_k": int(self.top_k.value()),
            "repeat_penalty": round(self.repeat_penalty.value(), 3),
            "max_tokens": int(self.max_tokens.value()),
            "gpu_layers": self.gpu_layers_spin.value(),
            "rag_enabled": self.rag_toggle.isChecked(),
            "rag_folder": self.rag_folder_field.text().strip(),
        }

    def _reset_params(self) -> None:
        """Reset sampling params to sensible defaults."""
        self.temperature.setValue(0.2)
        self.top_p.setValue(0.9)
        self.min_p.setValue(0.0)
        self.top_k.setValue(80)
        self.repeat_penalty.setValue(1.05)
        self.max_tokens.setValue(16384)

    def _on_temperature_changed(self, value: float) -> None:
        """When temp=0 (greedy), sampling knobs are irrelevant."""
        is_greedy = value == 0.0
        self.top_p.setEnabled(not is_greedy)
        self.min_p.setEnabled(not is_greedy)
        self.top_k.setEnabled(not is_greedy)
        self.greedy_label.setVisible(is_greedy)

    def _on_rag_toggled(self, enabled: bool) -> None:
        self.rag_toggle.setText(f"📚 LocalDocs: {'ON' if enabled else 'OFF'}")
        self.rag_scan_btn.setEnabled(enabled and bool(self.rag_folder_field.text().strip()))
        self.rag_toggled.emit(enabled)

    def _browse_rag_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Select Document Folder",
            self.rag_folder_field.text() or "",
            QFileDialog.Option.ShowDirsOnly,
        )
        if folder:
            self.rag_folder_field.setText(folder)
            self.rag_scan_btn.setEnabled(self.rag_toggle.isChecked())

    # ------------------------------------------------------------------
    # External setters (called by MainWindow)
    # ------------------------------------------------------------------

    def set_memory_estimate(self, estimate: dict) -> None:
        """Show memory estimate."""
        if not estimate:
            self.memory_estimate_label.setText("")
            return
        model_gb = estimate.get("model_gb", 0)
        kv_gb = estimate.get("kv_gb", 0)
        total_gb = estimate.get("total_gb", 0)
        layers = estimate.get("layers")
        quant = estimate.get("quant", "")
        ram_gb = estimate.get("ram_gb", 0)
        vram_gb = estimate.get("vram_gb", 0)
        fits_ram = estimate.get("fits_ram", True)
        fits_vram = estimate.get("fits_vram", False)

        parts = [f"Model: {model_gb:.1f} GB + KV: {kv_gb:.1f} GB = {total_gb:.1f} GB total"]
        if layers:
            parts.append(f"Layers: {layers}")
        if quant:
            parts.append(f"Quant: {quant}")
        if not fits_ram and ram_gb > 0:
            parts.append(f"⚠️ Exceeds available RAM ({ram_gb:.0f} GB)")
        elif fits_vram and vram_gb > 0:
            parts.append(f"✅ Fits in GPU VRAM ({vram_gb:.0f} GB)")
        elif ram_gb > 0:
            parts.append(f"✅ Fits in system RAM ({ram_gb:.0f} GB)")

        self.memory_estimate_label.setText("\n".join(parts))

    def set_rag_status(self, text: str) -> None:
        self.rag_status.setText(text)

    def set_gpu_layers_max(self, max_layers: int) -> None:
        try:
            self.gpu_layers_spin.setMaximum(max(1, int(max_layers)))
        except Exception:  # noqa: BLE001
            pass

    def get_gpu_layers(self) -> int:
        try:
            v = int(self.gpu_layers_spin.value())
            return -1 if v >= self.gpu_layers_spin.maximum() else v
        except Exception:  # noqa: BLE001
            return -1

    def get_rag_folder(self) -> str:
        return self.rag_folder_field.text().strip()

    def set_rag_folder(self, path: str) -> None:
        self.rag_folder_field.setText(path)
        self.rag_scan_btn.setEnabled(
            self.rag_toggle.isChecked() and bool(path.strip())
        )
