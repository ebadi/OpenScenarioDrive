"""
ParameterEditorPanel - view and edit scenario parameters at runtime.

Shows all parameters exposed by the current scenario (via SE_GetParameterName).
The Value column is editable; "Apply and Restart" stores every value as an
override and restarts the simulation so they take effect via the pre-SE_Init
parameter declaration callback.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..controller.simulation_controller import SimulationController

_TYPE_NAMES = {1: "int", 2: "double", 3: "string", 4: "bool"}


class ParameterEditorPanel(QWidget):
    def __init__(
        self, controller: SimulationController, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._params: list[dict] = []
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # ── toolbar ────────────────────────────────────────────────────
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Scenario Parameters"))
        bar.addStretch()
        apply_btn = QPushButton("Apply and Restart")
        apply_btn.clicked.connect(self._apply_all)
        bar.addWidget(apply_btn)
        layout.addLayout(bar)

        # ── table ──────────────────────────────────────────────────────
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Name", "Type", "Value"])
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table)

        hint = QLabel("Edit the Value column, then click Apply and Restart.")
        hint.setStyleSheet("color: gray; font-size: 9px;")
        layout.addWidget(hint)

    # ------------------------------------------------------------------
    # Public API - called from main thread via signal
    # ------------------------------------------------------------------

    def reset(self) -> None:
        self._params = []
        self._table.setRowCount(0)

    @pyqtSlot(list)
    def load_parameters(self, params: list) -> None:
        self._params = params
        overrides = self._controller.get_param_overrides()
        self._table.setRowCount(len(params))
        for row, p in enumerate(params):
            name_item = QTableWidgetItem(p["name"])
            name_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self._table.setItem(row, 0, name_item)

            type_item = QTableWidgetItem(_TYPE_NAMES.get(p["type"], "?"))
            type_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self._table.setItem(row, 1, type_item)

            # Show the user's overridden value if one exists, otherwise the XOSC default
            if p["name"] in overrides:
                val_str = overrides[p["name"]][0]
            else:
                val_str = self._value_to_str(p["value"], p["type"])
            self._table.setItem(row, 2, QTableWidgetItem(val_str))

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    @staticmethod
    def _value_to_str(value, ptype: int) -> str:
        if ptype == 4:
            return "true" if value else "false"
        if ptype == 2 and isinstance(value, float):
            return f"{value:.6g}"
        return str(value)

    @pyqtSlot()
    def _apply_all(self) -> None:
        params = []
        for row, p in enumerate(self._params):
            item = self._table.item(row, 2)
            if item:
                params.append((p["name"], item.text(), p["type"]))
        if params:
            self._controller.apply_params_and_restart(params)
