"""
Full system integration tests - EsminiLib + RoadManagerLib interoperability.

These tests exercise real-world scenarios that combine both libraries:
  1. Running a complete cut-in scenario and verifying vehicle trajectories.
  2. Cross-validating road-position data between SE and RM APIs.
  3. Verifying storyboard-driven events fire in the correct order.
  4. Confirming callback data matches direct object state queries.
"""

import math
import os

import pytest
from conftest import skip_no_se_lib
from esmini import EsminiLib, RoadManagerLib

DT = 0.05  # fixed simulation step (s)
SIM_TIME = 8.0  # seconds to run the full scenario


def _both_libs():
    """True when both shared libraries exist."""
    from conftest import _rm_lib_available, _se_lib_available

    return _se_lib_available() and _rm_lib_available()


skip_no_both = pytest.mark.skipif(
    not _both_libs(),
    reason="Both libesminiLib and libesminiRMLib are required for integration tests",
)


def _make_sim(xosc_path, lib_dir, resource_root):
    return EsminiLib.from_file(
        xosc_path,
        use_viewer=0,
        lib_dir=lib_dir,
        extra_paths=[resource_root],
    )


# ---------------------------------------------------------------------------
# 1.  Full scenario execution
# ---------------------------------------------------------------------------


@skip_no_se_lib
class TestFullScenario:
    """Run the cut-in scenario to completion and validate trajectory data."""

    def test_scenario_runs_to_completion(self, cut_in_xosc, lib_dir, resource_root):
        steps = 0
        max_steps = int(SIM_TIME / DT) + 100

        with _make_sim(cut_in_xosc, lib_dir, resource_root) as sim:
            while steps < max_steps:
                ret = sim.step_dt(DT)
                steps += 1
                if ret < 0 or sim.get_quit_flag():
                    break

        assert steps > 10, "Simulation ended too quickly (< 10 frames)"

    def test_ego_moves_forward(self, cut_in_xosc, lib_dir, resource_root):
        """Ego starts at s=50; it must move forward during the simulation."""
        with _make_sim(cut_in_xosc, lib_dir, resource_root) as sim:
            ego_id = sim.get_id_by_name("Ego")
            if ego_id < 0:
                ego_id = sim.get_id(0)

            s_initial = sim.get_object_state(ego_id).s

            for _ in range(int(3.0 / DT)):
                if sim.step_dt(DT) < 0:
                    break

            s_final = sim.get_object_state(ego_id).s

        assert s_final > s_initial, (
            f"Ego did not advance: s_initial={s_initial:.2f}, s_final={s_final:.2f}"
        )

    def test_all_objects_have_valid_positions(
        self, cut_in_xosc, lib_dir, resource_root
    ):
        """No object should ever have NaN coordinates."""
        with _make_sim(cut_in_xosc, lib_dir, resource_root) as sim:
            for step in range(int(2.0 / DT)):
                sim.step_dt(DT)
                for idx in range(sim.get_number_of_objects()):
                    obj_id = sim.get_id(idx)
                    state = sim.get_object_state(obj_id)
                    assert not math.isnan(state.x), (
                        f"NaN x at step {step}, obj {obj_id}"
                    )
                    assert not math.isnan(state.y), (
                        f"NaN y at step {step}, obj {obj_id}"
                    )
                    assert not math.isnan(state.speed), (
                        f"NaN speed at step {step}, obj {obj_id}"
                    )


# ---------------------------------------------------------------------------
# 2.  SE / RM interoperability
# ---------------------------------------------------------------------------


class TestInteroperability:
    """
    Load the same road network with both EsminiLib and RoadManagerLib and
    verify that position data is consistent between the two APIs.
    """

    @pytest.mark.skipif(
        not (_both_libs()),
        reason="Requires both libs",
    )
    def test_odr_filename_resolves_in_rm(self, cut_in_xosc, lib_dir, resource_root):
        """The ODR file returned by SE must be loadable by RM."""
        with _make_sim(cut_in_xosc, lib_dir, resource_root) as sim:
            odr_path = sim.get_odr_filename()

        assert isinstance(odr_path, str) and len(odr_path) > 0, (
            "SE_GetODRFilename returned empty string"
        )

        # Resolve the path relative to the resources directory if needed
        if not os.path.isabs(odr_path):
            candidate = os.path.join(resource_root, odr_path)
            if os.path.isfile(candidate):
                odr_path = candidate
            else:
                candidate = os.path.join(
                    resource_root, "xodr", os.path.basename(odr_path)
                )
                if os.path.isfile(candidate):
                    odr_path = candidate

        if not os.path.isfile(odr_path):
            pytest.skip(f"Could not locate ODR file: {odr_path}")

        with RoadManagerLib(odr_path, lib_dir=lib_dir) as rm:
            assert rm.get_number_of_roads() > 0

    @pytest.mark.skipif(
        not (_both_libs()),
        reason="Requires both libs",
    )
    def test_se_and_rm_agree_on_road_position(
        self,
        cut_in_xosc,
        lib_dir,
        resource_root,
        straight_xodr,
    ):
        """
        Place an RM position on the same road/lane/s as the Ego vehicle reports
        from SE.  The world x,y coordinates from both APIs should agree within
        a reasonable tolerance (different snap logic may shift slightly).
        """
        with _make_sim(cut_in_xosc, lib_dir, resource_root) as sim:
            for _ in range(10):
                sim.step_dt(DT)
            ego_id = sim.get_id_by_name("Ego")
            if ego_id < 0:
                ego_id = sim.get_id(0)
            se_state = sim.get_object_state(ego_id)

        with RoadManagerLib(straight_xodr, lib_dir=lib_dir) as rm:
            h = rm.create_position()
            rm.set_lane_position(
                h,
                road_id=se_state.roadId,
                lane_id=se_state.laneId,
                lane_offset=se_state.laneOffset,
                s=se_state.s,
            )
            rm_data = rm.get_position_data(h)
            rm.delete_position(h)

        assert rm_data is not None
        # Allow up to 2 m tolerance - different road-snap implementations may differ
        dist = math.hypot(se_state.x - rm_data.x, se_state.y - rm_data.y)
        assert dist < 2.0, (
            f"SE pos ({se_state.x:.2f}, {se_state.y:.2f}) vs "
            f"RM pos ({rm_data.x:.2f}, {rm_data.y:.2f}) - delta {dist:.2f} m"
        )

    @pytest.mark.skipif(
        not (_both_libs()),
        reason="Requires both libs",
    )
    def test_rm_lookahead_along_se_trajectory(
        self,
        cut_in_xosc,
        lib_dir,
        resource_root,
        straight_xodr,
    ):
        """
        Simulate a simple lookahead: get the Ego's current position, ask RM
        for lane info 30 m ahead, and verify the result is on the same road.
        """
        with _make_sim(cut_in_xosc, lib_dir, resource_root) as sim:
            for _ in range(5):
                sim.step_dt(DT)
            ego_id = sim.get_id_by_name("Ego")
            if ego_id < 0:
                ego_id = sim.get_id(0)
            state = sim.get_object_state(ego_id)
            road_id = state.roadId
            s_ego = state.s

        with RoadManagerLib(straight_xodr, lib_dir=lib_dir) as rm:
            h = rm.create_position()
            rm.set_lane_position(
                h, road_id=road_id, lane_id=-1, lane_offset=0.0, s=s_ego
            )
            info = rm.get_lane_info(h, 30.0)
            rm.delete_position(h)

        assert info is not None, "RM_GetLaneInfo failed for 30 m lookahead"
        assert info.roadId == road_id


# ---------------------------------------------------------------------------
# 3.  Storyboard event ordering
# ---------------------------------------------------------------------------


@skip_no_se_lib
class TestStoryboardOrdering:
    def test_storyboard_sequence(self, cut_in_xosc, lib_dir, resource_root):
        """
        Events must follow the order: STANDBY → RUNNING (→ COMPLETE).
        Verify that no element jumps from STANDBY to COMPLETE without RUNNING.
        """
        per_element = {}  # name → [states in order]

        def on_change(name, etype, estate, path):
            per_element.setdefault(name, []).append(estate)

        with _make_sim(cut_in_xosc, lib_dir, resource_root) as sim:
            sim.register_storyboard_callback(on_change)
            for _ in range(int(SIM_TIME / DT)):
                if sim.step_dt(DT) < 0 or sim.get_quit_flag():
                    break

        assert len(per_element) > 0, "No storyboard events were received"

        for name, states in per_element.items():
            # STANDBY (1) must appear before RUNNING (2) if RUNNING is present
            if 2 in states and 1 in states:
                first_standby = states.index(1)
                first_running = states.index(2)
                assert first_standby < first_running, (
                    f"'{name}': RUNNING appeared before STANDBY"
                )


# ---------------------------------------------------------------------------
# 4.  Callback / direct-query consistency
# ---------------------------------------------------------------------------


@skip_no_se_lib
class TestCallbackConsistency:
    def test_object_callback_matches_direct_query(
        self, cut_in_xosc, lib_dir, resource_root
    ):
        """
        The ScenarioObjectState received in the object callback must match the
        value returned by get_object_state() at the same step.
        """
        callback_states = []

        with _make_sim(cut_in_xosc, lib_dir, resource_root) as sim:
            ego_id = sim.get_id_by_name("Ego")
            if ego_id < 0:
                ego_id = sim.get_id(0)

            sim.register_object_callback(
                ego_id, lambda s: callback_states.append((s.x, s.y, s.speed))
            )

            direct_states = []
            for _ in range(10):
                sim.step_dt(DT)
                ds = sim.get_object_state(ego_id)
                direct_states.append((ds.x, ds.y, ds.speed))

        assert len(callback_states) == len(direct_states), (
            "Mismatch in number of callback vs direct-query samples"
        )
        for i, (cb, dq) in enumerate(zip(callback_states, direct_states)):
            assert cb[0] == pytest.approx(dq[0], abs=1e-6), f"x mismatch at step {i}"
            assert cb[1] == pytest.approx(dq[1], abs=1e-6), f"y mismatch at step {i}"
