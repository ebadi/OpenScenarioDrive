"""
ObjectInspectorPanel - actor list + live property editor.

Left pane: QListWidget of all active scenario objects.
Right pane: QFormLayout for editing the selected object's position.
The "Apply" button sends the new position to the controller, which
forwards it to the simulation worker thread.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..controller.simulation_controller import SimulationController
from ..controller.simulation_worker import ObjectSnapshot


def _spin(lo: float, hi: float, decimals: int = 3, step: float = 0.1) -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(decimals)
    s.setSingleStep(step)
    return s


class ObjectInspectorPanel(QWidget):
    object_selected = pyqtSignal(str)  # emits the object name when a row is clicked
    object_road_selected = pyqtSignal(int)  # emits the road_id of the selected object

    def __init__(
        self, controller: SimulationController, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._snapshots: list[ObjectSnapshot] = []
        self._selected_id: int | None = None
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        splitter = QSplitter(Qt.Orientation.Vertical, self)

        # ── Actor list ──────────────────────────────────────────────────
        self._list = QListWidget()
        self._list.setMouseTracking(True)  # required for itemEntered to fire
        self._list.currentRowChanged.connect(self._on_row_changed)
        splitter.addWidget(self._list)

        # ── Property editor ─────────────────────────────────────────────
        editor = QGroupBox("Position")
        form = QFormLayout(editor)

        self._x_spin = _spin(-10_000, 10_000)
        self._y_spin = _spin(-10_000, 10_000)
        self._z_spin = _spin(-100, 1_000)
        self._h_spin = _spin(-3.15, 3.15, decimals=4, step=0.01)
        self._speed_lbl = QLabel("—")
        self._lane_lbl = QLabel("—")
        self._road_lbl = QLabel("—")
        self._s_lbl = QLabel("—")

        form.addRow("x (m):", self._x_spin)
        form.addRow("y (m):", self._y_spin)
        form.addRow("z (m):", self._z_spin)
        form.addRow("heading (rad):", self._h_spin)
        form.addRow("speed (m/s):", self._speed_lbl)
        form.addRow("road id:", self._road_lbl)
        form.addRow("lane id:", self._lane_lbl)
        form.addRow("s (m):", self._s_lbl)

        apply_btn = QPushButton("Apply position")
        apply_btn.clicked.connect(self._apply_position)
        form.addRow(apply_btn)

        splitter.addWidget(editor)

        # ── Dynamics (read-only) ─────────────────────────────────────────
        dynamics = QGroupBox("Dynamics")
        dform = QFormLayout(dynamics)

        self._accel_lbl = QLabel("—")
        self._vel_lbl = QLabel("—")
        self._yawrate_lbl = QLabel("—")
        self._odometer_lbl = QLabel("—")
        self._collide_lbl = QLabel("—")
        self._type_lbl = QLabel("—")
        self._model_lbl = QLabel("—")
        self._model_lbl.setWordWrap(True)

        dform.addRow("accel (m/s²):", self._accel_lbl)
        dform.addRow("vel xyz (m/s):", self._vel_lbl)
        dform.addRow("yaw rate (r/s):", self._yawrate_lbl)
        dform.addRow("odometer (m):", self._odometer_lbl)
        dform.addRow("collisions:", self._collide_lbl)
        dform.addRow("type:", self._type_lbl)
        dform.addRow("model:", self._model_lbl)

        splitter.addWidget(dynamics)
        splitter.setSizes([200, 300, 180])
        layout.addWidget(splitter)

    # ------------------------------------------------------------------
    # Public update API - called from the main thread via signal
    # ------------------------------------------------------------------

    def reset(self) -> None:
        self._snapshots = []
        self._selected_id = None
        self._list.blockSignals(True)
        self._list.clear()
        self._list.blockSignals(False)
        for w in (self._x_spin, self._y_spin, self._z_spin, self._h_spin):
            w.blockSignals(True)
            w.setValue(0.0)
            w.blockSignals(False)
        for lbl in (
            self._speed_lbl,
            self._road_lbl,
            self._lane_lbl,
            self._s_lbl,
            self._accel_lbl,
            self._vel_lbl,
            self._yawrate_lbl,
            self._odometer_lbl,
            self._collide_lbl,
            self._type_lbl,
            self._model_lbl,
        ):
            lbl.setText("—")

    def update_objects(self, snapshots: list[ObjectSnapshot]) -> None:
        self._snapshots = snapshots

        # Update items IN-PLACE so Qt's tooltip timer is not reset each frame.
        # Clearing and re-adding items every 50 ms destroys them before the
        # ~500 ms tooltip delay can fire - that was the tooltip bug.
        self._list.blockSignals(True)

        for i, snap in enumerate(snapshots):
            if i < self._list.count():
                item = self._list.item(i)
            else:
                item = QListWidgetItem()
                self._list.addItem(item)
            item.setText(f"[{snap.id}]  {snap.name}")
            item.setData(Qt.ItemDataRole.UserRole, snap.id)
            item.setToolTip(self._make_tooltip(snap))

        # Remove surplus rows (objects that left the scenario)
        while self._list.count() > len(snapshots):
            self._list.takeItem(self._list.count() - 1)

        self._list.blockSignals(False)

        # Auto-select Ego (or first object) on first update after a reset
        if self._selected_id is None and snapshots:
            ego_index = next((i for i, s in enumerate(snapshots) if s.name == "Ego"), 0)
            self._list.setCurrentRow(ego_index)
            return

        # Refresh position editor for the currently selected object
        if self._selected_id is not None:
            for snap in snapshots:
                if snap.id == self._selected_id:
                    self._populate_editor(snap)
                    break

    def select_by_id(self, obj_id: int) -> None:
        """Select the list row whose object id matches *obj_id*."""
        for i, snap in enumerate(self._snapshots):
            if snap.id == obj_id:
                self._list.setCurrentRow(i)
                return

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    @staticmethod
    def _make_tooltip(snap: ObjectSnapshot) -> str:
        return (
            f"id:         {snap.id}\n"
            f"x:          {snap.x:.3f} m\n"
            f"y:          {snap.y:.3f} m\n"
            f"z:          {snap.z:.3f} m\n"
            f"heading:    {snap.h:.4f} rad  ({snap.h * 57.296:.1f}°)\n"
            f"speed:      {snap.speed:.2f} m/s  ({snap.speed * 3.6:.1f} km/h)\n"
            f"accel:      {snap.acceleration:.3f} m/s²\n"
            f"vel xyz:    {snap.vx:.2f}, {snap.vy:.2f}, {snap.vz:.2f} m/s\n"
            f"yaw rate:   {snap.yaw_rate:.4f} rad/s\n"
            f"odometer:   {snap.odometer:.1f} m\n"
            f"collisions: {snap.collision_count}\n"
            f"road id:    {snap.road_id}\n"
            f"lane id:    {snap.lane_id}\n"
            f"s:          {snap.s:.2f} m\n"
            f"size:       {snap.length:.1f} × {snap.width:.1f} m\n"
            f"type:       {snap.type_name}\n"
            f"model:      {snap.model_filename}"
        )

    @pyqtSlot(int)
    def _on_row_changed(self, row: int) -> None:
        if row < 0 or row >= len(self._snapshots):
            self._selected_id = None
            return
        snap = self._snapshots[row]
        self._selected_id = snap.id
        self._populate_editor(snap)
        self.object_selected.emit(snap.name)
        self.object_road_selected.emit(snap.road_id)

    def _populate_editor(self, snap: ObjectSnapshot) -> None:
        for w in (self._x_spin, self._y_spin, self._z_spin, self._h_spin):
            w.blockSignals(True)
        self._x_spin.setValue(snap.x)
        self._y_spin.setValue(snap.y)
        self._z_spin.setValue(snap.z)
        self._h_spin.setValue(snap.h)
        for w in (self._x_spin, self._y_spin, self._z_spin, self._h_spin):
            w.blockSignals(False)

        self._speed_lbl.setText(f"{snap.speed:.2f}")
        self._road_lbl.setText(str(snap.road_id))
        self._lane_lbl.setText(str(snap.lane_id))
        self._s_lbl.setText(f"{snap.s:.2f}")

        self._accel_lbl.setText(f"{snap.acceleration:.3f}")
        self._vel_lbl.setText(f"{snap.vx:.2f}, {snap.vy:.2f}, {snap.vz:.2f}")
        self._yawrate_lbl.setText(f"{snap.yaw_rate:.4f}")
        self._odometer_lbl.setText(f"{snap.odometer:.1f}")
        self._collide_lbl.setText(str(snap.collision_count))
        self._type_lbl.setText(snap.type_name or "—")
        model = snap.model_filename
        self._model_lbl.setText(model.split("/")[-1] if model else "—")

    @pyqtSlot()
    def _apply_position(self) -> None:
        if self._selected_id is None:
            return
        self._controller.report_object_position(
            self._selected_id,
            x=self._x_spin.value(),
            y=self._y_spin.value(),
            z=self._z_spin.value(),
            h=self._h_spin.value(),
            p=0.0,
            r=0.0,
        )
