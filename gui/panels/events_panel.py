"""
EventsPanel - live log of storyboard state changes and condition triggers.

Storyboard events  → displayed in blue  (element name, type, new state)
Condition triggers → displayed in green (condition name, timestamp)

The log auto-scrolls to the latest entry.  "Clear" wipes the list.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

_COLOR_STORYBOARD = QColor(100, 170, 255)  # blue
_COLOR_CONDITION = QColor(100, 230, 130)  # green
_COLOR_FINISH = QColor(255, 180, 80)  # amber


class EventsPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # ── toolbar ────────────────────────────────────────────────────
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Events"))
        bar.addStretch()
        clear_btn = QPushButton("Clear")
        clear_btn.setFixedWidth(60)
        clear_btn.clicked.connect(self._clear)
        bar.addWidget(clear_btn)
        layout.addLayout(bar)

        # ── log list ───────────────────────────────────────────────────
        self._log = QListWidget()
        self._log.setFont(QFont("monospace", 8))
        self._log.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self._log.setStyleSheet("background:#111; border:none;")
        layout.addWidget(self._log)

    # ------------------------------------------------------------------
    # Public slots - connect to SimulationController signals
    # ------------------------------------------------------------------

    @pyqtSlot(float, str, str, str)
    def on_storyboard_event(self, t: float, name: str, etype: str, estate: str) -> None:
        text = f"[{t:7.3f}s]  SB  {etype:<16} {name}  →  {estate}"
        color = _COLOR_STORYBOARD
        self._append(text, color)

    @pyqtSlot(float, str)
    def on_condition_triggered(self, timestamp: float, name: str) -> None:
        text = f"[{timestamp:7.3f}s]  COND  {name}"
        color = _COLOR_CONDITION
        self._append(text, color)

    @pyqtSlot()
    def on_sim_finished(self) -> None:
        self._append("── simulation finished ──", _COLOR_FINISH)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _append(self, text: str, color: QColor) -> None:
        item = QListWidgetItem(text)
        item.setForeground(color)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        self._log.addItem(item)
        self._log.scrollToBottom()

    def clear(self) -> None:
        self._log.clear()

    # keep old private name working (Clear button)
    _clear = clear
