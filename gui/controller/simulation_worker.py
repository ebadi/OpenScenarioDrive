"""
SimulationWorker - runs the esmini step loop on a dedicated QThread.

All esmini API calls are confined to this thread. The main thread
communicates via put_command(); results come back through Qt signals.
"""

from __future__ import annotations

import dataclasses
import logging
import math
from queue import Empty, Queue
from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal

_log = logging.getLogger(f"OpenScenarioDrive.{__name__}")


@dataclasses.dataclass
class ObjectSnapshot:
    """Lightweight, picklable snapshot of one scenario object."""

    id: int
    name: str
    x: float
    y: float
    z: float
    h: float
    speed: float
    road_id: int
    lane_id: int
    s: float
    length: float = 4.5
    width: float = 2.0
    # Extended dynamics
    acceleration: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0
    yaw_rate: float = 0.0
    odometer: float = 0.0
    collision_count: int = 0
    type_name: str = ""
    model_filename: str = ""


class SimulationWorker(QThread):
    """
    Signals
    -------
    state_updated(sim_time, objects)
        Emitted every step with current time and a list of ObjectSnapshot.
    storyboard_event(sim_time, element_name, element_type, element_state)
        Emitted when a storyboard element changes state.
    condition_triggered(timestamp, condition_name)
        Emitted when a condition evaluates to true.
    error_occurred(message)
        Emitted on any unrecoverable error; worker stops afterwards.
    sim_finished()
        Emitted when the scenario reaches its natural end.
    """

    state_updated = pyqtSignal(float, list)
    storyboard_event = pyqtSignal(float, str, str, str)  # time, name, type, state
    condition_triggered = pyqtSignal(float, str)  # timestamp, name
    road_network_ready = pyqtSignal(list, list)  # lane_strips, signs
    odr_filename_ready = pyqtSignal(str)  # resolved .xodr path
    parameters_ready = pyqtSignal(list)  # [{name, type, value}]
    road_load_warning = pyqtSignal(str)  # non-fatal road sampling error
    error_occurred = pyqtSignal(str)
    sim_finished = pyqtSignal()

    # Command tokens - passed via put_command()
    CMD_PAUSE = "pause"
    CMD_RESUME = "resume"
    CMD_STOP = "stop"
    CMD_STEP = "step"
    CMD_SET_DT = "set_dt"
    CMD_SET_OBJECT_POS = "set_object_pos"
    CMD_SEEK = "seek"
    CMD_SET_PARAMETER = "set_parameter"

    def __init__(
        self,
        xosc_path: str,
        lib_dir: str,
        resource_root: str,
        dt: float = 0.05,
        param_overrides: list | None = None,
    ) -> None:
        super().__init__()
        self._xosc_path = xosc_path
        self._lib_dir = lib_dir
        self._resource_root = resource_root
        self._dt = dt
        self._param_overrides: list = param_overrides or []

        self._commands: Queue = Queue()
        self._paused = True
        self._running = False
        self._sim: Any = None

    # ------------------------------------------------------------------
    # Public API - safe to call from any thread
    # ------------------------------------------------------------------

    def put_command(self, cmd: str, **kwargs) -> None:
        """Enqueue a command for the worker thread to process."""
        self._commands.put((cmd, kwargs))

    # ------------------------------------------------------------------
    # QThread.run - everything below runs on the worker thread
    # ------------------------------------------------------------------

    def run(self) -> None:
        try:
            self._sim = self._init_sim()
            if self._sim is None:
                return
            self._register_callbacks()
            self._load_road_network()
            self._emit_parameters()
            self._running = True
            self._loop()
        except Exception as exc:
            self.error_occurred.emit(str(exc))
        finally:
            self._teardown()

    def _init_sim(self):
        try:
            from esmini import EsminiLib

            overrides = self._param_overrides

            def _on_param_decl(sim) -> None:
                for name, value_str, ptype in overrides:
                    try:
                        if ptype == 1:
                            sim.set_parameter_int(name, int(value_str))
                        elif ptype == 2:
                            sim.set_parameter_double(name, float(value_str))
                        elif ptype == 3:
                            sim.set_parameter_string(name, value_str)
                        elif ptype == 4:
                            sim.set_parameter_bool(
                                name, value_str.lower() in ("true", "1", "yes")
                            )
                    except Exception as exc:
                        _log.warning("Parameter override '%s' failed: %s", name, exc)

            return EsminiLib.from_file(
                self._xosc_path,
                use_viewer=0,
                lib_dir=self._lib_dir,
                extra_paths=[self._resource_root] if self._resource_root else None,
                param_decl_fn=_on_param_decl if overrides else None,
            )
        except Exception as exc:
            self.error_occurred.emit(self._diagnose_init_error(str(exc)))
            return None

    def _diagnose_init_error(self, raw: str) -> str:
        lines = [f"Failed to load scenario:\n{raw}", ""]
        xosc = self._xosc_path
        try:
            import pathlib
            import re

            text = pathlib.Path(xosc).read_text(errors="replace")
            # Catalog directories referenced in the file
            catalogs = re.findall(r'<Directory\s+path=["\']([^"\']+)["\']', text)
            missing = [p for p in catalogs if not pathlib.Path(p).exists()]
            if missing:
                lines.append("Missing catalog / resource directories:")
                for p in missing:
                    lines.append(f"  • {p}")
                lines.append(
                    "\nMount or copy the required assets into the container,\n"
                    "or set SCENARIO_DIR in docker-compose.yml to a directory\n"
                    "that contains both the .xosc file and its dependencies."
                )
        except Exception as exc:
            _log.debug("Could not analyse scenario file for error hints: %s", exc)
        if len(lines) == 2:
            lines.append(
                "Check that ESMINI_RESOURCE_PATH is set correctly and that all\n"
                "files referenced by the scenario exist inside the container."
            )
        return "\n".join(lines)

    def _register_callbacks(self) -> None:
        from esmini import ELEMENT_STATES, ELEMENT_TYPES

        def _on_storyboard(name: str, etype: int, estate: int, path: str) -> None:
            t = self._sim.get_simulation_time() if self._sim else 0.0
            self.storyboard_event.emit(
                t,
                name,
                ELEMENT_TYPES.get(etype, str(etype)),
                ELEMENT_STATES.get(estate, str(estate)),
            )

        def _on_condition(name: str, timestamp: float) -> None:
            self.condition_triggered.emit(timestamp, name)

        self._sim.register_storyboard_callback(_on_storyboard)
        self._sim.register_condition_callback(_on_condition)

    def _loop(self) -> None:
        while self._running:
            self._drain_commands()

            if self._paused:
                self.msleep(50)
                continue

            ret = self._sim.step_dt(self._dt)
            t = self._sim.get_simulation_time()
            self.state_updated.emit(t, self._collect_snapshots())

            if ret < 0 or self._sim.get_quit_flag():
                self._running = False
                self.sim_finished.emit()
                break

            self.msleep(50)  # fixed 20 fps wall-clock; dt controls sim speed

    def _drain_commands(self) -> None:
        while True:
            try:
                cmd, kwargs = self._commands.get_nowait()
            except Empty:
                break

            if cmd == self.CMD_PAUSE:
                self._paused = True
            elif cmd == self.CMD_RESUME:
                self._paused = False
            elif cmd == self.CMD_STOP:
                self._running = False
            elif cmd == self.CMD_STEP:
                self._step_once()
            elif cmd == self.CMD_SET_DT:
                self._dt = float(kwargs["dt"])
            elif cmd == self.CMD_SET_OBJECT_POS:
                self._apply_object_pos(**kwargs)
            elif cmd == self.CMD_SEEK:
                self._apply_seek(kwargs["t"], kwargs["snapshots"])
            elif cmd == self.CMD_SET_PARAMETER:
                self._apply_parameter(**kwargs)

    def _step_once(self) -> None:
        """Advance the simulation by exactly one dt while remaining paused."""
        if self._sim is None:
            return
        ret = self._sim.step_dt(self._dt)
        t = self._sim.get_simulation_time()
        self.state_updated.emit(t, self._collect_snapshots())
        if ret < 0 or self._sim.get_quit_flag():
            self._running = False
            self.sim_finished.emit()

    def _apply_seek(self, t: float, snapshots: list) -> None:
        """Apply a historical frame's positions for visual scrubbing (sim stays paused)."""
        for snap in snapshots:
            try:
                self._sim.report_object_pos(
                    snap.id, snap.x, snap.y, snap.z, snap.h, 0.0, 0.0
                )
            except Exception as exc:
                _log.debug(
                    "report_object_pos during seek failed for obj %d: %s", snap.id, exc
                )
        self.state_updated.emit(t, snapshots)

    def _apply_object_pos(
        self,
        obj_id: int,
        x: float,
        y: float,
        z: float,
        h: float,
        p: float,
        r: float,
    ) -> None:
        try:
            self._sim.report_object_pos(obj_id, x, y, z, h, p, r)
        except Exception as exc:
            self.error_occurred.emit(f"report_object_pos failed: {exc}")

    def _collect_snapshots(self) -> list[ObjectSnapshot]:
        snapshots = []
        try:
            n = self._sim.get_number_of_objects()
            for i in range(n):
                obj_id = self._sim.get_id(i)
                state = self._sim.get_object_state(obj_id)
                if math.isnan(state.x):
                    continue

                acceleration = 0.0
                vx = vy = vz = 0.0
                yaw_rate = 0.0
                odometer = 0.0
                collision_count = 0
                type_name = ""
                model_filename = ""

                try:
                    acceleration = self._sim.get_object_acceleration(obj_id)
                except Exception:
                    pass
                try:
                    vx, vy, vz = self._sim.get_object_velocity_global_xyz(obj_id)
                except Exception:
                    pass
                try:
                    yaw_rate, _, _ = self._sim.get_object_angular_velocity(obj_id)
                except Exception:
                    pass
                try:
                    odometer = self._sim.get_object_odometer(obj_id)
                except Exception:
                    pass
                try:
                    collision_count = self._sim.get_object_number_of_collisions(obj_id)
                except Exception:
                    pass
                try:
                    type_name = self._sim.get_object_type_name(obj_id) or ""
                except Exception:
                    pass
                try:
                    model_filename = self._sim.get_object_model_filename(obj_id) or ""
                except Exception:
                    pass

                snapshots.append(
                    ObjectSnapshot(
                        id=obj_id,
                        name=self._sim.get_object_name(obj_id),
                        x=state.x,
                        y=state.y,
                        z=state.z,
                        h=state.h,
                        speed=state.speed,
                        road_id=state.roadId,
                        lane_id=state.laneId,
                        s=state.s,
                        length=max(1.0, state.length),
                        width=max(0.5, state.width),
                        acceleration=acceleration,
                        vx=vx,
                        vy=vy,
                        vz=vz,
                        yaw_rate=yaw_rate,
                        odometer=odometer,
                        collision_count=collision_count,
                        type_name=type_name,
                        model_filename=model_filename,
                    )
                )
        except Exception as exc:
            _log.error("Snapshot collection failed: %s", exc)
        return snapshots

    def _load_road_network(self) -> None:
        """Sample road geometry once from RoadManagerLib and emit road_network_ready."""
        import traceback

        lane_strips: list = []
        signs: list = []

        try:
            from esmini import RoadManagerLib

            odr = self._sim.get_odr_filename()
            if not odr:
                print(
                    "[road] SE_GetODRFilename returned empty - skipping road network",
                    flush=True,
                )
                return
            print(f"[road] ODR path: {odr!r}  lib_dir: {self._lib_dir!r}", flush=True)
            self.odr_filename_ready.emit(odr)

            with RoadManagerLib(odr, lib_dir=self._lib_dir) as rm:
                n_roads = rm.get_number_of_roads()
                print(f"[road] {n_roads} road(s) found", flush=True)
                for ri in range(n_roads):
                    road_id = rm.get_id_of_road_from_index(ri)
                    road_len = rm.get_road_length(road_id)
                    if road_len <= 0:
                        continue

                    s_mid = road_len / 2.0
                    step = max(0.5, road_len / 200)  # max 200 samples per road

                    h = rm.create_position()
                    try:
                        # Collect drivable lane IDs at road midpoint
                        n_driv = rm.get_road_number_of_drivable_lanes(road_id, s_mid)
                        lane_ids = []
                        for j in range(n_driv):
                            try:
                                lane_ids.append(
                                    rm.get_drivable_lane_id_by_index(road_id, j, s_mid)
                                )
                            except IndexError:
                                pass

                        # Fall back to reference line if no drivable lanes found
                        if not lane_ids:
                            lane_ids = [None]

                        for lane_id in lane_ids:
                            if lane_id is None:
                                width = 3.5
                            else:
                                width = (
                                    rm.get_lane_width_by_road_id(
                                        road_id, lane_id, s_mid
                                    )
                                    or 3.5
                                )

                            pts = []
                            s = 0.0
                            while True:
                                if lane_id is None:
                                    rm.set_road_position(h, road_id, s, 0.0)
                                else:
                                    rm.set_lane_position(h, road_id, lane_id, 0.0, s)
                                d = rm.get_position_data(h)
                                if d:
                                    pts.append((d.x, d.y))
                                if s >= road_len:
                                    break
                                s = min(s + step, road_len)

                            if len(pts) >= 2:
                                lane_strips.append(
                                    {
                                        "points": pts,
                                        "width": width,
                                        "lane_id": lane_id,
                                        "road_id": road_id,
                                    }
                                )
                    finally:
                        rm.delete_position(h)

                    # Road signs
                    for si in range(rm.get_number_of_road_signs(road_id)):
                        sg = rm.get_road_sign(road_id, si)
                        if sg:
                            nm = (
                                sg.name.decode("utf-8", errors="replace")
                                if sg.name
                                else ""
                            )
                            signs.append({"x": sg.x, "y": sg.y, "h": sg.h, "name": nm})

        except Exception:
            import io

            buf = io.StringIO()
            traceback.print_exc(file=buf)
            msg = buf.getvalue()
            print(msg, flush=True)
            self.road_load_warning.emit(f"Road network could not be loaded:\n{msg}")

        print(
            f"[road] emitting {len(lane_strips)} strip(s), {len(signs)} sign(s)",
            flush=True,
        )
        self.road_network_ready.emit(lane_strips, signs)

    def _emit_parameters(self) -> None:
        try:
            n = self._sim.get_number_of_parameters()
            params = []
            for i in range(n):
                name, ptype = self._sim.get_parameter_name(i)
                if not name:
                    continue
                value = self._read_parameter_value(name, ptype)
                params.append({"name": name, "type": ptype, "value": value})
            if params:
                self.parameters_ready.emit(params)
        except Exception as exc:
            _log.warning("Failed to enumerate parameters: %s", exc)

    def _read_parameter_value(self, name: str, ptype: int):
        try:
            if ptype == 1:
                return self._sim.get_parameter_int(name)
            elif ptype == 2:
                return self._sim.get_parameter_double(name)
            elif ptype == 3:
                return self._sim.get_parameter_string(name)
            elif ptype == 4:
                return self._sim.get_parameter_bool(name)
        except Exception as exc:
            _log.warning(
                "Failed to read parameter '%s' (type %d): %s", name, ptype, exc
            )
        return ""

    def _apply_parameter(self, name: str, value_str: str, ptype: int) -> None:
        try:
            if ptype == 1:
                self._sim.set_parameter_int(name, int(value_str))
            elif ptype == 2:
                self._sim.set_parameter_double(name, float(value_str))
            elif ptype == 3:
                self._sim.set_parameter_string(name, value_str)
            elif ptype == 4:
                self._sim.set_parameter_bool(
                    name, value_str.lower() in ("true", "1", "yes")
                )
        except Exception as exc:
            self.error_occurred.emit(f"set_parameter '{name}' failed: {exc}")

    def _teardown(self) -> None:
        if self._sim:
            try:
                self._sim.close()
            except Exception:
                pass
            self._sim = None
