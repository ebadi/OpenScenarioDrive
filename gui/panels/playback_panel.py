"""
PlaybackPanel - transport controls (play/pause toggle + restart) and rewind scrubber.

Rewind note
-----------
The scrubber replays stored *positions* from the frame history buffer.
Storyboard/trigger state is not rewound - it reflects the last live state.
After a scenario finishes, the full history is still scrubbable.
Pressing Play after scrubbing resumes from the live simulation time.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ..controller.simulation_controller import SimulationController

_LABEL_PLAY = "▶  Play  [F5]"
_LABEL_PAUSE = "⏸  Pause  [F5]"
_LABEL_STEP = "⏭  Step  [F10]"


class PlaybackPanel(QWidget):
    def __init__(
        self, controller: SimulationController, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._scrubbing = False
        self._is_running = False  # tracks play/pause state for the toggle
        self._build_ui()
        controller.state_updated.connect(self._on_state_updated)
        controller.status_changed.connect(self._on_status_changed)
        controller.sim_finished.connect(self._on_sim_finished)
        controller.storyboard_event.connect(self._on_callback_triggered)
        controller.condition_triggered.connect(self._on_callback_triggered)

    def _build_ui(self) -> None:
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(8, 4, 8, 4)
        vbox.setSpacing(4)

        # ── Transport buttons ───────────────────────────────────────────
        btn_row = QHBoxLayout()

        self._play_pause_btn = QPushButton(_LABEL_PLAY)
        self._play_pause_btn.setMinimumWidth(150)
        self._play_pause_btn.clicked.connect(self._toggle_play_pause)
        btn_row.addWidget(self._play_pause_btn)

        self._step_btn = QPushButton(_LABEL_STEP)
        self._step_btn.setMinimumWidth(130)
        self._step_btn.setToolTip("Advance one simulation step (dt) while paused.")
        self._step_btn.clicked.connect(self._controller.step)
        btn_row.addWidget(self._step_btn)

        self._restart_btn = QPushButton("↺  Reload  [Ctrl+R]")
        self._restart_btn.setMinimumWidth(140)
        self._restart_btn.clicked.connect(self._controller.restart)
        btn_row.addWidget(self._restart_btn)

        self._pause_on_event_cb = QCheckBox("Pause on event")
        self._pause_on_event_cb.setChecked(True)
        self._pause_on_event_cb.setToolTip(
            "When checked, the simulation pauses automatically whenever a\n"
            "storyboard event or condition callback fires."
        )
        btn_row.addWidget(self._pause_on_event_cb)

        btn_row.addStretch()

        btn_row.addWidget(QLabel("Speed dt (s):"))
        self._dt_spin = QDoubleSpinBox()
        self._dt_spin.setRange(0.001, 1.0)
        self._dt_spin.setSingleStep(0.005)
        self._dt_spin.setValue(0.05)
        self._dt_spin.setDecimals(3)
        self._dt_spin.setFixedWidth(80)
        self._dt_spin.valueChanged.connect(self._controller.set_timestep)
        btn_row.addWidget(self._dt_spin)

        # ── Integrated simulation state (replaces separate World Properties dock) ──
        btn_row.addWidget(QLabel("│"))
        btn_row.addWidget(QLabel("obj:"))
        self._world_obj_lbl = QLabel("—")
        self._world_obj_lbl.setFixedWidth(30)
        btn_row.addWidget(self._world_obj_lbl)

        vbox.addLayout(btn_row)

        # ── Window-level keyboard shortcuts ─────────────────────────────
        sc_play = QShortcut(QKeySequence("F5"), self)
        sc_play.setContext(Qt.ShortcutContext.WindowShortcut)
        sc_play.activated.connect(self._toggle_play_pause)

        sc_step = QShortcut(QKeySequence("F10"), self)
        sc_step.setContext(Qt.ShortcutContext.WindowShortcut)
        sc_step.activated.connect(self._controller.step)

        sc_reload = QShortcut(QKeySequence("Ctrl+R"), self)
        sc_reload.setContext(Qt.ShortcutContext.WindowShortcut)
        sc_reload.activated.connect(self._controller.restart)

        # ── Rewind scrubber ─────────────────────────────────────────────
        scrub_row = QHBoxLayout()

        scrub_row.addWidget(QLabel("Rewind:"))

        self._scrub = QSlider(Qt.Orientation.Horizontal)
        self._scrub.setMinimum(0)
        self._scrub.setMaximum(0)
        self._scrub.setTracking(True)
        self._scrub.sliderPressed.connect(self._on_scrub_pressed)
        self._scrub.sliderMoved.connect(self._on_scrub_moved)
        self._scrub.sliderReleased.connect(self._on_scrub_released)
        scrub_row.addWidget(self._scrub, stretch=1)

        self._time_lbl = QLabel("t = 0.000 s")
        self._time_lbl.setFixedWidth(100)
        scrub_row.addWidget(self._time_lbl)

        vbox.addLayout(scrub_row)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Reset simulation state display (called when a new scenario is loaded)."""
        self._world_obj_lbl.setText("—")
        self._time_lbl.setText("t = 0.000 s")
        self._scrub.setMaximum(0)
        self._scrub.setValue(0)

    @pyqtSlot(float, list)
    def _on_state_updated(self, t: float, objects: list) -> None:
        self._time_lbl.setText(f"t = {t:.3f} s")
        self._world_obj_lbl.setText(str(len(objects)))
        if not self._scrubbing:
            n = len(self._controller.history)
            self._scrub.setMaximum(max(0, n - 1))
            self._scrub.setValue(n - 1)

    @pyqtSlot(str)
    def _on_status_changed(self, status: str) -> None:
        running = status == "Running"
        self._is_running = running
        self._play_pause_btn.setText(_LABEL_PAUSE if running else _LABEL_PLAY)

    @pyqtSlot()
    def _on_sim_finished(self) -> None:
        self._is_running = False
        self._play_pause_btn.setText(_LABEL_PLAY)

    @pyqtSlot()
    def _toggle_play_pause(self) -> None:
        if self._is_running:
            self._controller.pause()
        else:
            self._controller.play()

    @pyqtSlot()
    def _on_scrub_pressed(self) -> None:
        self._scrubbing = True
        self._controller.pause()

    @pyqtSlot(int)
    def _on_scrub_moved(self, value: int) -> None:
        self._controller.seek(value)

    @pyqtSlot()
    def _on_scrub_released(self) -> None:
        self._scrubbing = False
        # Leave simulation paused - user presses Play/Pause to resume

    def _on_callback_triggered(self, *_args) -> None:
        if self._pause_on_event_cb.isChecked() and self._is_running:
            self._controller.pause()
