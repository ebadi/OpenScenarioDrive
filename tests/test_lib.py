"""
Unit tests for EsminiLib (esminiLib).

All tests run headless (use_viewer=0) so no display is required.
Tests are skipped when the shared library or scenario files are absent.
"""

import math

import pytest
from conftest import skip_no_se_lib
from esmini import (
    EsminiLib,
    SE_LaneChangeActionStruct,
    SE_SpeedActionStruct,
)

DT = 0.05  # fixed simulation timestep (s)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sim(xosc_path, lib_dir, resource_root):
    return EsminiLib.from_file(
        xosc_path,
        use_viewer=0,
        lib_dir=lib_dir,
        extra_paths=[resource_root],
    )


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


@skip_no_se_lib
class TestInit:
    def test_init_from_file(self, cut_in_xosc, lib_dir, resource_root):
        sim = _make_sim(cut_in_xosc, lib_dir, resource_root)
        assert sim.get_number_of_objects() > 0
        sim.close()

    def test_context_manager(self, cut_in_xosc, lib_dir, resource_root):
        with _make_sim(cut_in_xosc, lib_dir, resource_root) as sim:
            assert sim.get_number_of_objects() > 0

    def test_bad_file_raises(self, lib_dir):
        with pytest.raises(RuntimeError):
            EsminiLib.from_file("/nonexistent/bad.xosc", use_viewer=0, lib_dir=lib_dir)

    def test_init_headless_no_window(self, cut_in_xosc, lib_dir, resource_root):
        # Headless init must not fail even without a display
        with _make_sim(cut_in_xosc, lib_dir, resource_root) as sim:
            assert sim.get_quit_flag() in (0, 1)  # either not-done or already done


# ---------------------------------------------------------------------------
# Simulation stepping
# ---------------------------------------------------------------------------


@skip_no_se_lib
class TestStepping:
    @pytest.fixture(autouse=True)
    def sim(self, cut_in_xosc, lib_dir, resource_root):
        self._sim = _make_sim(cut_in_xosc, lib_dir, resource_root)
        yield
        self._sim.close()

    def test_simulation_time_starts_at_zero(self):
        assert self._sim.get_simulation_time() == pytest.approx(0.0, abs=1e-6)

    def test_step_dt_advances_time(self):
        self._sim.step_dt(DT)
        assert self._sim.get_simulation_time() > 0.0

    def test_step_dt_accumulates(self):
        for _ in range(10):
            self._sim.step_dt(DT)
        t = self._sim.get_simulation_time()
        assert t == pytest.approx(10 * DT, rel=0.05)

    def test_quit_flag_initially_not_set(self):
        assert self._sim.get_quit_flag() == 0

    def test_step_returns_nonnegative_while_running(self):
        ret = self._sim.step_dt(DT)
        assert ret >= 0


# ---------------------------------------------------------------------------
# Object queries
# ---------------------------------------------------------------------------


@skip_no_se_lib
class TestObjectQueries:
    @pytest.fixture(autouse=True)
    def sim(self, cut_in_xosc, lib_dir, resource_root):
        self._sim = _make_sim(cut_in_xosc, lib_dir, resource_root)
        self._sim.step_dt(DT)  # advance once so positions are defined
        yield
        self._sim.close()

    def test_number_of_objects(self):
        n = self._sim.get_number_of_objects()
        assert n >= 2  # cut-in_simple has Ego + OverTaker

    def test_get_id(self):
        obj_id = self._sim.get_id(0)
        assert obj_id >= 0

    def test_get_id_by_name_ego(self):
        obj_id = self._sim.get_id_by_name("Ego")
        assert obj_id >= 0

    def test_get_id_by_name_unknown(self):
        obj_id = self._sim.get_id_by_name("DoesNotExist")
        assert obj_id < 0

    def test_get_object_name(self):
        obj_id = self._sim.get_id(0)
        name = self._sim.get_object_name(obj_id)
        assert isinstance(name, str)
        assert len(name) > 0

    def test_get_object_state_fields(self):
        obj_id = self._sim.get_id(0)
        state = self._sim.get_object_state(obj_id)
        assert not math.isnan(state.x)
        assert not math.isnan(state.y)
        assert not math.isnan(state.speed)
        assert state.id == obj_id

    def test_get_object_state_by_index(self):
        state = self._sim.get_object_state_by_index(0)
        assert not math.isnan(state.x)

    def test_get_object_odometer(self):
        obj_id = self._sim.get_id(0)
        odo = self._sim.get_object_odometer(obj_id)
        assert not math.isnan(odo)

    def test_get_object_velocity_xyz(self):
        obj_id = self._sim.get_id(0)
        vx, vy, vz = self._sim.get_object_velocity_global_xyz(obj_id)
        assert not math.isnan(vx)

    def test_get_object_acceleration(self):
        obj_id = self._sim.get_id(0)
        acc = self._sim.get_object_acceleration(obj_id)
        assert not math.isnan(acc)

    def test_get_number_of_properties(self):
        obj_id = self._sim.get_id(0)
        n = self._sim.get_number_of_properties(obj_id)
        assert n >= 0


# ---------------------------------------------------------------------------
# Road information
# ---------------------------------------------------------------------------


@skip_no_se_lib
class TestRoadInfo:
    @pytest.fixture(autouse=True)
    def sim(self, cut_in_xosc, lib_dir, resource_root):
        self._sim = _make_sim(cut_in_xosc, lib_dir, resource_root)
        self._sim.step_dt(DT)
        yield
        self._sim.close()

    def test_get_odr_filename_is_string(self):
        name = self._sim.get_odr_filename()
        assert isinstance(name, str)
        assert len(name) > 0

    def test_get_road_info_at_distance(self):
        obj_id = self._sim.get_id(0)
        info = self._sim.get_road_info_at_distance(obj_id, 20.0)
        assert info is not None
        assert not math.isnan(info.global_pos_x)
        assert not math.isnan(info.curvature)

    def test_get_road_info_along_route(self):
        obj_id = self._sim.get_id(0)
        info = self._sim.get_road_info_along_route(obj_id, 10.0)
        # may return None if no route is set - that's OK
        if info is not None:
            assert not math.isnan(info.global_pos_x)

    def test_get_speed_unit(self):
        unit = self._sim.get_speed_unit()
        assert unit in (-1, 0, 1, 2, 3)

    def test_get_distance_to_object(self):
        if self._sim.get_number_of_objects() < 2:
            pytest.skip("Need at least 2 objects")
        id_a = self._sim.get_id(0)
        id_b = self._sim.get_id(1)
        diff = self._sim.get_distance_to_object(id_a, id_b)
        # None is valid when no route between positions can be found
        if diff is not None:
            assert not math.isnan(diff.ds)

    def test_get_road_signs(self):
        obj_id = self._sim.get_id(0)
        state = self._sim.get_object_state(obj_id)
        n_signs = self._sim.get_number_of_road_signs(state.roadId)
        assert n_signs >= 0


# ---------------------------------------------------------------------------
# Position reporting (external controller)
# ---------------------------------------------------------------------------


@skip_no_se_lib
class TestPositionReporting:
    @pytest.fixture(autouse=True)
    def sim(self, cut_in_xosc, lib_dir, resource_root):
        self._sim = _make_sim(cut_in_xosc, lib_dir, resource_root)
        self._sim.step_dt(DT)
        yield
        self._sim.close()

    def test_report_object_pos(self):
        obj_id = self._sim.get_id(0)
        state = self._sim.get_object_state(obj_id)
        ret = self._sim.report_object_pos(
            obj_id, state.x + 1.0, state.y, state.z, state.h, state.p, state.r
        )
        assert ret >= 0

    def test_report_object_pos_xyh(self):
        obj_id = self._sim.get_id(0)
        state = self._sim.get_object_state(obj_id)
        ret = self._sim.report_object_pos_xyh(obj_id, state.x, state.y, state.h)
        assert ret >= 0

    def test_report_object_road_pos(self):
        obj_id = self._sim.get_id(0)
        state = self._sim.get_object_state(obj_id)
        ret = self._sim.report_object_road_pos(
            obj_id, state.roadId, state.laneId, state.laneOffset, state.s
        )
        assert ret >= 0

    def test_report_object_speed(self):
        obj_id = self._sim.get_id(0)
        ret = self._sim.report_object_speed(obj_id, 15.0)
        assert ret >= 0

    def test_report_object_vel(self):
        obj_id = self._sim.get_id(0)
        ret = self._sim.report_object_vel(obj_id, 10.0, 0.0, 0.0)
        assert ret >= 0


# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------


@skip_no_se_lib
class TestParameters:
    @pytest.fixture(autouse=True)
    def sim(self, cut_in_xosc, lib_dir, resource_root):
        self._sim = _make_sim(cut_in_xosc, lib_dir, resource_root)
        yield
        self._sim.close()

    def test_get_number_of_parameters(self):
        n = self._sim.get_number_of_parameters()
        assert n >= 0

    def test_get_parameter_name(self):
        n = self._sim.get_number_of_parameters()
        if n == 0:
            pytest.skip("No parameters in this scenario")
        name, ptype = self._sim.get_parameter_name(0)
        assert isinstance(name, str) and len(name) > 0
        assert ptype in (1, 2, 3, 4)

    def test_set_get_parameter_double(self):
        # HeadwayTime_LaneChange is defined in cut-in_simple.xosc
        try:
            self._sim.set_parameter_double("HeadwayTime_LaneChange", 0.5)
            val = self._sim.get_parameter_double("HeadwayTime_LaneChange")
            assert val == pytest.approx(0.5)
        except KeyError:
            pytest.skip("Parameter not present in this scenario")

    def test_get_nonexistent_parameter_raises(self):
        with pytest.raises(KeyError):
            self._sim.get_parameter_int("__nonexistent__")


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------


@skip_no_se_lib
class TestCallbacks:
    def test_storyboard_callback(self, cut_in_xosc, lib_dir, resource_root):
        events = []

        with _make_sim(cut_in_xosc, lib_dir, resource_root) as sim:
            sim.register_storyboard_callback(
                lambda name, etype, estate, path: events.append((name, etype, estate))
            )
            for _ in range(20):
                sim.step_dt(DT)

        assert len(events) > 0
        names = [e[0] for e in events]
        assert any(isinstance(n, str) and len(n) > 0 for n in names)

    def test_condition_callback(self, cut_in_xosc, lib_dir, resource_root):
        conditions = []

        with _make_sim(cut_in_xosc, lib_dir, resource_root) as sim:
            sim.register_condition_callback(
                lambda name, ts: conditions.append((name, ts))
            )
            # Run for a few seconds - at least the start condition should trigger
            for _ in range(int(3.0 / DT)):
                if sim.step_dt(DT) < 0:
                    break

        assert len(conditions) > 0
        assert all(isinstance(c[0], str) for c in conditions)
        assert all(isinstance(c[1], float) for c in conditions)


# ---------------------------------------------------------------------------
# Simple Vehicle
# ---------------------------------------------------------------------------


@skip_no_se_lib
class TestSimpleVehicle:
    @pytest.fixture(autouse=True)
    def sim(self, cut_in_xosc, lib_dir, resource_root):
        self._sim = _make_sim(cut_in_xosc, lib_dir, resource_root)
        yield
        self._sim.close()

    def test_create_and_delete(self):
        sv = self._sim.create_simple_vehicle(0.0, 0.0, 0.0, 4.0, 0.0)
        assert sv is not None
        sv.delete()

    def test_context_manager(self):
        with self._sim.create_simple_vehicle(0.0, 0.0, 0.0, 4.0, 10.0) as sv:
            state = sv.get_state()
            assert not math.isnan(state.x)
            assert not math.isnan(state.speed)

    def test_control_analog_accelerates(self):
        with self._sim.create_simple_vehicle(0.0, 0.0, 0.0, 4.0, 0.0) as sv:
            for _ in range(20):
                sv.control_analog(DT, 1.0, 0.0)  # full throttle, straight
            state = sv.get_state()
            assert state.speed > 0.1

    def test_control_binary_brakes(self):
        with self._sim.create_simple_vehicle(0.0, 0.0, 0.0, 4.0, 20.0) as sv:
            for _ in range(30):
                sv.control_binary(DT, -1, 0)  # brake
            state = sv.get_state()
            assert state.speed < 20.0  # must have decelerated

    def test_set_speed(self):
        with self._sim.create_simple_vehicle(0.0, 0.0, 0.0, 4.0, 0.0) as sv:
            sv.set_speed(15.0)
            state = sv.get_state()
            assert state.speed == pytest.approx(15.0, abs=1.0)

    def test_control_target(self):
        with self._sim.create_simple_vehicle(0.0, 0.0, 0.0, 4.0, 10.0) as sv:
            for _ in range(5):
                sv.control_target(DT, 20.0, 0.0)  # target speed 20 m/s, heading 0
            state = sv.get_state()
            assert state.speed >= 10.0  # should have accelerated toward target


# ---------------------------------------------------------------------------
# Action injection
# ---------------------------------------------------------------------------


@skip_no_se_lib
class TestActionInjection:
    @pytest.fixture(autouse=True)
    def sim(self, cut_in_xosc, lib_dir, resource_root):
        self._sim = _make_sim(cut_in_xosc, lib_dir, resource_root)
        for _ in range(5):
            self._sim.step_dt(DT)
        yield
        self._sim.close()

    def test_inject_speed_action(self):
        obj_id = self._sim.get_id(0)
        action = SE_SpeedActionStruct()
        action.id = obj_id
        action.speed = 30.0
        action.transition_shape = 0  # cubic
        action.transition_dim = 2  # time
        action.transition_value = 2.0
        self._sim.inject_speed_action(action)
        # Verify the injected action is accepted without error
        assert True  # no exception means success

    def test_inject_lane_change_action(self):
        obj_id = self._sim.get_id(0)
        action = SE_LaneChangeActionStruct()
        action.id = obj_id
        action.mode = 0  # absolute
        action.target = -2  # target lane id
        action.transition_shape = 0
        action.transition_dim = 2
        action.transition_value = 3.0
        self._sim.inject_lane_change_action(action)
        assert True

    def test_injected_action_ongoing_check(self):
        result = self._sim.injected_action_ongoing(-1)
        assert isinstance(result, bool)
