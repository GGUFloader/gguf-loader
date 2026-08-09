"""
Theme - Dark/light application theming.

A single token set drives both themes. The QSS template below uses
``$name`` markers that are substituted at build time, so dark and light
share one structure and can never drift apart.

Palette direction ("Midnight & Amber"):
    cool slate-charcoal surfaces paired with a warm amber accent.
    Amber is reserved for primary actions, active states and focus
    rings so it reads as intentional, not decorative.
"""

from __future__ import annotations

DARK_TOKENS = {
    "bg": "#0b0e14",
    "surface": "#12161f",
    "elevated": "#1a202c",
    "elevatedHover": "#202837",
    "pressedBg": "#141922",
    "disabledBg": "#171c26",
    "border": "#242c3a",
    "borderStrong": "#2f3a4b",
    "text": "#e7ebf2",
    "textSec": "#a3adbf",
    "textMuted": "#677184",
    "accent": "#e8a33d",
    "accentHover": "#f0b458",
    "accentPressed": "#cc8a27",
    "accentSoft": "rgba(232, 163, 61, 0.16)",
    "accentBorder": "rgba(232, 163, 61, 0.35)",
    "accentSelection": "rgba(255, 255, 255, 0.30)",
    "onAccent": "#191204",
    "success": "#3fbf8a",
    "danger": "#e5544b",
    "dangerHover": "#d14a42",
    "warn": "#e8a33d",
}

LIGHT_TOKENS = {
    "bg": "#f4f5f8",
    "surface": "#ffffff",
    "elevated": "#ffffff",
    "elevatedHover": "#f0f2f7",
    "pressedBg": "#eceef4",
    "disabledBg": "#f0f1f4",
    "border": "#e1e5ee",
    "borderStrong": "#c9d0dd",
    "text": "#1b2333",
    "textSec": "#5a6474",
    "textMuted": "#8a93a4",
    "accent": "#a97014",
    "accentHover": "#8f5e0e",
    "accentPressed": "#7a4f0c",
    "accentSoft": "rgba(169, 112, 20, 0.14)",
    "accentBorder": "rgba(169, 112, 20, 0.30)",
    "accentSelection": "rgba(0, 0, 0, 0.22)",
    "onAccent": "#ffffff",
    "success": "#1f9d63",
    "danger": "#d6453d",
    "dangerHover": "#b93b34",
    "warn": "#b97710",
}

QSS_TEMPLATE = """
/* Defaults first: plain widgets must not leak the (light) system palette.
   More specific rules below override these. */
QWidget { background: transparent; }
QFrame { background: transparent; }
QMainWindow, QDialog { background-color: $bg; color: $text; }
QWidget#chatRoot { background-color: $bg; }

/* ---- panels ---- */
QFrame#sidePanel { background-color: $surface; border: none; }
QFrame#headerBar { background-color: $surface; border: none;
                   border-bottom: 1px solid $border; }
QFrame#inputFrame { background-color: $surface; border: 1px solid $border;
                    border-radius: 10px; }

/* ---- labels ---- */
QLabel { color: $text; background: transparent; }
QLabel#panelTitle { font-size: 15px; font-weight: bold; color: $text; }
QLabel#brandTitle { font-size: 16px; font-weight: bold; color: $accent; }
QLabel#brandSub { color: $textMuted; font-size: 10px; }
QLabel#sectionEyebrow { color: $accent; font-size: 10px; font-weight: bold; }
QLabel#mutedLabel { color: $textSec; }
QLabel#aboutLabel { color: $textMuted; font-size: 11px; }
QLabel#systemMessage { color: $textMuted; font-size: 11px; font-style: italic;
                       padding: 5px; background: transparent; }
QLabel#sizePill { background-color: $elevated; border: 1px solid $border;
                  border-radius: 4px; padding: 2px 6px; color: $text; }
QLabel#statusLabel { color: $textSec; }
QLabel#statusLabel[state="ok"] { color: $success; }
QLabel#statusLabel[state="err"] { color: $danger; }
QLabel#statusChip { background-color: $elevated; border: 1px solid $border;
                    border-radius: 12px; padding: 4px 12px;
                    color: $textSec; font-size: 11px; }
QLabel#statusChip[state="ok"] { color: $success; }
QLabel#statusChip[state="err"] { color: $danger; }
QLabel#agentStatus { color: $textMuted; font-size: 10px; }
QLabel#agentStatus[state="ok"] { color: $success; }
QLabel#agentStatus[state="busy"] { color: $warn; }
QLabel#agentStatus[state="err"] { color: $danger; }

/* ---- agent transcript ---- */
QLabel#stepChip { background-color: $elevated; border: 1px solid $border;
                  border-radius: 10px; padding: 3px 12px; color: $textSec;
                  font-size: 11px; }
QFrame#toolCard { background-color: $elevated; border: 1px solid $border;
                  border-radius: 10px; }
QFrame#approvalCard { background-color: $elevated;
                      border: 1px solid $accentBorder; border-radius: 10px; }
QLabel#toolCardTitle { color: $text; font-size: 12px; font-weight: bold; }
QLabel#toolCardSub { color: $textSec; font-size: 11px; }
QLabel#approvalTitle { color: $warn; font-size: 12px; font-weight: bold; }
QLabel#monoText { font-family: Consolas, "Courier New", monospace;
                  color: $textSec; font-size: 11px; background-color: $bg;
                  border-radius: 6px; padding: 6px 8px; }

/* ---- buttons ---- */
QPushButton { background-color: $elevated; color: $textSec;
              border: 1px solid $border; border-radius: 8px;
              padding: 8px 14px; font-size: 12px; }
QPushButton:hover { background-color: $elevatedHover; color: $text;
                    border-color: $borderStrong; }
QPushButton:pressed { background-color: $pressedBg; }
QPushButton:disabled { color: $textMuted; background-color: $disabledBg;
                       border-color: $border; }
QPushButton#primaryButton { background-color: $accent; color: $onAccent;
                            border: none; font-weight: bold; }
QPushButton#primaryButton:hover { background-color: $accentHover; }
QPushButton#primaryButton:pressed { background-color: $accentPressed; }
QPushButton#primaryButton:disabled { background-color: $disabledBg;
                                     color: $textMuted; }
QPushButton#agentToggle { border-radius: 15px; padding: 8px 14px; }
QPushButton#agentToggle:checked { background-color: $accent; color: $onAccent;
                                  border: none; font-weight: bold; }
QPushButton#gpuToggle:checked { background-color: $accent; color: $onAccent;
                                border: none; font-weight: bold; }
QPushButton#gpuToggle:checked:hover { background-color: $accentHover; }
QPushButton#gpuInstallBtn[state="ok"] { background-color: $accentSoft;
    color: $success; border-color: $success; font-weight: bold; }
QPushButton#gpuInstallBtn[state="ok"]:hover { background-color: $accentSoft;
    color: $success; border-color: $success; }
QPushButton#dangerButton { background-color: $danger; color: #ffffff;
                           border: none; font-weight: bold; }
QPushButton#dangerButton:hover { background-color: $dangerHover; }
QPushButton#dangerButton:pressed { background-color: $danger; }
QPushButton#dangerButton:disabled { background-color: $disabledBg;
                                     color: $textMuted; }

/* ---- inputs ---- */
QComboBox, QLineEdit, QTextEdit { background-color: $elevated; color: $text;
    border: 1px solid $border; border-radius: 8px; padding: 7px 10px;
    selection-background-color: $accentSoft; }
QComboBox:hover, QLineEdit:hover, QTextEdit:hover { border-color: $borderStrong; }
QComboBox:focus, QLineEdit:focus, QTextEdit:focus { border-color: $accent; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox QAbstractItemView { background-color: $elevated; color: $text;
    border: 1px solid $border; selection-background-color: $accentSoft;
    selection-color: $text; outline: none; }

/* ---- checkboxes / sliders / progress ---- */
QCheckBox { color: $textSec; spacing: 8px; }
QCheckBox:hover { color: $text; }
QSlider::groove:horizontal { height: 4px; background: $border; border-radius: 2px; }
QSlider::handle:horizontal { width: 14px; height: 14px; margin: -5px 0;
    border-radius: 7px; background: $accent; border: 2px solid $bg; }
QSlider::handle:horizontal:hover { background: $accentHover; }
QProgressBar { background-color: $elevated; border: 1px solid $border;
               border-radius: 5px; color: $textSec; font-size: 10px; }
QProgressBar::chunk { background-color: $accent; border-radius: 4px; }

/* ---- scroll areas / bars ---- */
QScrollArea { border: none; background: transparent; }
QScrollArea QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: $borderStrong; border-radius: 5px;
                              min-height: 24px; }
QScrollBar::handle:vertical:hover { background: $textMuted; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: $borderStrong; border-radius: 5px;
                                min-width: 24px; }
QScrollBar::handle:horizontal:hover { background: $textMuted; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

/* ---- chrome ---- */
QSplitter { background-color: $bg; }
QSplitter::handle { background-color: $border; }
QToolTip { background-color: $elevated; color: $text;
           border: 1px solid $borderStrong; padding: 4px 8px; }
QMenuBar { background-color: $surface; color: $textSec; }
QMenuBar::item { padding: 6px 12px; background: transparent; border-radius: 6px; }
QMenuBar::item:selected { background-color: $elevated; color: $text; }
QMenuBar::item:pressed { background-color: $elevated; color: $text; }
QMenu { background-color: $surface; color: $text; border: 1px solid $border;
        padding: 4px; }
QMenu::item { padding: 6px 26px 6px 18px; border-radius: 4px; }
QMenu::item:selected { background-color: $accentSoft; color: $text; }
QMenu::item:disabled { color: $textMuted; }
QMenu::separator { height: 1px; background: $border; margin: 4px 10px; }
QStatusBar { background-color: $surface; color: $textMuted; }
"""


def build_stylesheet(tokens: dict) -> str:
    """Substitute ``$name`` markers with the given token values.

    Longer names are replaced first: ``$accentSoft`` must be handled
    before ``$accent``, otherwise ``$accentSoft`` becomes ``#e8a33dSoft``.
    """
    qss = QSS_TEMPLATE
    for name in sorted(tokens, key=len, reverse=True):
        qss = qss.replace(f"${name}", tokens[name])
    return qss


DARK_STYLESHEET = build_stylesheet(DARK_TOKENS)
LIGHT_STYLESHEET = build_stylesheet(LIGHT_TOKENS)


class ThemeMixin:
    """Mixin providing :meth:`apply_styles` for dark/light mode.

    Exposes ``self.tokens`` (the active palette) so widgets can pick
    stateful colors that match the current theme.
    """

    def apply_styles(self) -> None:
        is_dark = getattr(self, "is_dark_mode", False)
        self.tokens = DARK_TOKENS if is_dark else LIGHT_TOKENS
        stylesheet = DARK_STYLESHEET if is_dark else LIGHT_STYLESHEET
        self.setStyleSheet(stylesheet)
