"""
OnboardingWizard - Step-by-step first-launch setup UI.

Guides the user through:
1. Welcome & workspace selection
2. Agent preset selection
3. Feature toggles
4. AGENTS.md generation
5. Ready to go!

Pattern from: Claude Code first-run + VS Code welcome page.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ggufloader.config import FONT_FAMILY


STEPS = [
    {
        "title": "Welcome to GGUF Loader Agent",
        "description": "Let's set up your AI coding agent in a few simple steps.\n\nThis wizard will configure your workspace, select a preset, and generate your first AGENTS.md.",
        "icon": "🤖",
    },
    {
        "title": "Select Workspace",
        "description": "Choose the folder where your project lives.\nThe agent will read and modify files in this directory.",
        "icon": "📁",
    },
    {
        "title": "Choose Agent Preset",
        "description": "Pick a preset that matches your task.\nYou can change this later in Agent Settings.",
        "icon": "🎯",
    },
    {
        "title": "Select Features",
        "description": "Enable the agent capabilities you want.\nAdvanced users can customize these later.",
        "icon": "🧩",
    },
    {
        "title": "Generate AGENTS.md",
        "description": "Create a project context file that helps the agent understand your codebase.\nThis is optional but recommended.",
        "icon": "📄",
    },
    {
        "title": "You're All Set!",
        "description": "Your agent is configured and ready to help.\n\nTips:\n• Press Ctrl+M to toggle agent mode\n• Press Ctrl+M to toggle agent mode\n• Type /help in the chat for slash commands\n• Press Ctrl+/ for keyboard shortcuts",
        "icon": "✅",
    },
]

PRESETS = [
    ("full_stack", "🚀 Full Stack", "All tools enabled, maximum flexibility"),
    ("research", "🔍 Research", "Read-only exploration, no modifications"),
    ("code_review", "📝 Code Review", "Structured analysis with feedback"),
    ("refactor", "♻️ Refactor", "Safe refactoring with auto-verify"),
    ("debug", "🐛 Debug", "Error-focused with diagnostics"),
    ("quick_fix", "⚡ Quick Fix", "Minimal changes, fast turnaround"),
]

FEATURES = [
    ("memory", "🧠 Persistent Memory", True),
    ("knowledge", "📚 Knowledge Base", True),
    ("auto_commit", "💾 Auto-Commit", True),
    ("auto_test", "🧪 Auto-Test", True),
    ("reflection", "🔍 Reflection Loop", True),
    ("delegation", "👷 Delegation", False),
    ("retry", "🔄 Auto-Retry", True),
    ("checkpoints", "📋 Checkpoints", True),
    ("context_budget", "📦 Context Budget", True),
]


class OnboardingWizard(QDialog):
    """Step-by-step onboarding wizard."""

    setup_complete = Signal(dict)  # final config

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Agent Setup Wizard")
        self.setMinimumSize(560, 500)
        self._step = 0
        self._workspace = ""
        self._preset = "full_stack"
        self._features: dict[str, bool] = {}
        self._build_ui()
        self._update_step()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Progress indicator
        self._progress = QLabel("")
        self._progress.setObjectName("mutedLabel")
        self._progress.setAlignment(Qt.AlignCenter)
        self._progress.setStyleSheet("font-size: 10px; color: #6b7280;")
        layout.addWidget(self._progress)

        # Content stack
        self._stack = QStackedWidget()

        # Step 0: Welcome
        self._stack.addWidget(self._make_welcome_step())

        # Step 1: Workspace
        self._stack.addWidget(self._make_workspace_step())

        # Step 2: Preset
        self._stack.addWidget(self._make_preset_step())

        # Step 3: Features
        self._stack.addWidget(self._make_features_step())

        # Step 4: AGENTS.md
        self._stack.addWidget(self._make_agents_step())

        # Step 5: Done
        self._stack.addWidget(self._make_done_step())

        layout.addWidget(self._stack, 1)

        # Navigation buttons
        nav = QHBoxLayout()
        nav.addStretch()

        self._prev_btn = QPushButton("← Back")
        self._prev_btn.clicked.connect(self._prev_step)
        nav.addWidget(self._prev_btn)

        self._next_btn = QPushButton("Next →")
        self._next_btn.setObjectName("primaryButton")
        self._next_btn.clicked.connect(self._next_step)
        nav.addWidget(self._next_btn)

        self._finish_btn = QPushButton("✨ Start Using Agent")
        self._finish_btn.setObjectName("primaryButton")
        self._finish_btn.clicked.connect(self._finish)
        self._finish_btn.setVisible(False)
        nav.addWidget(self._finish_btn)

        layout.addLayout(nav)

    def _make_welcome_step(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)

        icon = QLabel("🤖")
        icon.setFont(QFont(FONT_FAMILY, 48))
        icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon)

        title = QLabel(STEPS[0]["title"])
        title.setFont(QFont(FONT_FAMILY, 18, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        desc = QLabel(STEPS[0]["description"])
        desc.setObjectName("mutedLabel")
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)

        layout.addStretch()
        return w

    def _make_workspace_step(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)

        title = QLabel(f"{STEPS[1]['icon']} {STEPS[1]['title']}")
        title.setFont(QFont(FONT_FAMILY, 14, QFont.Bold))
        layout.addWidget(title)

        desc = QLabel(STEPS[1]["description"])
        desc.setObjectName("mutedLabel")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        row = QHBoxLayout()
        self._workspace_input = QLineEdit()
        self._workspace_input.setPlaceholderText("Select your project folder...")
        self._workspace_input.setMinimumHeight(36)
        row.addWidget(self._workspace_input)

        browse = QPushButton("📁 Browse")
        browse.setObjectName("gpuInstallBtn")
        browse.clicked.connect(self._browse_workspace)
        row.addWidget(browse)
        layout.addLayout(row)

        self._workspace_status = QLabel("")
        self._workspace_status.setObjectName("mutedLabel")
        layout.addWidget(self._workspace_status)

        layout.addStretch()
        return w

    def _make_preset_step(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)

        title = QLabel(f"{STEPS[2]['icon']} {STEPS[2]['title']}")
        title.setFont(QFont(FONT_FAMILY, 14, QFont.Bold))
        layout.addWidget(title)

        desc = QLabel(STEPS[2]["description"])
        desc.setObjectName("mutedLabel")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        self._preset_combo = QComboBox()
        self._preset_combo.setMinimumHeight(36)
        for pid, name, pdesc in PRESETS:
            self._preset_combo.addItem(f"{name} — {pdesc}", pid)
        self._preset_combo.currentIndexChanged.connect(
            lambda i: setattr(self, '_preset', self._preset_combo.currentData()))
        layout.addWidget(self._preset_combo)

        layout.addStretch()
        return w

    def _make_features_step(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(8)

        title = QLabel(f"{STEPS[3]['icon']} {STEPS[3]['title']}")
        title.setFont(QFont(FONT_FAMILY, 14, QFont.Bold))
        layout.addWidget(title)

        desc = QLabel(STEPS[3]["description"])
        desc.setObjectName("mutedLabel")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        self._feature_checks: dict[str, QCheckBox] = {}
        for fid, name, default in FEATURES:
            cb = QCheckBox(name)
            cb.setChecked(default)
            self._feature_checks[fid] = cb
            layout.addWidget(cb)

        layout.addStretch()
        return w

    def _make_agents_step(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)

        title = QLabel(f"{STEPS[4]['icon']} {STEPS[4]['title']}")
        title.setFont(QFont(FONT_FAMILY, 14, QFont.Bold))
        layout.addWidget(title)

        desc = QLabel(STEPS[4]["description"])
        desc.setObjectName("mutedLabel")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        self._gen_agents_btn = QPushButton("📄 Generate AGENTS.md")
        self._gen_agents_btn.setObjectName("primaryButton")
        self._gen_agents_btn.clicked.connect(self._generate_agents_md)
        layout.addWidget(self._gen_agents_btn)

        self._agents_preview = QTextEdit()
        self._agents_preview.setReadOnly(True)
        self._agents_preview.setPlaceholderText("Click 'Generate' to preview...")
        self._agents_preview.setMaximumHeight(200)
        layout.addWidget(self._agents_preview)

        self._agents_status = QLabel("")
        self._agents_status.setObjectName("mutedLabel")
        layout.addWidget(self._agents_status)

        layout.addStretch()
        return w

    def _make_done_step(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)

        icon = QLabel(STEPS[5]["icon"])
        icon.setFont(QFont(FONT_FAMILY, 48))
        icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon)

        title = QLabel(STEPS[5]["title"])
        title.setFont(QFont(FONT_FAMILY, 18, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        desc = QLabel(STEPS[5]["description"])
        desc.setObjectName("mutedLabel")
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)

        layout.addStretch()
        return w

    def _browse_workspace(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Select Workspace", str(Path.home()),
            QFileDialog.Option.ShowDirsOnly,
        )
        if path:
            self._workspace_input.setText(path)
            self._workspace = path
            p = Path(path)
            file_count = sum(1 for _ in p.rglob("*") if _.is_file())
            self._workspace_status.setText(f"✅ {file_count} files found in {p.name}")

    def _generate_agents_md(self) -> None:
        workspace = self._workspace_input.text()
        if not workspace or not Path(workspace).is_dir():
            self._agents_status.setText("⚠️ Please select a valid workspace first.")
            return
        try:
            from ggufloader.core.agent.agents_md import AgentsMdGenerator
            gen = AgentsMdGenerator(Path(workspace))
            content = gen.generate()
            self._agents_preview.setPlainText(content)
            # Write the file
            agents_path = Path(workspace) / "AGENTS.md"
            agents_path.write_text(content, encoding="utf-8")
            self._agents_status.setText(f"✅ Generated AGENTS.md ({len(content)} chars)")
        except Exception as e:
            self._agents_status.setText(f"❌ Error: {e}")

    def _update_step(self) -> None:
        self._stack.setCurrentIndex(self._step)
        self._progress.setText(f"Step {self._step + 1} of {len(STEPS)}")
        self._prev_btn.setVisible(self._step > 0 and self._step < len(STEPS) - 1)
        self._next_btn.setVisible(self._step < len(STEPS) - 1)
        self._finish_btn.setVisible(self._step == len(STEPS) - 1)

        # Collect features on features step
        if self._step == 3:
            self._features = {fid: cb.isChecked() for fid, cb in self._feature_checks.items()}

    def _next_step(self) -> None:
        if self._step < len(STEPS) - 1:
            self._step += 1
            self._update_step()

    def _prev_step(self) -> None:
        if self._step > 0:
            self._step -= 1
            self._update_step()

    def _finish(self) -> None:
        config = {
            "workspace": self._workspace_input.text() or self._workspace,
            "preset": self._preset_combo.currentData() or self._preset,
            "features": {fid: cb.isChecked() for fid, cb in self._feature_checks.items()},
            "agents_md_generated": bool(self._agents_preview.toPlainText().strip()),
        }
        self.setup_complete.emit(config)
        self.accept()
