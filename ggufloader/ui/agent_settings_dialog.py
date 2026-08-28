"""
AgentSettingsDialog - Configure agent engine from the GUI.

Exposes:
- Preset picker (research, code_review, refactor, debug, full_stack, quick_fix)
- Feature toggles (memory, knowledge, auto_commit, auto_test, etc.)
- Config editor (max_steps, max_tokens, budget, etc.)
- Agent health overview
- One-click AGENTS.md generation

Pattern from: OpenHands settings + Aider settings + Claude Code config UI.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ggufloader.config import FONT_FAMILY

logger = logging.getLogger(__name__)

# Preset definitions (mirrors presets.py)
PRESETS = [
    {
        "id": "research",
        "name": "🔍 Research",
        "desc": "Read-only exploration, no modifications",
        "max_steps": 12,
        "auto_commit": False,
        "auto_test": False,
    },
    {
        "id": "code_review",
        "name": "📝 Code Review",
        "desc": "Structured analysis with actionable feedback",
        "max_steps": 10,
        "auto_commit": False,
        "auto_test": False,
    },
    {
        "id": "refactor",
        "name": "♻️ Refactor",
        "desc": "Safe refactoring with auto-verify",
        "max_steps": 15,
        "auto_commit": True,
        "auto_test": True,
    },
    {
        "id": "debug",
        "name": "🐛 Debug",
        "desc": "Error-focused with diagnostic tools",
        "max_steps": 12,
        "auto_commit": False,
        "auto_test": True,
    },
    {
        "id": "full_stack",
        "name": "🚀 Full Stack",
        "desc": "All tools enabled, maximum flexibility",
        "max_steps": 20,
        "auto_commit": True,
        "auto_test": True,
    },
    {
        "id": "quick_fix",
        "name": "⚡ Quick Fix",
        "desc": "Minimal changes, fast turnaround",
        "max_steps": 4,
        "auto_commit": False,
        "auto_test": False,
    },
]

# Feature toggles
FEATURES = [
    ("memory", "🧠 Persistent Memory", "Remember facts across sessions"),
    ("knowledge", "📚 Knowledge Base", "Project-specific insights"),
    ("auto_commit", "💾 Auto-Commit", "Git commit after file edits"),
    ("auto_test", "🧪 Auto-Test", "Run tests after code changes"),
    ("reflection", "🔍 Reflection Loop", "Verify answers before responding"),
    ("delegation", "👷 Delegation", "Spawn read-only child agents"),
    ("retry", "🔄 Auto-Retry", "Retry failed LLM/tool calls"),
    ("checkpoints", "📋 Checkpoints", "Undo support for file changes"),
    ("context_budget", "📦 Context Budget", "Auto-compact long conversations"),
    ("file_watcher", "👁 File Watcher", "Monitor workspace for changes"),
    ("mcp", "🔌 MCP Protocol", "Connect to external tool servers"),
    ("self_improve", "📈 Self-Improvement", "Learn from corrections"),
]


class AgentSettingsDialog(QDialog):
    """Agent configuration dialog with preset picker and feature toggles."""

    settings_changed = Signal(dict)  # emitted with new config when saved

    def __init__(self, parent: QWidget | None = None,
                 current_config: dict | None = None,
                 workspace: str | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Agent Settings")
        self.setMinimumSize(580, 620)
        self._config = current_config or {}
        self._workspace = workspace
        self._preset_data = {}
        self._feature_checks: dict[str, QCheckBox] = {}
        self._build_ui()
        self._load_current_config()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Title
        title = QLabel("⚙️ Agent Settings")
        title.setObjectName("panelTitle")
        title.setFont(QFont(FONT_FAMILY, 15, QFont.Bold))
        layout.addWidget(title)

        tabs = QTabWidget()

        # --- Tab 1: Preset ---
        preset_tab = QWidget()
        preset_layout = QVBoxLayout(preset_tab)
        preset_layout.setSpacing(8)

        preset_label = QLabel("Choose a preset for the agent's behavior:")
        preset_label.setObjectName("mutedLabel")
        preset_layout.addWidget(preset_label)

        self._preset_combo = QComboBox()
        self._preset_combo.setMinimumHeight(36)
        for p in PRESETS:
            self._preset_combo.addItem(p["name"], p["id"])
        self._preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        preset_layout.addWidget(self._preset_combo)

        self._preset_desc = QLabel("")
        self._preset_desc.setObjectName("mutedLabel")
        self._preset_desc.setWordWrap(True)
        preset_layout.addWidget(self._preset_desc)

        # Preset details grid
        details_frame = QFrame()
        details_frame.setObjectName("toolCard")
        details_layout = QGridLayout(details_frame)
        details_layout.setContentsMargins(12, 10, 12, 10)
        details_layout.setSpacing(6)

        details_layout.addWidget(QLabel("Max Steps:"), 0, 0)
        self._preset_steps = QLabel("—")
        details_layout.addWidget(self._preset_steps, 0, 1)
        details_layout.addWidget(QLabel("Auto-Commit:"), 1, 0)
        self._preset_commit = QLabel("—")
        details_layout.addWidget(self._preset_commit, 1, 1)
        details_layout.addWidget(QLabel("Auto-Test:"), 2, 0)
        self._preset_test = QLabel("—")
        details_layout.addWidget(self._preset_test, 2, 1)
        preset_layout.addWidget(details_frame)
        preset_layout.addStretch()

        tabs.addTab(preset_tab, "🎯 Preset")

        # --- Tab 2: Features ---
        features_tab = QWidget()
        features_layout = QVBoxLayout(features_tab)
        features_layout.setSpacing(6)

        feat_label = QLabel("Toggle individual agent capabilities:")
        feat_label.setObjectName("mutedLabel")
        features_layout.addWidget(feat_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        feat_container = QWidget()
        feat_grid = QVBoxLayout(feat_container)
        feat_grid.setSpacing(4)

        for feat_id, name, desc in FEATURES:
            row = QFrame()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(8, 4, 8, 4)
            row_layout.setSpacing(8)

            cb = QCheckBox()
            cb.setChecked(True)
            self._feature_checks[feat_id] = cb
            row_layout.addWidget(cb)

            info = QVBoxLayout()
            info.setSpacing(0)
            info.addWidget(QLabel(name))
            desc_label = QLabel(desc)
            desc_label.setObjectName("mutedLabel")
            desc_label.setStyleSheet("font-size: 10px;")
            info.addWidget(desc_label)
            row_layout.addLayout(info)

            feat_grid.addWidget(row)

        feat_grid.addStretch()
        scroll.setWidget(feat_container)
        features_layout.addWidget(scroll)

        tabs.addTab(features_tab, "🧩 Features")

        # --- Tab 3: Config ---
        config_tab = QWidget()
        config_layout = QVBoxLayout(config_tab)
        config_layout.setSpacing(8)

        config_label = QLabel("Fine-tune agent parameters:")
        config_label.setObjectName("mutedLabel")
        config_layout.addWidget(config_label)

        grid = QGridLayout()
        grid.setSpacing(8)

        grid.addWidget(QLabel("Max Steps:"), 0, 0)
        self._max_steps_spin = QSpinBox()
        self._max_steps_spin.setRange(1, 50)
        self._max_steps_spin.setValue(8)
        grid.addWidget(self._max_steps_spin, 0, 1)

        grid.addWidget(QLabel("Max Tokens:"), 1, 0)
        self._max_tokens_spin = QSpinBox()
        self._max_tokens_spin.setRange(256, 32768)
        self._max_tokens_spin.setSingleStep(256)
        self._max_tokens_spin.setValue(2048)
        grid.addWidget(self._max_tokens_spin, 1, 1)

        grid.addWidget(QLabel("Context Budget:"), 2, 0)
        self._budget_spin = QSpinBox()
        self._budget_spin.setRange(1024, 131072)
        self._budget_spin.setSingleStep(1024)
        self._budget_spin.setValue(8192)
        grid.addWidget(self._budget_spin, 2, 1)

        grid.addWidget(QLabel("JSON Retries:"), 3, 0)
        self._json_retries_spin = QSpinBox()
        self._json_retries_spin.setRange(0, 5)
        self._json_retries_spin.setValue(2)
        grid.addWidget(self._json_retries_spin, 3, 1)

        grid.addWidget(QLabel("Temperature:"), 4, 0)
        self._temp_spin = QLineEdit("0.1")
        self._temp_spin.setMaximumWidth(100)
        grid.addWidget(self._temp_spin, 4, 1)

        config_layout.addLayout(grid)

        # Workspace
        config_layout.addWidget(QLabel("Workspace:"))
        ws_row = QHBoxLayout()
        self._workspace_input = QLineEdit(self._workspace or "")
        self._workspace_input.setPlaceholderText("Select workspace folder...")
        ws_row.addWidget(self._workspace_input)
        browse_btn = QPushButton("📁")
        browse_btn.setMaximumWidth(36)
        browse_btn.clicked.connect(self._browse_workspace)
        ws_row.addWidget(browse_btn)
        config_layout.addLayout(ws_row)

        config_layout.addStretch()
        tabs.addTab(config_tab, "🔧 Config")

        # --- Tab 4: AGENTS.md ---
        agents_tab = QWidget()
        agents_layout = QVBoxLayout(agents_tab)
        agents_layout.setSpacing(8)

        gen_label = QLabel("Auto-generate AGENTS.md from workspace:")
        gen_label.setObjectName("mutedLabel")
        agents_layout.addWidget(gen_label)

        gen_row = QHBoxLayout()
        gen_btn = QPushButton("📄 Generate AGENTS.md")
        gen_btn.setObjectName("primaryButton")
        gen_btn.clicked.connect(self._generate_agents_md)
        gen_row.addWidget(gen_btn)
        gen_row.addStretch()
        agents_layout.addLayout(gen_row)

        self._agents_preview = QTextEdit()
        self._agents_preview.setReadOnly(True)
        self._agents_preview.setPlaceholderText("Click 'Generate' to preview...")
        agents_layout.addWidget(self._agents_preview)

        tabs.addTab(agents_tab, "📄 AGENTS.md")

        layout.addWidget(tabs)

        # Bottom buttons
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)
        save_btn = QPushButton("Save Settings")
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self._save_and_accept)
        buttons.addWidget(save_btn)
        layout.addLayout(buttons)

    def _load_current_config(self) -> None:
        """Populate controls from current config."""
        # Preset
        preset_id = self._config.get("preset", "full_stack")
        for i, p in enumerate(PRESETS):
            if p["id"] == preset_id:
                self._preset_combo.setCurrentIndex(i)
                break

        # Features
        features = self._config.get("features", {})
        for feat_id, cb in self._feature_checks.items():
            if feat_id in features:
                cb.setChecked(features[feat_id])

        # Config values
        self._max_steps_spin.setValue(self._config.get("max_steps", 8))
        self._max_tokens_spin.setValue(self._config.get("max_tokens", 2048))
        self._budget_spin.setValue(self._config.get("budget_tokens", 8192))
        self._json_retries_spin.setValue(self._config.get("json_retries", 2))
        self._temp_spin.setText(str(self._config.get("temperature", 0.1)))

    def _on_preset_changed(self, index: int) -> None:
        """Update description when preset changes."""
        if 0 <= index < len(PRESETS):
            p = PRESETS[index]
            self._preset_desc.setText(p["desc"])
            self._preset_steps.setText(str(p["max_steps"]))
            self._preset_commit.setText("✅ Yes" if p["auto_commit"] else "❌ No")
            self._preset_test.setText("✅ Yes" if p["auto_test"] else "❌ No")

    def _browse_workspace(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        path = QFileDialog.getExistingDirectory(
            self, "Select Workspace", self._workspace_input.text() or str(Path.home()),
            QFileDialog.Option.ShowDirsOnly,
        )
        if path:
            self._workspace_input.setText(path)

    def _generate_agents_md(self) -> None:
        """Generate AGENTS.md and show preview."""
        workspace = self._workspace_input.text()
        if not workspace or not Path(workspace).is_dir():
            QMessageBox.warning(self, "Workspace", "Please select a valid workspace folder first.")
            return
        try:
            from ggufloader.core.agent.agents_md import AgentsMdGenerator
            gen = AgentsMdGenerator(Path(workspace))
            content = gen.generate()
            self._agents_preview.setPlainText(content)
        except Exception as e:
            self._agents_preview.setPlainText(f"Error generating AGENTS.md:\n{e}")

    def _save_and_accept(self) -> None:
        """Collect all settings and emit."""
        preset_id = self._preset_combo.currentData()
        preset = next((p for p in PRESETS if p["id"] == preset_id), PRESETS[0])

        config = {
            "preset": preset_id,
            "max_steps": self._max_steps_spin.value(),
            "max_tokens": self._max_tokens_spin.value(),
            "budget_tokens": self._budget_spin.value(),
            "json_retries": self._json_retries_spin.value(),
            "workspace": self._workspace_input.text(),
            "features": {
                feat_id: cb.isChecked()
                for feat_id, cb in self._feature_checks.items()
            },
        }
        # Apply preset overrides
        config["auto_commit"] = preset["auto_commit"]
        config["auto_test"] = preset["auto_test"]

        try:
            config["temperature"] = float(self._temp_spin.text())
        except ValueError:
            config["temperature"] = 0.1

        self.settings_changed.emit(config)
        self.accept()

    def get_config(self) -> dict:
        """Return the current config dict without closing."""
        preset_id = self._preset_combo.currentData()
        return {
            "preset": preset_id,
            "max_steps": self._max_steps_spin.value(),
            "max_tokens": self._max_tokens_spin.value(),
            "budget_tokens": self._budget_spin.value(),
            "json_retries": self._json_retries_spin.value(),
            "temperature": float(self._temp_spin.text() or "0.1"),
            "workspace": self._workspace_input.text(),
            "features": {
                feat_id: cb.isChecked()
                for feat_id, cb in self._feature_checks.items()
            },
        }
