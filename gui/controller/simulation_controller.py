"""
SimulationController - mediates between the GUI panels and SimulationWorker.

Lives on the main thread. Owns the worker thread and translates high-level
GUI actions (play/pause/restart/seek) into thread-safe worker commands.
"""

from __future__ import annotations

from collections import deque
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from .simulation_worker import SimulationWorker

# Maximum frames kept in the rewind buffer (20 fps × 120 s = 2400 frames)
_HISTORY_MAX = 2400


class SimulationController(QObject):
    """
    Signals
    -------
    state_updated(sim_time, objects)   - every step (also during seek playback)
    storyboard_event(t, name, type, state)
    condition_triggered(timestamp, name)
    road_network_ready(lane_strips, signs)
    scenario_loading()                 - fired before a new scenario starts
    error_occurred(message)
    status_changed(status_string)
    sim_finished()
    """

    state_updated = pyqtSignal(float, list)
    storyboard_event = pyqtSignal(float, str, str, str)
    condition_triggered = pyqtSignal(float, str)
    road_network_ready = pyqtSignal(list, list)
    odr_filename_ready = pyqtSignal(str)
    parameters_ready = pyqtSignal(list)
    scenario_loading = pyqtSignal()
    road_load_warning = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    status_changed = pyqtSignal(str)
    sim_finished = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._worker: SimulationWorker | None = None
        self._lib_dir: str = ""
        self._resource_root: str = ""
        self._current_scenario: str = ""
        self._history: deque = deque(maxlen=_HISTORY_MAX)
        # name → (value_str, ptype) - persists across restarts of the same scenario
        self._param_overrides: dict = {}

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_environment(self, lib_dir: str, resource_root: str) -> None:
        self._lib_dir = lib_dir
        self._resource_root = resource_root

    @property
    def history(self) -> deque:
        return self._history

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def load_scenario(self, xosc_path: str) -> None:
        """Stop any running simulation and start a new one from xosc_path."""
        self._stop_worker()
        if not Path(xosc_path).exists():
            self.error_occurred.emit(f"Scenario file not found: {xosc_path}")
            return

        # Clear overrides when a different scenario file is loaded
        if xosc_path != self._current_scenario:
            self._param_overrides.clear()

        self._current_scenario = xosc_path
        self._history.clear()
        self.scenario_loading.emit()

        self._worker = SimulationWorker(
            xosc_path=xosc_path,
            lib_dir=self._lib_dir,
            resource_root=self._resource_root,
            param_overrides=[
                (name, value_str, ptype)
                for name, (value_str, ptype) in self._param_overrides.items()
            ],
        )
        self._worker.state_updated.connect(self._accumulate_state)
        self._worker.storyboard_event.connect(self.storyboard_event)
        self._worker.condition_triggered.connect(self.condition_triggered)
        self._worker.road_network_ready.connect(self.road_network_ready)
        self._worker.odr_filename_ready.connect(self.odr_filename_ready)
        self._worker.parameters_ready.connect(self.parameters_ready)
        self._worker.road_load_warning.connect(self._on_road_load_warning)
        self._worker.error_occurred.connect(self._on_worker_error)
        self._worker.sim_finished.connect(self._on_sim_finished)
        self._worker.start()
        self.status_changed.emit("Paused")

    @pyqtSlot()
    def play(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.put_command(SimulationWorker.CMD_RESUME)
            self.status_changed.emit("Running")

    @pyqtSlot()
    def pause(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.put_command(SimulationWorker.CMD_PAUSE)
            self.status_changed.emit("Paused")

    @pyqtSlot()
    def step(self) -> None:
        """Advance the simulation by one dt while keeping it paused."""
        if self._worker and self._worker.isRunning():
            self._worker.put_command(SimulationWorker.CMD_STEP)

    @pyqtSlot()
    def restart(self) -> None:
        """Reload the current scenario from the beginning."""
        if self._current_scenario:
            self.load_scenario(self._current_scenario)

    @pyqtSlot(float)
    def set_timestep(self, dt: float) -> None:
        if self._worker:
            self._worker.put_command(SimulationWorker.CMD_SET_DT, dt=dt)

    # ------------------------------------------------------------------
    # Rewind / seek
    # ------------------------------------------------------------------

    def seek(self, frame_index: int) -> None:
        """
        Show a historical frame without advancing the simulation.

        When the worker is still running, delegates via CMD_SEEK so that
        report_object_pos is called on the worker thread.  When the simulation
        has already finished (worker stopped), replays positions directly from
        the history buffer without needing the worker.
        """
        if not self._history:
            return
        history_list = list(self._history)
        frame_index = max(0, min(frame_index, len(history_list) - 1))
        t, snapshots = history_list[frame_index]

        if self._worker and self._worker.isRunning():
            self.pause()
            self._worker.put_command(
                SimulationWorker.CMD_SEEK, t=t, snapshots=snapshots
            )
        else:
            # Worker finished - emit historical state directly without report_object_pos
            self.state_updated.emit(t, snapshots)

    # ------------------------------------------------------------------
    # Parameter editor
    # ------------------------------------------------------------------

    def apply_params_and_restart(self, params: list) -> None:
        """Store parameter overrides and restart the simulation with them applied."""
        for name, value_str, ptype in params:
            self._param_overrides[name] = (value_str, ptype)
        if self._current_scenario:
            self.load_scenario(self._current_scenario)

    def get_param_overrides(self) -> dict:
        """Return the current parameter overrides dict (name → (value_str, ptype))."""
        return self._param_overrides

    # ------------------------------------------------------------------
    # Object manipulation
    # ------------------------------------------------------------------

    def report_object_position(
        self,
        obj_id: int,
        x: float,
        y: float,
        z: float,
        h: float,
        p: float,
        r: float,
    ) -> None:
        if self._worker:
            self._worker.put_command(
                SimulationWorker.CMD_SET_OBJECT_POS,
                obj_id=obj_id,
                x=x,
                y=y,
                z=z,
                h=h,
                p=p,
                r=r,
            )

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _stop_worker(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.put_command(SimulationWorker.CMD_STOP)
            self._worker.wait(3000)
        self._worker = None

    @pyqtSlot(float, list)
    def _accumulate_state(self, t: float, objects: list) -> None:
        self._history.append((t, objects))
        self.state_updated.emit(t, objects)

    @pyqtSlot(str)
    def _on_road_load_warning(self, message: str) -> None:
        self.road_load_warning.emit(message)

    @pyqtSlot(str)
    def _on_worker_error(self, message: str) -> None:
        self.error_occurred.emit(message)
        self.status_changed.emit("Error")

    @pyqtSlot()
    def _on_sim_finished(self) -> None:
        self.sim_finished.emit()
        self.status_changed.emit("Finished")
