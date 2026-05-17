"""
Unit tests for RoadManagerLib (esminiRMLib).

Each test class is self-contained and targets a logical group of the RM API.
Tests are skipped automatically when the shared library is not available.
"""

import math

import pytest
from conftest import skip_no_rm_lib
from esmini import (
    RoadManagerLib,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_rm(odr_path, lib_dir):
    return RoadManagerLib(odr_path, lib_dir=lib_dir)


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


@skip_no_rm_lib
class TestInit:
    def test_init_from_file(self, straight_xodr, lib_dir):
        rm = _make_rm(straight_xodr, lib_dir)
        assert rm.get_number_of_roads() > 0
        rm.close()

    def test_context_manager(self, straight_xodr, lib_dir):
        with _make_rm(straight_xodr, lib_dir) as rm:
            assert rm.get_number_of_roads() > 0

    def test_init_bad_file_raises(self, lib_dir):
        with pytest.raises(RuntimeError):
            RoadManagerLib("/nonexistent/path/bad.xodr", lib_dir=lib_dir)


# ---------------------------------------------------------------------------
# Road topology queries
# ---------------------------------------------------------------------------


@skip_no_rm_lib
class TestRoadTopology:
    @pytest.fixture(autouse=True)
    def rm(self, straight_xodr, lib_dir):
        self._rm = _make_rm(straight_xodr, lib_dir)
        yield
        self._rm.close()

    def test_number_of_roads(self):
        n = self._rm.get_number_of_roads()
        assert n >= 1

    def test_road_id_from_index(self):
        road_id = self._rm.get_id_of_road_from_index(0)
        assert road_id >= 0

    def test_road_length(self):
        road_id = self._rm.get_id_of_road_from_index(0)
        length = self._rm.get_road_length(road_id)
        assert length > 0.0

    def test_road_id_string_roundtrip(self):
        road_id = self._rm.get_id_of_road_from_index(0)
        s = self._rm.get_road_id_string(road_id)
        # If RM returns a non-empty string, round-trip it
        if s:
            recovered = self._rm.get_road_id_from_string(s)
            assert recovered == road_id

    def test_number_of_drivable_lanes(self):
        road_id = self._rm.get_id_of_road_from_index(0)
        length = self._rm.get_road_length(road_id)
        n = self._rm.get_road_number_of_drivable_lanes(road_id, length / 2)
        assert n > 0

    def test_number_of_all_lanes(self):
        road_id = self._rm.get_id_of_road_from_index(0)
        n = self._rm.get_road_number_of_lanes(road_id, 10.0, -1)  # -1 = any type
        assert n > 0

    def test_drivable_lane_id_by_index(self):
        road_id = self._rm.get_id_of_road_from_index(0)
        lane_id = self._rm.get_drivable_lane_id_by_index(road_id, 0, 10.0)
        assert lane_id != 0  # 0 is the reference lane, never drivable


# ---------------------------------------------------------------------------
# Position object lifecycle
# ---------------------------------------------------------------------------


@skip_no_rm_lib
class TestPositionLifecycle:
    @pytest.fixture(autouse=True)
    def rm(self, straight_xodr, lib_dir):
        self._rm = _make_rm(straight_xodr, lib_dir)
        yield
        self._rm.close()

    def test_create_and_delete(self):
        h = self._rm.create_position()
        assert h >= 0
        assert self._rm.delete_position(h) >= 0

    def test_nr_of_positions(self):
        before = self._rm.get_nr_of_positions()
        h = self._rm.create_position()
        assert self._rm.get_nr_of_positions() == before + 1
        self._rm.delete_position(h)
        assert self._rm.get_nr_of_positions() == before

    def test_copy_position(self):
        h1 = self._rm.create_position()
        self._rm.set_lane_position(h1, road_id=1, lane_id=-1, lane_offset=0.0, s=100.0)
        h2 = self._rm.copy_position(h1)
        assert h2 >= 0
        d1 = self._rm.get_position_data(h1)
        d2 = self._rm.get_position_data(h2)
        assert d1 is not None and d2 is not None
        assert abs(d1.s - d2.s) < 1e-6
        self._rm.delete_position(h1)
        self._rm.delete_position(h2)


# ---------------------------------------------------------------------------
# Setting positions
# ---------------------------------------------------------------------------


@skip_no_rm_lib
class TestSetPosition:
    ROAD_ID = 1
    LANE_ID = -1
    S_VALUE = 50.0

    @pytest.fixture(autouse=True)
    def setup(self, straight_xodr, lib_dir):
        self._rm = _make_rm(straight_xodr, lib_dir)
        self._h = self._rm.create_position()
        yield
        self._rm.delete_position(self._h)
        self._rm.close()

    def test_set_lane_position(self):
        ret = self._rm.set_lane_position(
            self._h, self.ROAD_ID, self.LANE_ID, 0.0, self.S_VALUE
        )
        assert ret >= 0
        data = self._rm.get_position_data(self._h)
        assert data is not None
        assert abs(data.s - self.S_VALUE) < 1.0  # within 1 m (snap may shift)

    def test_set_world_position(self):
        # Set via lane first to get a world coordinate
        self._rm.set_lane_position(
            self._h, self.ROAD_ID, self.LANE_ID, 0.0, self.S_VALUE
        )
        data = self._rm.get_position_data(self._h)
        assert data is not None
        # Round-trip: set world position from the obtained coordinates
        ret = self._rm.set_world_position(
            self._h, data.x, data.y, data.z, data.h, data.p, data.r
        )
        assert ret >= 0

    def test_set_world_xyh_position(self):
        self._rm.set_lane_position(
            self._h, self.ROAD_ID, self.LANE_ID, 0.0, self.S_VALUE
        )
        data = self._rm.get_position_data(self._h)
        ret = self._rm.set_world_xyh_position(self._h, data.x, data.y, data.h)
        assert ret >= 0

    def test_set_s(self):
        self._rm.set_lane_position(self._h, self.ROAD_ID, self.LANE_ID, 0.0, 10.0)
        ret = self._rm.set_s(self._h, 200.0)
        assert ret >= 0
        data = self._rm.get_position_data(self._h)
        assert data is not None
        assert abs(data.s - 200.0) < 1.0

    def test_set_road_position(self):
        ret = self._rm.set_road_position(self._h, self.ROAD_ID, self.S_VALUE, 0.0)
        assert ret >= 0

    def test_set_h(self):
        self._rm.set_lane_position(
            self._h, self.ROAD_ID, self.LANE_ID, 0.0, self.S_VALUE
        )
        ret = self._rm.set_h(self._h, 1.0)
        assert ret >= 0


# ---------------------------------------------------------------------------
# Querying position data
# ---------------------------------------------------------------------------


@skip_no_rm_lib
class TestQueryPosition:
    @pytest.fixture(autouse=True)
    def setup(self, straight_xodr, lib_dir):
        self._rm = _make_rm(straight_xodr, lib_dir)
        self._h = self._rm.create_position()
        self._rm.set_lane_position(
            self._h, road_id=1, lane_id=-1, lane_offset=0.0, s=100.0
        )
        yield
        self._rm.delete_position(self._h)
        self._rm.close()

    def test_get_position_data_fields(self):
        data = self._rm.get_position_data(self._h)
        assert data is not None
        assert data.roadId == 1
        assert data.laneId == -1
        assert abs(data.s - 100.0) < 1.0
        assert not math.isnan(data.x)
        assert not math.isnan(data.y)

    def test_get_speed_limit(self):
        limit = self._rm.get_speed_limit(self._h)
        assert limit >= 0.0  # 0 means not set in ODR, still valid

    def test_get_lane_info(self):
        info = self._rm.get_lane_info(self._h, 10.0)
        assert info is not None
        assert not math.isnan(info.pos.x)
        assert not math.isnan(info.pos.y)

    def test_get_probe_info(self):
        probe = self._rm.get_probe_info(self._h, 20.0)
        assert probe is not None
        assert not math.isnan(probe.road_lane_info.pos.x)

    def test_get_lane_width(self):
        width = self._rm.get_lane_width(self._h, -1)
        assert width > 0.0

    def test_get_lane_width_by_road_id(self):
        width = self._rm.get_lane_width_by_road_id(road_id=1, lane_id=-1, s=100.0)
        assert width > 0.0

    def test_get_in_lane_type(self):
        ltype = self._rm.get_in_lane_type(self._h)
        # Type 2 = driving - any positive value indicates a valid lane type
        assert ltype > 0

    def test_get_lane_type_by_road_id(self):
        ltype = self._rm.get_lane_type_by_road_id(road_id=1, lane_id=-1, s=100.0)
        assert ltype > 0


# ---------------------------------------------------------------------------
# Position movement
# ---------------------------------------------------------------------------


@skip_no_rm_lib
class TestMovement:
    @pytest.fixture(autouse=True)
    def setup(self, straight_xodr, lib_dir):
        self._rm = _make_rm(straight_xodr, lib_dir)
        self._h = self._rm.create_position()
        self._rm.set_lane_position(
            self._h, road_id=1, lane_id=-1, lane_offset=0.0, s=50.0
        )
        yield
        self._rm.delete_position(self._h)
        self._rm.close()

    def test_move_forward(self):
        before = self._rm.get_position_data(self._h).s
        self._rm.position_move_forward(self._h, 30.0)
        after = self._rm.get_position_data(self._h).s
        assert after > before

    def test_subtract_a_from_b(self):
        h2 = self._rm.create_position()
        self._rm.set_lane_position(h2, road_id=1, lane_id=-1, lane_offset=0.0, s=100.0)
        diff = self._rm.subtract_a_from_b(self._h, h2)
        assert diff is not None
        assert diff.ds > 0  # h2 is ahead of self._h
        self._rm.delete_position(h2)


# ---------------------------------------------------------------------------
# Road signs
# ---------------------------------------------------------------------------


@skip_no_rm_lib
class TestRoadSigns:
    def test_signs_xodr(self, signs_xodr, lib_dir):
        with _make_rm(signs_xodr, lib_dir) as rm:
            road_id = rm.get_id_of_road_from_index(0)
            n = rm.get_number_of_road_signs(road_id)
            assert n >= 0  # may be 0 on the reference road
            if n > 0:
                sign = rm.get_road_sign(road_id, 0)
                assert sign is not None
                assert sign.id >= 0

    def test_sign_validity_records(self, signs_xodr, lib_dir):
        with _make_rm(signs_xodr, lib_dir) as rm:
            road_id = rm.get_id_of_road_from_index(0)
            n_signs = rm.get_number_of_road_signs(road_id)
            if n_signs == 0:
                pytest.skip("No road signs in this road - nothing to test")
            n_val = rm.get_number_of_road_sign_validity_records(road_id, 0)
            assert n_val >= 0
