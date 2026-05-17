"""
WorldPanel - scenario / road metadata and live simulation state.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QFormLayout, QGroupBox, QLabel, QVBoxLayout, QWidget


class WorldPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        box = QGroupBox("Simulation State")
        form = QFormLayout(box)

        self._time_lbl = QLabel("—")
        self._obj_count_lbl = QLabel("—")

        form.addRow("Sim time (s):", self._time_lbl)
        form.addRow("Active objects:", self._obj_count_lbl)

        layout.addWidget(box)
        layout.addStretch()

    # ------------------------------------------------------------------
    # Public update API - called from main thread via signal
    # ------------------------------------------------------------------

    def reset(self) -> None:
        self._time_lbl.setText("—")
        self._obj_count_lbl.setText("—")

    def update_time(self, t: float) -> None:
        self._time_lbl.setText(f"{t:.3f}")

    def update_object_count(self, n: int) -> None:
        self._obj_count_lbl.setText(str(n))
