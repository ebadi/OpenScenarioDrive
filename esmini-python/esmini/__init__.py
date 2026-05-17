# mypy: ignore-errors
"""
esmini Python wrapper - ctypes bindings for esminiLib and esminiRMLib.

Classes
-------
EsminiLib      : wraps libesminiLib  - full scenario simulation engine
RoadManagerLib : wraps libesminiRMLib - standalone road-network queries
SimpleVehicle  : context-manager helper around SE_SimpleVehicle*

Interoperability
----------------
After initialising EsminiLib, pass the loaded ODR file name to
RoadManagerLib so both libraries operate on the same road network:

    sim = EsminiLib.from_file("scenario.xosc", use_viewer=0)
    rm  = RoadManagerLib(sim.get_odr_filename())

"""

import ctypes
import os
import sys
from ctypes import (
    CFUNCTYPE,
    POINTER,
    Structure,
    byref,
    c_bool,
    c_char_p,
    c_double,
    c_int,
    c_ubyte,
    c_uint,
    c_ulonglong,
    c_void_p,
)

# ---------------------------------------------------------------------------
# Platform helpers
# ---------------------------------------------------------------------------


def _lib_suffix():
    if sys.platform in ("linux", "linux2"):
        return ".so"
    if sys.platform == "darwin":
        return ".dylib"
    if sys.platform == "win32":
        return ".dll"
    raise RuntimeError(f"Unsupported platform: {sys.platform}")


def _lib_path(lib_dir: str, stem: str) -> str:
    """Return the platform-appropriate shared-library path."""
    suffix = _lib_suffix()
    if sys.platform == "win32":
        return os.path.join(lib_dir, f"{stem}{suffix}")
    return os.path.join(lib_dir, f"lib{stem}{suffix}")


def _default_lib_dir() -> str:
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), "esmini")


_dll_dir_cookies: list = []  # keep os.add_dll_directory cookies alive


def _register_dll_dir(lib_dir: str) -> None:
    """Add lib_dir to the Windows DLL search path (no-op on other platforms).

    Without this, ctypes.CDLL loading of esminiRMLib.dll fails in frozen
    PyInstaller apps because the _internal/ bundle directory is not automatically
    on the Windows DLL search path for dependencies of dynamically loaded DLLs.
    """
    if sys.platform != "win32" or not hasattr(os, "add_dll_directory"):
        return
    try:
        cookie = os.add_dll_directory(os.path.abspath(lib_dir))
        _dll_dir_cookies.append(cookie)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# SE structs  (mirror esminiLib.hpp)
# ---------------------------------------------------------------------------


class ScenarioObjectState(Structure):
    """Mirror of SE_ScenarioObjectState."""

    _fields_ = [
        ("id", c_int),
        ("model_id", c_int),
        ("ctrl_type", c_int),
        ("timestamp", c_double),
        ("x", c_double),
        ("y", c_double),
        ("z", c_double),
        ("h", c_double),
        ("p", c_double),
        ("r", c_double),
        ("roadId", c_uint),
        ("junctionId", c_uint),
        ("t", c_double),
        ("laneId", c_int),
        ("laneOffset", c_double),
        ("s", c_double),
        ("speed", c_double),
        ("centerOffsetX", c_double),
        ("centerOffsetY", c_double),
        ("centerOffsetZ", c_double),
        ("width", c_double),
        ("length", c_double),
        ("height", c_double),
        ("objectType", c_int),
        ("objectCategory", c_int),
        ("wheel_angle", c_double),
        ("wheel_rot", c_double),
        ("visibilityMask", c_int),
    ]


class WheelData(Structure):
    """Mirror of SE_WheelData."""

    _fields_ = [
        ("x", c_double),
        ("y", c_double),
        ("z", c_double),
        ("h", c_double),
        ("p", c_double),
        ("wheel_radius", c_double),
        ("friction_coefficient", c_double),
        ("axle", c_int),
        ("index", c_int),
    ]


class RoadInfo(Structure):
    """Mirror of SE_RoadInfo."""

    _fields_ = [
        ("global_pos_x", c_double),
        ("global_pos_y", c_double),
        ("global_pos_z", c_double),
        ("local_pos_x", c_double),
        ("local_pos_y", c_double),
        ("local_pos_z", c_double),
        ("angle", c_double),
        ("road_heading", c_double),
        ("road_pitch", c_double),
        ("road_roll", c_double),
        ("trail_heading", c_double),
        ("curvature", c_double),
        ("speed_limit", c_double),
        ("roadId", c_uint),
        ("junctionId", c_uint),
        ("laneId", c_int),
        ("laneOffset", c_double),
        ("s", c_double),
        ("t", c_double),
        ("road_type", c_int),
        ("road_rule", c_int),
        ("lane_type", c_int),
        ("trail_wheel_angle", c_double),
    ]


class RouteInfo(Structure):
    """Mirror of SE_RouteInfo."""

    _fields_ = [
        ("x", c_double),
        ("y", c_double),
        ("z", c_double),
        ("h", c_double),
        ("roadId", c_uint),
        ("junctionId", c_uint),
        ("laneId", c_int),
        ("osiLaneId", c_int),
        ("laneOffset", c_double),
        ("s", c_double),
        ("t", c_double),
    ]


class LaneBoundaryId(Structure):
    """Mirror of SE_LaneBoundaryId."""

    _fields_ = [
        ("far_left_lb_id", c_uint),
        ("left_lb_id", c_uint),
        ("right_lb_id", c_uint),
        ("far_right_lb_id", c_uint),
    ]


class SEPositionDiff(Structure):
    """Mirror of SE_PositionDiff."""

    _fields_ = [
        ("ds", c_double),
        ("dt", c_double),
        ("dLaneId", c_int),
        ("dx", c_double),
        ("dy", c_double),
        ("oppositeLanes", c_bool),
    ]


class SimpleVehicleState(Structure):
    """Mirror of SE_SimpleVehicleState."""

    _fields_ = [
        ("x", c_double),
        ("y", c_double),
        ("z", c_double),
        ("h", c_double),
        ("p", c_double),
        ("speed", c_double),
        ("wheel_rotation", c_double),
        ("wheel_angle", c_double),
    ]


class SE_Center(Structure):
    _fields_ = [("x_", c_double), ("y_", c_double), ("z_", c_double)]


class SE_Dimensions(Structure):
    _fields_ = [("width_", c_double), ("length_", c_double), ("height_", c_double)]


class SE_OSCBoundingBox(Structure):
    """Mirror of SE_OSCBoundingBox."""

    _fields_ = [("center_", SE_Center), ("dimensions_", SE_Dimensions)]


class SE_RoadSign(Structure):
    """Mirror of SE_RoadSign."""

    _fields_ = [
        ("id", c_int),
        ("x", c_double),
        ("y", c_double),
        ("z", c_double),
        ("z_offset", c_double),
        ("h", c_double),
        ("roadId", c_int),
        ("s", c_double),
        ("t", c_double),
        ("name", c_char_p),
        ("orientation", c_int),
        ("length", c_double),
        ("height", c_double),
        ("width", c_double),
    ]


class SE_RoadObjValidity(Structure):
    _fields_ = [("fromLane", c_int), ("toLane", c_int)]


class SE_SpeedActionStruct(Structure):
    """Mirror of SE_SpeedActionStruct - used with inject_speed_action()."""

    _fields_ = [
        ("id", c_int),
        ("speed", c_double),
        ("transition_shape", c_int),
        ("transition_dim", c_int),
        ("transition_value", c_double),
    ]


class SE_LaneChangeActionStruct(Structure):
    """Mirror of SE_LaneChangeActionStruct - used with inject_lane_change_action()."""

    _fields_ = [
        ("id", c_int),
        ("mode", c_int),
        ("target", c_int),
        ("transition_shape", c_int),
        ("transition_dim", c_int),
        ("transition_value", c_double),
    ]


class SE_LaneOffsetActionStruct(Structure):
    """Mirror of SE_LaneOffsetActionStruct - used with inject_lane_offset_action()."""

    _fields_ = [
        ("id", c_int),
        ("offset", c_double),
        ("maxLateralAcc", c_double),
        ("transition_shape", c_int),
    ]


class SE_Image(Structure):
    """Mirror of SE_Image - returned by fetch_image()."""

    _fields_ = [
        ("width", c_int),
        ("height", c_int),
        ("pixelSize", c_int),
        ("pixelFormat", c_int),
        ("data", POINTER(c_ubyte)),
    ]


# Override-action status structs - layout must match C ABI exactly.
# bool fields are 1 byte; doubles follow standard platform alignment.
class _OverridePedals(Structure):
    _fields_ = [("active", c_bool), ("value", c_double), ("maxRate", c_double)]


class _OverrideBrake(Structure):
    _fields_ = [
        ("active", c_bool),
        ("type", c_int),
        ("value", c_double),
        ("maxRate", c_double),
        ("value_type", c_int),
    ]


class _OverrideSteering(Structure):
    _fields_ = [
        ("active", c_bool),
        ("value", c_double),
        ("maxRate", c_double),
        ("maxTorque", c_double),
    ]


class _OverrideGear(Structure):
    _fields_ = [
        ("active", c_bool),
        ("type", c_int),
        ("number", c_int),
        ("value_type", c_int),
    ]


class SE_OverrideActionList(Structure):
    """Mirror of SE_OverrideActionList."""

    _fields_ = [
        ("throttle", _OverridePedals),
        ("brake", _OverrideBrake),
        ("clutch", _OverridePedals),
        ("parkingBrake", _OverrideBrake),
        ("steeringWheel", _OverrideSteering),
        ("gear", _OverrideGear),
    ]


# ---------------------------------------------------------------------------
# RM structs  (mirror esminiRMLib.hpp)
# ---------------------------------------------------------------------------


class RM_PositionXYZ(Structure):
    _fields_ = [("x", c_double), ("y", c_double), ("z", c_double)]


class RM_PositionData(Structure):
    """Mirror of RM_PositionData."""

    _fields_ = [
        ("x", c_double),
        ("y", c_double),
        ("z", c_double),
        ("h", c_double),
        ("p", c_double),
        ("r", c_double),
        ("hRelative", c_double),
        ("roadId", c_uint),
        ("junctionId", c_uint),
        ("laneId", c_int),
        ("laneOffset", c_double),
        ("s", c_double),
    ]


class RM_RoadLaneInfo(Structure):
    """Mirror of RM_RoadLaneInfo."""

    _fields_ = [
        ("pos", RM_PositionXYZ),
        ("heading", c_double),
        ("pitch", c_double),
        ("roll", c_double),
        ("width", c_double),
        ("curvature", c_double),
        ("speed_limit", c_double),
        ("roadId", c_uint),
        ("junctionId", c_uint),
        ("laneId", c_int),
        ("laneOffset", c_double),
        ("s", c_double),
        ("t", c_double),
        ("road_type", c_int),
        ("road_rule", c_int),
        ("lane_type", c_int),
    ]


class RM_RoadProbeInfo(Structure):
    """Mirror of RM_RoadProbeInfo."""

    _fields_ = [
        ("road_lane_info", RM_RoadLaneInfo),
        ("relative_pos", RM_PositionXYZ),
        ("relative_h", c_double),
    ]


class RM_PositionDiff(Structure):
    """Mirror of RM_PositionDiff."""

    _fields_ = [
        ("ds", c_double),
        ("dt", c_double),
        ("dLaneId", c_int),
    ]


class RM_RoadSign(Structure):
    """Mirror of RM_RoadSign."""

    _fields_ = [
        ("id", c_int),
        ("x", c_double),
        ("y", c_double),
        ("z", c_double),
        ("z_offset", c_double),
        ("h", c_double),
        ("roadId", c_uint),
        ("s", c_double),
        ("t", c_double),
        ("name", c_char_p),
        ("orientation", c_int),
        ("length", c_double),
        ("height", c_double),
        ("width", c_double),
    ]


class RM_RoadObjValidity(Structure):
    _fields_ = [("fromLane", c_int), ("toLane", c_int)]


class RM_GeoReference(Structure):
    """Mirror of RM_GeoReference."""

    _fields_ = [
        ("a_", c_double),
        ("axis_", c_char_p),
        ("b_", c_double),
        ("ellps_", c_char_p),
        ("k_", c_double),
        ("k_0_", c_double),
        ("lat_0_", c_double),
        ("lon_0_", c_double),
        ("lon_wrap_", c_double),
        ("over_", c_double),
        ("pm_", c_char_p),
        ("proj_", c_char_p),
        ("units_", c_char_p),
        ("vunits_", c_char_p),
        ("x_0_", c_double),
        ("y_0_", c_double),
        ("datum_", c_char_p),
        ("geo_id_grids_", c_char_p),
        ("zone_", c_double),
        ("towgs84_", c_int),
        ("original_georef_str_", c_char_p),
    ]


# ---------------------------------------------------------------------------
# Constants / lookup tables
# ---------------------------------------------------------------------------

ELEMENT_TYPES = {
    0: "UNDEFINED",
    1: "STORY_BOARD",
    2: "STORY",
    3: "ACT",
    4: "MANEUVER_GROUP",
    5: "MANEUVER",
    6: "EVENT",
    7: "ACTION",
}

ELEMENT_STATES = {
    0: "UNDEFINED",
    1: "STANDBY",
    2: "RUNNING",
    3: "COMPLETE",
}

# SE_PositionMode bitmask values
SE_Z_SET = SE_Z_DEFAULT = 1
SE_Z_ABS = 3
SE_Z_REL = 7
SE_H_SET = SE_Z_SET << 4
SE_H_DEFAULT = SE_Z_DEFAULT << 4
SE_H_ABS = SE_Z_ABS << 4
SE_H_REL = SE_Z_REL << 4
SE_P_SET = SE_Z_SET << 8
SE_P_DEFAULT = SE_Z_DEFAULT << 8
SE_P_ABS = SE_Z_ABS << 8
SE_P_REL = SE_Z_REL << 8
SE_R_SET = SE_Z_SET << 12
SE_R_DEFAULT = SE_Z_DEFAULT << 12
SE_R_ABS = SE_Z_ABS << 12
SE_R_REL = SE_Z_REL << 12

# SE_PositionModeType
SE_MODE_SET = 1
SE_MODE_UPDATE = 2

# SE_RelativeDistanceType
REL_DIST_UNDEFINED = 0
REL_DIST_LATERAL = 1
REL_DIST_LONGITUDINAL = 2
REL_DIST_CARTESIAN = 3
REL_DIST_EUCLIDIAN = 4

# RM_PositionMode bitmask values
RM_Z_SET = RM_Z_DEFAULT = 1
RM_Z_ABS = 3
RM_Z_REL = 7
RM_H_SET = RM_Z_SET << 4
RM_H_DEFAULT = RM_Z_DEFAULT << 4
RM_H_ABS = RM_Z_ABS << 4
RM_H_REL = RM_Z_REL << 4

# ---------------------------------------------------------------------------
# ctypes callback signatures
# ---------------------------------------------------------------------------

_StoryboardCbType = CFUNCTYPE(None, c_char_p, c_int, c_int, c_char_p)
_ConditionCbType = CFUNCTYPE(None, c_char_p, c_double)
_ObjectCbType = CFUNCTYPE(None, POINTER(ScenarioObjectState), c_void_p)
_ParamDeclCbType = CFUNCTYPE(None, c_void_p)
_ImageCbType = CFUNCTYPE(None, POINTER(SE_Image), c_void_p)


# ---------------------------------------------------------------------------
# SimpleVehicle  (standalone helper)
# ---------------------------------------------------------------------------


class SimpleVehicle:
    """
    Wrapper around the SE_SimpleVehicle* 2-D bicycle kinematic model.

    Obtain via EsminiLib.create_simple_vehicle() - do not construct directly.
    Use as a context manager to guarantee deletion:

        with sim.create_simple_vehicle(x=0, y=0, h=0, length=4, speed=0) as sv:
            sv.control_analog(dt=0.05, throttle=1.0, steering=0.0)
            state = sv.get_state()
    """

    def __init__(self, handle: c_void_p, lib: ctypes.CDLL):
        self._handle = handle
        self._lib = lib

    # --- control ---

    def control_binary(self, dt: float, throttle: int, steering: int) -> None:
        """Discrete [-1, 0, 1] throttle and steering; steps the vehicle model."""
        self._lib.SE_SimpleVehicleControlBinary(self._handle, dt, throttle, steering)

    def control_analog(self, dt: float, throttle: float, steering: float) -> None:
        """Continuous [-1..1] throttle and steering; steps the vehicle model."""
        self._lib.SE_SimpleVehicleControlAnalog(self._handle, dt, throttle, steering)

    def control_acc_and_steer(
        self, dt: float, acceleration: float, steering_angle: float
    ) -> None:
        """Explicit acceleration (m/s²) and steering angle (rad); steps the model."""
        self._lib.SE_SimpleVehicleControlAccAndSteer(
            self._handle, dt, acceleration, steering_angle
        )

    def control_target(
        self, dt: float, target_speed: float, heading_to_target: float
    ) -> None:
        """Speed-target + heading-to-target controller; steps the model."""
        self._lib.SE_SimpleVehicleControlTarget(
            self._handle, dt, target_speed, heading_to_target
        )

    # --- state ---

    def get_state(self) -> SimpleVehicleState:
        state = SimpleVehicleState()
        self._lib.SE_SimpleVehicleGetState(self._handle, byref(state))
        return state

    # --- tuning ---

    def set_speed(self, speed: float) -> None:
        self._lib.SE_SimpleVehicleSetSpeed(self._handle, speed)

    def set_max_speed(self, speed: float) -> None:
        self._lib.SE_SimpleVehicleSetMaxSpeed(self._handle, speed)

    def set_max_acceleration(self, max_acc: float) -> None:
        self._lib.SE_SimpleVehicleSetMaxAcceleration(self._handle, max_acc)

    def set_max_deceleration(self, max_dec: float) -> None:
        self._lib.SE_SimpleVehicleSetMaxDeceleration(self._handle, max_dec)

    def set_engine_brake_factor(self, factor: float) -> None:
        self._lib.SE_SimpleVehicleSetEngineBrakeFactor(self._handle, factor)

    def set_steering_disabled(self, disabled: bool) -> None:
        self._lib.SE_SimpleVehicleSetSteeringDisabled(self._handle, disabled)

    def set_throttle_disabled(self, disabled: bool) -> None:
        self._lib.SE_SimpleVehicleSetThrottleDisabled(self._handle, disabled)

    # --- lifecycle ---

    def delete(self) -> None:
        if self._handle is not None:
            self._lib.SE_SimpleVehicleDelete(self._handle)
            self._handle = None

    def __del__(self):
        self.delete()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.delete()


# ---------------------------------------------------------------------------
# EsminiLib
# ---------------------------------------------------------------------------


class EsminiLib:
    """
    Python wrapper around libesminiLib.

    Headless simulation (most common API usage):

        with EsminiLib.from_file("cut-in.xosc", use_viewer=0) as sim:
            while not sim.get_quit_flag():
                sim.step_dt(0.05)
                state = sim.get_object_state(sim.get_id(0))
                print(f"t={sim.get_simulation_time():.2f}  x={state.x:.2f}")

    Legacy constructor (SE_InitWithArgs - accepts most esmini CLI flags):

        sim = EsminiLib("cut-in.xosc", use_viewer=False, disable_ctrls=True)
    """

    # ------------------------------------------------------------------ init

    def __init__(
        self,
        osc_file: str,
        disable_ctrls: bool = False,
        use_viewer: bool = False,
        threads: bool = False,
        record_file: str = "",
        lib_dir: str = None,
    ):
        """
        Initialise via SE_InitWithArgs (mirrors the esmini CLI).

        Parameters
        ----------
        osc_file       : Path to the OpenSCENARIO file.
        disable_ctrls  : Disable all controllers defined in the scenario.
        use_viewer     : Open a viewer window (requires OSG build).
        threads        : Run viewer in a separate thread.
        record_file    : Path to write a .dat recording ('' to disable).
        lib_dir        : Directory containing the esmini shared libraries.
                         Defaults to <this_script>/esmini/.
        """
        self._lib_dir = lib_dir or _default_lib_dir()
        _register_dll_dir(self._lib_dir)
        self._lib = ctypes.CDLL(_lib_path(self._lib_dir, "esminiLib"))
        self._declare_signatures()
        self._storyboard_cb = None
        self._condition_cb = None
        self._object_cbs = {}
        self._param_decl_cb = None
        self._image_cb = None

        args = ["esmini", "--osc", osc_file]
        if disable_ctrls:
            args.append("--disable_controllers")
        if threads:
            args.append("--threads")
        if record_file:
            args += ["--record", record_file]
        args += ["--window", "60", "60", "800", "400"] if use_viewer else ["--headless"]

        argv = (c_char_p * len(args))(*[a.encode() for a in args])
        if self._lib.SE_InitWithArgs(len(args), argv) < 0:
            raise RuntimeError(f"SE_InitWithArgs failed for {osc_file!r}")

        resources_dir = os.path.join(self._lib_dir, "resources")
        if os.path.isdir(resources_dir):
            self._lib.SE_AddPath(resources_dir.encode())

    @classmethod
    def from_file(
        cls,
        osc_file: str,
        disable_ctrls: int = 0,
        use_viewer: int = 0,
        threads: int = 0,
        record: int = 0,
        lib_dir: str = None,
        extra_paths: list = None,
        param_decl_fn=None,
    ) -> "EsminiLib":
        """
        Initialise using SE_Init() - simpler, direct interface.

        use_viewer bitmask: 0=headless, 1=window, 3=offscreen, 7=offscreen+capture.
        extra_paths: additional search directories (added BEFORE SE_Init).
        param_decl_fn: optional callable(sim) fired during SE_Init after
                       <ParameterDeclarations> is parsed but before the scenario
                       body is parsed - use it to override parameter values.
        """
        obj = cls.__new__(cls)
        obj._lib_dir = lib_dir or _default_lib_dir()
        obj._lib = ctypes.CDLL(_lib_path(obj._lib_dir, "esminiLib"))
        obj._declare_signatures()
        obj._storyboard_cb = None
        obj._condition_cb = None
        obj._object_cbs = {}
        obj._param_decl_cb = None
        obj._image_cb = None

        # Search paths must be set BEFORE SE_Init
        resources_dir = os.path.join(obj._lib_dir, "resources")
        if os.path.isdir(resources_dir):
            obj._lib.SE_AddPath(resources_dir.encode())
        for path in extra_paths or []:
            obj._lib.SE_AddPath(path.encode())

        # Register callback BEFORE SE_Init: fires after ParseParameterDeclarations()
        # but before ParseScenario(), so overrides are used when the scenario body runs.
        if param_decl_fn is not None:

            def _wrapper(_user_data):
                param_decl_fn(obj)

            obj._param_decl_cb = _ParamDeclCbType(_wrapper)
            obj._lib.SE_RegisterParameterDeclarationCallback(obj._param_decl_cb, None)

        ret = obj._lib.SE_Init(
            osc_file.encode(), disable_ctrls, use_viewer, threads, record
        )
        if ret < 0:
            raise RuntimeError(f"SE_Init failed for {osc_file!r}")
        return obj

    @classmethod
    def from_string(
        cls,
        xosc_xml: str,
        disable_ctrls: int = 0,
        use_viewer: int = 0,
        threads: int = 0,
        record: int = 0,
        lib_dir: str = None,
        extra_paths: list = None,
    ) -> "EsminiLib":
        """Initialise from an OpenSCENARIO XML string (SE_InitWithString)."""
        obj = cls.__new__(cls)
        obj._lib_dir = lib_dir or _default_lib_dir()
        obj._lib = ctypes.CDLL(_lib_path(obj._lib_dir, "esminiLib"))
        obj._declare_signatures()
        obj._storyboard_cb = None
        obj._condition_cb = None
        obj._object_cbs = {}
        obj._param_decl_cb = None
        obj._image_cb = None

        resources_dir = os.path.join(obj._lib_dir, "resources")
        if os.path.isdir(resources_dir):
            obj._lib.SE_AddPath(resources_dir.encode())
        for path in extra_paths or []:
            obj._lib.SE_AddPath(path.encode())

        ret = obj._lib.SE_InitWithString(
            xosc_xml.encode(), disable_ctrls, use_viewer, threads, record
        )
        if ret < 0:
            raise RuntimeError("SE_InitWithString failed - check the XML content")
        return obj

    # --------------------------------------------------------- context manager

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def __del__(self):
        try:
            self._lib.SE_Close()
        except Exception:
            pass

    # ---------------------------------------------------- ctypes declarations

    def _declare_signatures(self):  # noqa: C901  (intentionally long)
        lib = self._lib

        # --- init / teardown ---
        lib.SE_Init.argtypes = [c_char_p, c_int, c_int, c_int, c_int]
        lib.SE_Init.restype = c_int

        lib.SE_InitWithString.argtypes = [c_char_p, c_int, c_int, c_int, c_int]
        lib.SE_InitWithString.restype = c_int

        lib.SE_InitWithArgs.argtypes = [c_int, POINTER(c_char_p)]
        lib.SE_InitWithArgs.restype = c_int

        lib.SE_Close.argtypes = []
        lib.SE_Close.restype = None

        # --- paths & options ---
        lib.SE_AddPath.argtypes = [c_char_p]
        lib.SE_AddPath.restype = c_int

        lib.SE_ClearPaths.argtypes = []
        lib.SE_ClearPaths.restype = None

        lib.SE_SetLogFilePath.argtypes = [c_char_p]
        lib.SE_SetLogFilePath.restype = None

        lib.SE_SetDatFilePath.argtypes = [c_char_p]
        lib.SE_SetDatFilePath.restype = None

        lib.SE_SetOption.argtypes = [c_char_p]
        lib.SE_SetOption.restype = c_int

        lib.SE_UnsetOption.argtypes = [c_char_p]
        lib.SE_UnsetOption.restype = c_int

        lib.SE_SetOptionValue.argtypes = [c_char_p, c_char_p]
        lib.SE_SetOptionValue.restype = c_int

        lib.SE_GetOptionValue.argtypes = [c_char_p]
        lib.SE_GetOptionValue.restype = c_char_p

        lib.SE_GetOptionSet.argtypes = [c_char_p]
        lib.SE_GetOptionSet.restype = c_bool

        # --- seed ---
        lib.SE_GetSeed.argtypes = []
        lib.SE_GetSeed.restype = c_uint

        lib.SE_SetSeed.argtypes = [c_uint]
        lib.SE_SetSeed.restype = None

        # --- simulation control ---
        lib.SE_StepDT.argtypes = [c_double]
        lib.SE_StepDT.restype = c_int

        lib.SE_Step.argtypes = []
        lib.SE_Step.restype = c_int

        lib.SE_GetSimulationTime.argtypes = []
        lib.SE_GetSimulationTime.restype = c_double

        lib.SE_GetSimTimeStep.argtypes = []
        lib.SE_GetSimTimeStep.restype = c_double

        lib.SE_GetQuitFlag.argtypes = []
        lib.SE_GetQuitFlag.restype = c_int

        lib.SE_GetPauseFlag.argtypes = []
        lib.SE_GetPauseFlag.restype = c_int

        lib.SE_LogToConsole.argtypes = [c_bool]
        lib.SE_LogToConsole.restype = None

        lib.SE_CollisionDetection.argtypes = [c_bool]
        lib.SE_CollisionDetection.restype = None

        # --- file names ---
        lib.SE_GetODRFilename.argtypes = []
        lib.SE_GetODRFilename.restype = c_char_p

        lib.SE_GetSceneGraphFilename.argtypes = []
        lib.SE_GetSceneGraphFilename.restype = c_char_p

        # --- parameters ---
        lib.SE_GetNumberOfParameters.argtypes = []
        lib.SE_GetNumberOfParameters.restype = c_int

        lib.SE_GetParameterName.argtypes = [c_int, POINTER(c_int)]
        lib.SE_GetParameterName.restype = c_char_p

        lib.SE_GetParameterInt.argtypes = [c_char_p, POINTER(c_int)]
        lib.SE_GetParameterInt.restype = c_int

        lib.SE_GetParameterDouble.argtypes = [c_char_p, POINTER(c_double)]
        lib.SE_GetParameterDouble.restype = c_int

        lib.SE_GetParameterString.argtypes = [c_char_p, POINTER(c_char_p)]
        lib.SE_GetParameterString.restype = c_int

        lib.SE_GetParameterBool.argtypes = [c_char_p, POINTER(c_bool)]
        lib.SE_GetParameterBool.restype = c_int

        lib.SE_SetParameterInt.argtypes = [c_char_p, c_int]
        lib.SE_SetParameterInt.restype = c_int

        lib.SE_SetParameterDouble.argtypes = [c_char_p, c_double]
        lib.SE_SetParameterDouble.restype = c_int

        lib.SE_SetParameterString.argtypes = [c_char_p, c_char_p]
        lib.SE_SetParameterString.restype = c_int

        lib.SE_SetParameterBool.argtypes = [c_char_p, c_bool]
        lib.SE_SetParameterBool.restype = c_int

        # --- variables ---
        lib.SE_GetNumberOfVariables.argtypes = []
        lib.SE_GetNumberOfVariables.restype = c_int

        lib.SE_GetVariableName.argtypes = [c_int, POINTER(c_int)]
        lib.SE_GetVariableName.restype = c_char_p

        lib.SE_GetVariableInt.argtypes = [c_char_p, POINTER(c_int)]
        lib.SE_GetVariableInt.restype = c_int

        lib.SE_GetVariableDouble.argtypes = [c_char_p, POINTER(c_double)]
        lib.SE_GetVariableDouble.restype = c_int

        lib.SE_GetVariableString.argtypes = [c_char_p, POINTER(c_char_p)]
        lib.SE_GetVariableString.restype = c_int

        lib.SE_GetVariableBool.argtypes = [c_char_p, POINTER(c_bool)]
        lib.SE_GetVariableBool.restype = c_int

        lib.SE_SetVariableInt.argtypes = [c_char_p, c_int]
        lib.SE_SetVariableInt.restype = c_int

        lib.SE_SetVariableDouble.argtypes = [c_char_p, c_double]
        lib.SE_SetVariableDouble.restype = c_int

        lib.SE_SetVariableString.argtypes = [c_char_p, c_char_p]
        lib.SE_SetVariableString.restype = c_int

        lib.SE_SetVariableBool.argtypes = [c_char_p, c_bool]
        lib.SE_SetVariableBool.restype = c_int

        # --- object management ---
        lib.SE_GetNumberOfObjects.argtypes = []
        lib.SE_GetNumberOfObjects.restype = c_int

        lib.SE_GetId.argtypes = [c_int]
        lib.SE_GetId.restype = c_int

        lib.SE_GetIdByName.argtypes = [c_char_p]
        lib.SE_GetIdByName.restype = c_int

        lib.SE_GetObjectState.argtypes = [c_int, POINTER(ScenarioObjectState)]
        lib.SE_GetObjectState.restype = c_int

        lib.SE_GetObjectName.argtypes = [c_int]
        lib.SE_GetObjectName.restype = c_char_p

        lib.SE_GetObjectTypeName.argtypes = [c_int]
        lib.SE_GetObjectTypeName.restype = c_char_p

        lib.SE_GetObjectModelFileName.argtypes = [c_int]
        lib.SE_GetObjectModelFileName.restype = c_char_p

        lib.SE_GetObjectRouteStatus.argtypes = [c_int]
        lib.SE_GetObjectRouteStatus.restype = c_int

        lib.SE_GetObjectInLaneType.argtypes = [c_int]
        lib.SE_GetObjectInLaneType.restype = c_int

        lib.SE_ObjectHasGhost.argtypes = [c_int]
        lib.SE_ObjectHasGhost.restype = c_int

        lib.SE_GetObjectGhostId.argtypes = [c_int]
        lib.SE_GetObjectGhostId.restype = c_int

        lib.SE_GetObjectGhostState.argtypes = [c_int, POINTER(ScenarioObjectState)]
        lib.SE_GetObjectGhostState.restype = c_int

        lib.SE_GetObjectNumberOfCollisions.argtypes = [c_int]
        lib.SE_GetObjectNumberOfCollisions.restype = c_int

        lib.SE_GetObjectCollision.argtypes = [c_int, c_int]
        lib.SE_GetObjectCollision.restype = c_int

        lib.SE_GetObjectOdometer.argtypes = [c_int]
        lib.SE_GetObjectOdometer.restype = c_double

        lib.SE_GetObjectVelocityGlobalXYZ.argtypes = [
            c_int,
            POINTER(c_double),
            POINTER(c_double),
            POINTER(c_double),
        ]
        lib.SE_GetObjectVelocityGlobalXYZ.restype = c_int

        lib.SE_GetObjectAngularVelocity.argtypes = [
            c_int,
            POINTER(c_double),
            POINTER(c_double),
            POINTER(c_double),
        ]
        lib.SE_GetObjectAngularVelocity.restype = c_int

        lib.SE_GetObjectAngularAcceleration.argtypes = [
            c_int,
            POINTER(c_double),
            POINTER(c_double),
            POINTER(c_double),
        ]
        lib.SE_GetObjectAngularAcceleration.restype = c_int

        lib.SE_GetObjectAcceleration.argtypes = [c_int]
        lib.SE_GetObjectAcceleration.restype = c_double

        lib.SE_GetObjectAccelerationGlobalXYZ.argtypes = [
            c_int,
            POINTER(c_double),
            POINTER(c_double),
            POINTER(c_double),
        ]
        lib.SE_GetObjectAccelerationGlobalXYZ.restype = c_int

        lib.SE_GetObjectNumberOfWheels.argtypes = [c_int]
        lib.SE_GetObjectNumberOfWheels.restype = c_int

        lib.SE_GetObjectWheelData.argtypes = [c_int, c_int, POINTER(WheelData)]
        lib.SE_GetObjectWheelData.restype = c_int

        lib.SE_GetOverrideActionStatus.argtypes = [
            c_int,
            POINTER(SE_OverrideActionList),
        ]
        lib.SE_GetOverrideActionStatus.restype = c_int

        lib.SE_AddObject.argtypes = [c_char_p, c_int, c_int, c_int, c_int, c_char_p]
        lib.SE_AddObject.restype = c_int

        lib.SE_AddObjectWithBoundingBox.argtypes = [
            c_char_p,
            c_int,
            c_int,
            c_int,
            c_int,
            c_char_p,
            SE_OSCBoundingBox,
            c_int,
        ]
        lib.SE_AddObjectWithBoundingBox.restype = c_int

        lib.SE_DeleteObject.argtypes = [c_int]
        lib.SE_DeleteObject.restype = c_int

        # --- position reporting ---
        lib.SE_ReportObjectPos.argtypes = [
            c_int,
            c_double,
            c_double,
            c_double,
            c_double,
            c_double,
            c_double,
        ]
        lib.SE_ReportObjectPos.restype = c_int

        lib.SE_ReportObjectPosMode.argtypes = [
            c_int,
            c_double,
            c_double,
            c_double,
            c_double,
            c_double,
            c_double,
            c_int,
        ]
        lib.SE_ReportObjectPosMode.restype = c_int

        lib.SE_ReportObjectPosXYH.argtypes = [c_int, c_double, c_double, c_double]
        lib.SE_ReportObjectPosXYH.restype = c_int

        lib.SE_ReportObjectRoadPos.argtypes = [c_int, c_uint, c_int, c_double, c_double]
        lib.SE_ReportObjectRoadPos.restype = c_int

        lib.SE_ReportObjectSpeed.argtypes = [c_int, c_double]
        lib.SE_ReportObjectSpeed.restype = c_int

        lib.SE_ReportObjectLateralPosition.argtypes = [c_int, c_double]
        lib.SE_ReportObjectLateralPosition.restype = c_int

        lib.SE_ReportObjectLateralLanePosition.argtypes = [c_int, c_int, c_double]
        lib.SE_ReportObjectLateralLanePosition.restype = c_int

        lib.SE_ReportObjectVel.argtypes = [c_int, c_double, c_double, c_double]
        lib.SE_ReportObjectVel.restype = c_int

        lib.SE_ReportObjectAngularVel.argtypes = [c_int, c_double, c_double, c_double]
        lib.SE_ReportObjectAngularVel.restype = c_int

        lib.SE_ReportObjectAcc.argtypes = [c_int, c_double, c_double, c_double]
        lib.SE_ReportObjectAcc.restype = c_int

        lib.SE_ReportObjectAngularAcc.argtypes = [c_int, c_double, c_double, c_double]
        lib.SE_ReportObjectAngularAcc.restype = c_int

        lib.SE_ReportObjectWheelStatus.argtypes = [c_int, c_double, c_double]
        lib.SE_ReportObjectWheelStatus.restype = c_int

        lib.SE_SetSnapLaneTypes.argtypes = [c_int, c_int]
        lib.SE_SetSnapLaneTypes.restype = c_int

        lib.SE_SetLockOnLane.argtypes = [c_int, c_bool]
        lib.SE_SetLockOnLane.restype = c_int

        lib.SE_SetObjectPositionMode.argtypes = [c_int, c_int, c_int]
        lib.SE_SetObjectPositionMode.restype = None

        lib.SE_SetObjectPositionModeDefault.argtypes = [c_int, c_int]
        lib.SE_SetObjectPositionModeDefault.restype = None

        lib.SE_GetNumberOfProperties.argtypes = [c_int]
        lib.SE_GetNumberOfProperties.restype = c_int

        lib.SE_GetObjectPropertyName.argtypes = [c_int, c_int]
        lib.SE_GetObjectPropertyName.restype = c_char_p

        lib.SE_GetObjectPropertyValue.argtypes = [c_int, c_char_p]
        lib.SE_GetObjectPropertyValue.restype = c_char_p

        # --- road info ---
        lib.SE_GetRoadInfoAtDistance.argtypes = [
            c_int,
            c_double,
            POINTER(RoadInfo),
            c_int,
            c_bool,
        ]
        lib.SE_GetRoadInfoAtDistance.restype = c_int

        lib.SE_GetRoadInfoAlongRoute.argtypes = [
            c_int,
            c_double,
            POINTER(RoadInfo),
            c_int,
            c_bool,
        ]
        lib.SE_GetRoadInfoAlongRoute.restype = c_int

        lib.SE_GetRoadInfoAlongGhostTrail.argtypes = [
            c_int,
            c_double,
            POINTER(RoadInfo),
            POINTER(c_double),
            POINTER(c_double),
        ]
        lib.SE_GetRoadInfoAlongGhostTrail.restype = c_int

        lib.SE_GetRoadInfoGhostTrailTime.argtypes = [
            c_int,
            c_double,
            POINTER(RoadInfo),
            POINTER(c_double),
        ]
        lib.SE_GetRoadInfoGhostTrailTime.restype = c_int

        lib.SE_GetDistanceToObject.argtypes = [
            c_int,
            c_int,
            c_bool,
            POINTER(SEPositionDiff),
        ]
        lib.SE_GetDistanceToObject.restype = c_int

        lib.SE_SimpleGetDistanceToObject.argtypes = [
            c_int,
            c_int,
            c_int,
            c_double,
            POINTER(c_double),
            POINTER(c_double),
        ]
        lib.SE_SimpleGetDistanceToObject.restype = c_int

        lib.SE_GetSpeedUnit.argtypes = []
        lib.SE_GetSpeedUnit.restype = c_int

        # --- road signs ---
        lib.SE_GetNumberOfRoadSigns.argtypes = [c_uint]
        lib.SE_GetNumberOfRoadSigns.restype = c_uint

        lib.SE_GetRoadSign.argtypes = [c_uint, c_uint, POINTER(SE_RoadSign)]
        lib.SE_GetRoadSign.restype = c_int

        lib.SE_GetNumberOfRoadSignValidityRecords.argtypes = [c_uint, c_uint]
        lib.SE_GetNumberOfRoadSignValidityRecords.restype = c_uint

        lib.SE_GetRoadSignValidityRecord.argtypes = [
            c_uint,
            c_uint,
            c_uint,
            POINTER(SE_RoadObjValidity),
        ]
        lib.SE_GetRoadSignValidityRecord.restype = c_int

        lib.SE_GetRoadIdString.argtypes = [c_uint]
        lib.SE_GetRoadIdString.restype = c_char_p

        lib.SE_GetRoadIdFromString.argtypes = [c_char_p]
        lib.SE_GetRoadIdFromString.restype = c_uint

        lib.SE_GetJunctionIdString.argtypes = [c_uint]
        lib.SE_GetJunctionIdString.restype = c_char_p

        lib.SE_GetJunctionIdFromString.argtypes = [c_char_p]
        lib.SE_GetJunctionIdFromString.restype = c_uint

        # --- sensor ---
        lib.SE_AddObjectSensor.argtypes = [
            c_int,
            c_double,
            c_double,
            c_double,
            c_double,
            c_double,
            c_double,
            c_double,
            c_int,
        ]
        lib.SE_AddObjectSensor.restype = c_int

        lib.SE_GetNumberOfObjectSensors.argtypes = []
        lib.SE_GetNumberOfObjectSensors.restype = c_int

        lib.SE_ViewSensorData.argtypes = [c_int]
        lib.SE_ViewSensorData.restype = c_int

        lib.SE_FetchSensorObjectList.argtypes = [c_int, POINTER(c_int)]
        lib.SE_FetchSensorObjectList.restype = c_int

        # --- route ---
        lib.SE_GetNumberOfRoutePoints.argtypes = [c_int]
        lib.SE_GetNumberOfRoutePoints.restype = c_int

        lib.SE_GetRoutePoint.argtypes = [c_int, c_uint, POINTER(RouteInfo)]
        lib.SE_GetRoutePoint.restype = c_int

        lib.SE_GetRouteTotalLength.argtypes = [c_int]
        lib.SE_GetRouteTotalLength.restype = c_double

        # --- action injection ---
        lib.SE_InjectSpeedAction.argtypes = [POINTER(SE_SpeedActionStruct)]
        lib.SE_InjectSpeedAction.restype = None

        lib.SE_InjectLaneChangeAction.argtypes = [POINTER(SE_LaneChangeActionStruct)]
        lib.SE_InjectLaneChangeAction.restype = None

        lib.SE_InjectLaneOffsetAction.argtypes = [POINTER(SE_LaneOffsetActionStruct)]
        lib.SE_InjectLaneOffsetAction.restype = None

        lib.SE_InjectedActionOngoing.argtypes = [c_int]
        lib.SE_InjectedActionOngoing.restype = c_bool

        # --- OSI ---
        lib.SE_EnableOSIFile.argtypes = [c_char_p]
        lib.SE_EnableOSIFile.restype = None

        lib.SE_DisableOSIFile.argtypes = []
        lib.SE_DisableOSIFile.restype = None

        lib.SE_FlushOSIFile.argtypes = []
        lib.SE_FlushOSIFile.restype = None

        lib.SE_OSISetTimeStamp.argtypes = [c_ulonglong]
        lib.SE_OSISetTimeStamp.restype = c_int

        lib.SE_OpenOSISocket.argtypes = [c_char_p]
        lib.SE_OpenOSISocket.restype = c_int

        lib.SE_GetOSIGroundTruth.argtypes = [POINTER(c_int)]
        lib.SE_GetOSIGroundTruth.restype = c_char_p

        lib.SE_GetOSILaneBoundaryIds.argtypes = [c_int, POINTER(LaneBoundaryId)]
        lib.SE_GetOSILaneBoundaryIds.restype = None

        lib.SE_SetOSITolerances.argtypes = [c_double, c_double]
        lib.SE_SetOSITolerances.restype = c_int

        # --- viewer ---
        lib.SE_ViewerShowFeature.argtypes = [c_int, c_bool]
        lib.SE_ViewerShowFeature.restype = None

        lib.SE_SetCameraMode.argtypes = [c_int]
        lib.SE_SetCameraMode.restype = c_int

        lib.SE_SetCameraObjectFocus.argtypes = [c_int]
        lib.SE_SetCameraObjectFocus.restype = c_int

        lib.SE_GetObjectInCameraFocus.argtypes = []
        lib.SE_GetObjectInCameraFocus.restype = c_int

        lib.SE_GetCameraPos.argtypes = [
            POINTER(c_double),
            POINTER(c_double),
            POINTER(c_double),
            POINTER(c_double),
            POINTER(c_double),
            POINTER(c_double),
        ]
        lib.SE_GetCameraPos.restype = c_int

        lib.SE_AddCustomCamera.argtypes = [
            c_double,
            c_double,
            c_double,
            c_double,
            c_double,
        ]
        lib.SE_AddCustomCamera.restype = c_int

        lib.SE_AddCustomFixedCamera.argtypes = [
            c_double,
            c_double,
            c_double,
            c_double,
            c_double,
        ]
        lib.SE_AddCustomFixedCamera.restype = c_int

        lib.SE_AddCustomAimingCamera.argtypes = [c_double, c_double, c_double]
        lib.SE_AddCustomAimingCamera.restype = c_int

        lib.SE_AddCustomFixedAimingCamera.argtypes = [c_double, c_double, c_double]
        lib.SE_AddCustomFixedAimingCamera.restype = c_int

        lib.SE_AddCustomFixedTopCamera.argtypes = [
            c_double,
            c_double,
            c_double,
            c_double,
        ]
        lib.SE_AddCustomFixedTopCamera.restype = c_int

        # --- image capture ---
        lib.SE_SaveImagesToRAM.argtypes = [c_bool]
        lib.SE_SaveImagesToRAM.restype = c_int

        lib.SE_SaveImagesToFile.argtypes = [c_int]
        lib.SE_SaveImagesToFile.restype = c_int

        lib.SE_FetchImage.argtypes = [POINTER(SE_Image)]
        lib.SE_FetchImage.restype = c_int

        # --- simple vehicle ---
        lib.SE_SimpleVehicleCreate.argtypes = [
            c_double,
            c_double,
            c_double,
            c_double,
            c_double,
        ]
        lib.SE_SimpleVehicleCreate.restype = c_void_p

        lib.SE_SimpleVehicleDelete.argtypes = [c_void_p]
        lib.SE_SimpleVehicleDelete.restype = None

        lib.SE_SimpleVehicleControlBinary.argtypes = [c_void_p, c_double, c_int, c_int]
        lib.SE_SimpleVehicleControlBinary.restype = None

        lib.SE_SimpleVehicleControlAnalog.argtypes = [
            c_void_p,
            c_double,
            c_double,
            c_double,
        ]
        lib.SE_SimpleVehicleControlAnalog.restype = None

        lib.SE_SimpleVehicleControlAccAndSteer.argtypes = [
            c_void_p,
            c_double,
            c_double,
            c_double,
        ]
        lib.SE_SimpleVehicleControlAccAndSteer.restype = None

        lib.SE_SimpleVehicleControlTarget.argtypes = [
            c_void_p,
            c_double,
            c_double,
            c_double,
        ]
        lib.SE_SimpleVehicleControlTarget.restype = None

        lib.SE_SimpleVehicleSetThrottleDisabled.argtypes = [c_void_p, c_bool]
        lib.SE_SimpleVehicleSetThrottleDisabled.restype = None

        lib.SE_SimpleVehicleSetSteeringDisabled.argtypes = [c_void_p, c_bool]
        lib.SE_SimpleVehicleSetSteeringDisabled.restype = None

        lib.SE_SimpleVehicleSetSpeed.argtypes = [c_void_p, c_double]
        lib.SE_SimpleVehicleSetSpeed.restype = None

        lib.SE_SimpleVehicleSetMaxSpeed.argtypes = [c_void_p, c_double]
        lib.SE_SimpleVehicleSetMaxSpeed.restype = None

        lib.SE_SimpleVehicleSetMaxAcceleration.argtypes = [c_void_p, c_double]
        lib.SE_SimpleVehicleSetMaxAcceleration.restype = None

        lib.SE_SimpleVehicleSetMaxDeceleration.argtypes = [c_void_p, c_double]
        lib.SE_SimpleVehicleSetMaxDeceleration.restype = None

        lib.SE_SimpleVehicleSetEngineBrakeFactor.argtypes = [c_void_p, c_double]
        lib.SE_SimpleVehicleSetEngineBrakeFactor.restype = None

        lib.SE_SimpleVehicleGetState.argtypes = [c_void_p, POINTER(SimpleVehicleState)]
        lib.SE_SimpleVehicleGetState.restype = None

        # --- callbacks ---
        lib.SE_RegisterStoryBoardElementStateChangeCallback.argtypes = [
            _StoryboardCbType
        ]
        lib.SE_RegisterStoryBoardElementStateChangeCallback.restype = None

        lib.SE_RegisterConditionCallback.argtypes = [_ConditionCbType]
        lib.SE_RegisterConditionCallback.restype = None

        lib.SE_RegisterObjectCallback.argtypes = [c_int, _ObjectCbType, c_void_p]
        lib.SE_RegisterObjectCallback.restype = None

        lib.SE_RegisterParameterDeclarationCallback.argtypes = [
            _ParamDeclCbType,
            c_void_p,
        ]
        lib.SE_RegisterParameterDeclarationCallback.restype = None

        lib.SE_RegisterImageCallback.argtypes = [_ImageCbType, c_void_p]
        lib.SE_RegisterImageCallback.restype = None

        # --- logging ---
        lib.SE_LogMessage.argtypes = [c_char_p]
        lib.SE_LogMessage.restype = None

        lib.SE_CloseLogFile.argtypes = []
        lib.SE_CloseLogFile.restype = None

        # --- parameter distribution ---
        lib.SE_SetParameterDistribution.argtypes = [c_char_p]
        lib.SE_SetParameterDistribution.restype = c_int

        lib.SE_ResetParameterDistribution.argtypes = []
        lib.SE_ResetParameterDistribution.restype = None

        lib.SE_GetNumberOfPermutations.argtypes = []
        lib.SE_GetNumberOfPermutations.restype = c_uint

        lib.SE_SelectPermutation.argtypes = [c_uint]
        lib.SE_SelectPermutation.restype = c_int

        lib.SE_GetPermutationIndex.argtypes = []
        lib.SE_GetPermutationIndex.restype = c_int

        lib.SE_SetWindowPosAndSize.argtypes = [c_int, c_int, c_int, c_int]
        lib.SE_SetWindowPosAndSize.restype = None

    # -------------------------------------------------------------- wrappers

    # --- lifecycle ---

    def close(self) -> None:
        self._lib.SE_Close()

    def step(self) -> bool:
        """Step using elapsed wall-clock time. Returns True while simulation is active."""
        return self._lib.SE_Step() >= 0

    def step_dt(self, dt: float) -> int:
        """Step with explicit timestep *dt* (seconds). Returns 0 on success, -1 on end."""
        return self._lib.SE_StepDT(dt)

    # --- time ---

    def get_simulation_time(self) -> float:
        return self._lib.SE_GetSimulationTime()

    def get_simulation_time_step(self) -> float:
        return self._lib.SE_GetSimTimeStep()

    def get_quit_flag(self) -> int:
        """0=not done, 1=done, -1=error."""
        return self._lib.SE_GetQuitFlag()

    def get_pause_flag(self) -> int:
        return self._lib.SE_GetPauseFlag()

    # --- config ---

    def set_log_file_path(self, path: str) -> None:
        self._lib.SE_SetLogFilePath(path.encode())

    def set_dat_file_path(self, path: str) -> None:
        self._lib.SE_SetDatFilePath(path.encode())

    def add_path(self, path: str) -> int:
        return self._lib.SE_AddPath(path.encode())

    def clear_paths(self) -> None:
        self._lib.SE_ClearPaths()

    def log_to_console(self, mode: bool) -> None:
        self._lib.SE_LogToConsole(mode)

    def log_message(self, message: str) -> None:
        self._lib.SE_LogMessage(message.encode())

    def collision_detection(self, mode: bool) -> None:
        self._lib.SE_CollisionDetection(mode)

    def get_seed(self) -> int:
        return self._lib.SE_GetSeed()

    def set_seed(self, seed: int) -> None:
        self._lib.SE_SetSeed(seed)

    def set_option(self, name: str) -> int:
        return self._lib.SE_SetOption(name.encode())

    def unset_option(self, name: str) -> int:
        return self._lib.SE_UnsetOption(name.encode())

    def set_option_value(self, name: str, value: str) -> int:
        return self._lib.SE_SetOptionValue(name.encode(), value.encode())

    def get_option_value(self, name: str) -> str:
        result = self._lib.SE_GetOptionValue(name.encode())
        return result.decode() if result else ""

    def get_option_set(self, name: str) -> bool:
        return self._lib.SE_GetOptionSet(name.encode())

    # --- filenames ---

    def get_odr_filename(self) -> str:
        """Return the OpenDRIVE file name loaded by the current scenario."""
        result = self._lib.SE_GetODRFilename()
        return result.decode() if result else ""

    def get_scene_graph_filename(self) -> str:
        result = self._lib.SE_GetSceneGraphFilename()
        return result.decode() if result else ""

    # --- parameters ---

    def get_number_of_parameters(self) -> int:
        return self._lib.SE_GetNumberOfParameters()

    def get_parameter_name(self, index: int) -> tuple:
        """Returns (name, type_int). type: 1=int, 2=double, 3=str, 4=bool."""
        ptype = c_int()
        name = self._lib.SE_GetParameterName(index, byref(ptype))
        return (name.decode() if name else "", ptype.value)

    def get_parameter_int(self, name: str) -> int:
        val = c_int()
        if self._lib.SE_GetParameterInt(name.encode(), byref(val)) < 0:
            raise KeyError(name)
        return val.value

    def get_parameter_double(self, name: str) -> float:
        val = c_double()
        if self._lib.SE_GetParameterDouble(name.encode(), byref(val)) < 0:
            raise KeyError(name)
        return val.value

    def get_parameter_string(self, name: str) -> str:
        val = c_char_p()
        if self._lib.SE_GetParameterString(name.encode(), byref(val)) < 0:
            raise KeyError(name)
        return val.value.decode() if val.value else ""

    def get_parameter_bool(self, name: str) -> bool:
        val = c_bool()
        if self._lib.SE_GetParameterBool(name.encode(), byref(val)) < 0:
            raise KeyError(name)
        return bool(val.value)

    def set_parameter_int(self, name: str, value: int) -> int:
        return self._lib.SE_SetParameterInt(name.encode(), value)

    def set_parameter_double(self, name: str, value: float) -> int:
        return self._lib.SE_SetParameterDouble(name.encode(), value)

    def set_parameter_string(self, name: str, value: str) -> int:
        return self._lib.SE_SetParameterString(name.encode(), value.encode())

    def set_parameter_bool(self, name: str, value: bool) -> int:
        return self._lib.SE_SetParameterBool(name.encode(), value)

    # --- variables ---

    def get_number_of_variables(self) -> int:
        return self._lib.SE_GetNumberOfVariables()

    def get_variable_int(self, name: str) -> int:
        val = c_int()
        if self._lib.SE_GetVariableInt(name.encode(), byref(val)) < 0:
            raise KeyError(name)
        return val.value

    def get_variable_double(self, name: str) -> float:
        val = c_double()
        if self._lib.SE_GetVariableDouble(name.encode(), byref(val)) < 0:
            raise KeyError(name)
        return val.value

    def set_variable_int(self, name: str, value: int) -> int:
        return self._lib.SE_SetVariableInt(name.encode(), value)

    def set_variable_double(self, name: str, value: float) -> int:
        return self._lib.SE_SetVariableDouble(name.encode(), value)

    # --- objects ---

    def get_number_of_objects(self) -> int:
        return self._lib.SE_GetNumberOfObjects()

    def get_id(self, index: int) -> int:
        """Return the object ID for a given 0-based index."""
        return self._lib.SE_GetId(index)

    def get_id_by_name(self, name: str) -> int:
        return self._lib.SE_GetIdByName(name.encode())

    def get_object_state(self, object_id: int) -> ScenarioObjectState:
        state = ScenarioObjectState()
        if self._lib.SE_GetObjectState(object_id, byref(state)) < 0:
            raise RuntimeError(f"SE_GetObjectState failed for object_id {object_id}")
        return state

    def get_object_state_by_index(self, index: int) -> ScenarioObjectState:
        """Convenience: look up by index rather than by ID."""
        return self.get_object_state(self.get_id(index))

    def get_object_name(self, object_id: int) -> str:
        result = self._lib.SE_GetObjectName(object_id)
        return result.decode() if result else ""

    def get_object_type_name(self, object_id: int) -> str:
        result = self._lib.SE_GetObjectTypeName(object_id)
        return result.decode() if result else ""

    def get_object_model_filename(self, object_id: int) -> str:
        result = self._lib.SE_GetObjectModelFileName(object_id)
        return result.decode() if result else ""

    def get_object_route_status(self, object_id: int) -> int:
        return self._lib.SE_GetObjectRouteStatus(object_id)

    def get_object_in_lane_type(self, object_id: int) -> int:
        return self._lib.SE_GetObjectInLaneType(object_id)

    def object_has_ghost(self, object_id: int) -> bool:
        return self._lib.SE_ObjectHasGhost(object_id) == 1

    def get_object_ghost_id(self, object_id: int) -> int:
        return self._lib.SE_GetObjectGhostId(object_id)

    def get_object_ghost_state(self, object_id: int) -> ScenarioObjectState:
        state = ScenarioObjectState()
        if self._lib.SE_GetObjectGhostState(object_id, byref(state)) < 0:
            raise RuntimeError(
                f"SE_GetObjectGhostState failed for object_id {object_id}"
            )
        return state

    def get_object_number_of_collisions(self, object_id: int) -> int:
        return self._lib.SE_GetObjectNumberOfCollisions(object_id)

    def get_object_collision(self, object_id: int, index: int) -> int:
        return self._lib.SE_GetObjectCollision(object_id, index)

    def get_object_odometer(self, object_id: int) -> float:
        return self._lib.SE_GetObjectOdometer(object_id)

    def get_object_velocity_global_xyz(self, object_id: int) -> tuple:
        """Returns (vx, vy, vz) in m/s."""
        vx, vy, vz = c_double(), c_double(), c_double()
        self._lib.SE_GetObjectVelocityGlobalXYZ(
            object_id, byref(vx), byref(vy), byref(vz)
        )
        return (vx.value, vy.value, vz.value)

    def get_object_angular_velocity(self, object_id: int) -> tuple:
        """Returns (h_rate, p_rate, r_rate) in rad/s."""
        h, p, r = c_double(), c_double(), c_double()
        self._lib.SE_GetObjectAngularVelocity(object_id, byref(h), byref(p), byref(r))
        return (h.value, p.value, r.value)

    def get_object_acceleration(self, object_id: int) -> float:
        return self._lib.SE_GetObjectAcceleration(object_id)

    def get_object_acceleration_global_xyz(self, object_id: int) -> tuple:
        ax, ay, az = c_double(), c_double(), c_double()
        self._lib.SE_GetObjectAccelerationGlobalXYZ(
            object_id, byref(ax), byref(ay), byref(az)
        )
        return (ax.value, ay.value, az.value)

    def get_object_number_of_wheels(self, object_id: int) -> int:
        return self._lib.SE_GetObjectNumberOfWheels(object_id)

    def get_object_wheel_data(self, object_id: int, wheel_index: int) -> WheelData:
        wd = WheelData()
        if self._lib.SE_GetObjectWheelData(object_id, wheel_index, byref(wd)) < 0:
            raise RuntimeError(
                f"SE_GetObjectWheelData failed for obj={object_id} wheel={wheel_index}"
            )
        return wd

    def get_number_of_properties(self, object_id: int) -> int:
        return self._lib.SE_GetNumberOfProperties(object_id)

    def get_object_property_name(self, object_id: int, prop_index: int) -> str:
        result = self._lib.SE_GetObjectPropertyName(object_id, prop_index)
        return result.decode() if result else ""

    def get_object_property_value(self, object_id: int, prop_name: str) -> str:
        result = self._lib.SE_GetObjectPropertyValue(object_id, prop_name.encode())
        return result.decode() if result else ""

    # --- add / delete objects ---

    def add_object(
        self,
        name: str,
        obj_type: int = 1,
        category: int = 0,
        role: int = 0,
        model_id: int = -1,
        model_3d: str = None,
    ) -> int:
        return self._lib.SE_AddObject(
            name.encode(),
            obj_type,
            category,
            role,
            model_id,
            model_3d.encode() if model_3d else None,
        )

    def delete_object(self, object_id: int) -> int:
        return self._lib.SE_DeleteObject(object_id)

    # --- position reporting ---

    def report_object_pos(
        self,
        object_id: int,
        x: float,
        y: float,
        z: float,
        h: float,
        p: float,
        r: float,
    ) -> int:
        return self._lib.SE_ReportObjectPos(object_id, x, y, z, h, p, r)

    def report_object_pos_xyh(
        self, object_id: int, x: float, y: float, h: float
    ) -> int:
        """Report x, y, heading - z/pitch/roll are aligned to the road surface."""
        return self._lib.SE_ReportObjectPosXYH(object_id, x, y, h)

    def report_object_road_pos(
        self,
        object_id: int,
        road_id: int,
        lane_id: int,
        lane_offset: float,
        s: float,
    ) -> int:
        return self._lib.SE_ReportObjectRoadPos(
            object_id, road_id, lane_id, lane_offset, s
        )

    def report_object_speed(self, object_id: int, speed: float) -> int:
        return self._lib.SE_ReportObjectSpeed(object_id, speed)

    def report_object_lateral_position(self, object_id: int, t: float) -> int:
        return self._lib.SE_ReportObjectLateralPosition(object_id, t)

    def report_object_lateral_lane_position(
        self,
        object_id: int,
        lane_id: int,
        lane_offset: float,
    ) -> int:
        return self._lib.SE_ReportObjectLateralLanePosition(
            object_id, lane_id, lane_offset
        )

    def report_object_vel(
        self, object_id: int, x_vel: float, y_vel: float, z_vel: float
    ) -> int:
        return self._lib.SE_ReportObjectVel(object_id, x_vel, y_vel, z_vel)

    def report_object_angular_vel(
        self,
        object_id: int,
        h_rate: float,
        p_rate: float,
        r_rate: float,
    ) -> int:
        return self._lib.SE_ReportObjectAngularVel(object_id, h_rate, p_rate, r_rate)

    def report_object_acc(
        self, object_id: int, x_acc: float, y_acc: float, z_acc: float
    ) -> int:
        return self._lib.SE_ReportObjectAcc(object_id, x_acc, y_acc, z_acc)

    def report_object_wheel_status(
        self, object_id: int, rotation: float, angle: float
    ) -> int:
        return self._lib.SE_ReportObjectWheelStatus(object_id, rotation, angle)

    def set_snap_lane_types(self, object_id: int, lane_types: int) -> int:
        return self._lib.SE_SetSnapLaneTypes(object_id, lane_types)

    def set_lock_on_lane(self, object_id: int, mode: bool) -> int:
        return self._lib.SE_SetLockOnLane(object_id, mode)

    def set_object_position_mode(
        self, object_id: int, mode_type: int, mode: int
    ) -> None:
        self._lib.SE_SetObjectPositionMode(object_id, mode_type, mode)

    # --- road info ---

    def get_road_info_at_distance(
        self,
        object_id: int,
        lookahead_distance: float,
        look_ahead_mode: int = 0,
        in_driving_direction: bool = True,
    ):
        """
        Return RoadInfo for a point *lookahead_distance* ahead along the road,
        or None if the call fails.

        look_ahead_mode: 0=lane centre, 1=road centre (ref line), 2=current offset.
        """
        info = RoadInfo()
        ret = self._lib.SE_GetRoadInfoAtDistance(
            object_id,
            lookahead_distance,
            byref(info),
            look_ahead_mode,
            in_driving_direction,
        )
        return info if ret >= 0 else None

    def get_road_info_along_route(
        self,
        object_id: int,
        lookahead_distance: float,
        look_ahead_mode: int = 0,
        in_driving_direction: bool = True,
    ):
        info = RoadInfo()
        ret = self._lib.SE_GetRoadInfoAlongRoute(
            object_id,
            lookahead_distance,
            byref(info),
            look_ahead_mode,
            in_driving_direction,
        )
        return info if ret >= 0 else None

    def get_distance_to_object(
        self,
        object_a_id: int,
        object_b_id: int,
        free_space: bool = False,
    ):
        """Return SEPositionDiff or None on failure."""
        diff = SEPositionDiff()
        ret = self._lib.SE_GetDistanceToObject(
            object_a_id, object_b_id, free_space, byref(diff)
        )
        return diff if ret >= 0 else None

    def get_speed_unit(self) -> int:
        """-1=error, 0=undefined, 1=km/h, 2=m/s, 3=mph."""
        return self._lib.SE_GetSpeedUnit()

    # --- road signs ---

    def get_number_of_road_signs(self, road_id: int) -> int:
        return self._lib.SE_GetNumberOfRoadSigns(road_id)

    def get_road_sign(self, road_id: int, index: int):
        sign = SE_RoadSign()
        if self._lib.SE_GetRoadSign(road_id, index, byref(sign)) < 0:
            return None
        return sign

    def get_road_sign_validity_records_count(
        self, road_id: int, sign_index: int
    ) -> int:
        return self._lib.SE_GetNumberOfRoadSignValidityRecords(road_id, sign_index)

    def get_road_sign_validity_record(
        self,
        road_id: int,
        sign_index: int,
        validity_index: int,
    ):
        validity = SE_RoadObjValidity()
        if (
            self._lib.SE_GetRoadSignValidityRecord(
                road_id, sign_index, validity_index, byref(validity)
            )
            < 0
        ):
            return None
        return validity

    def get_road_id_string(self, road_id: int) -> str:
        result = self._lib.SE_GetRoadIdString(road_id)
        return result.decode() if result else ""

    def get_road_id_from_string(self, road_id_str: str) -> int:
        return self._lib.SE_GetRoadIdFromString(road_id_str.encode())

    # --- sensor ---

    def add_object_sensor(
        self,
        object_id: int,
        x: float,
        y: float,
        z: float,
        h: float,
        range_near: float,
        range_far: float,
        fov_h: float,
        max_obj: int,
    ) -> int:
        return self._lib.SE_AddObjectSensor(
            object_id, x, y, z, h, range_near, range_far, fov_h, max_obj
        )

    def get_number_of_object_sensors(self) -> int:
        return self._lib.SE_GetNumberOfObjectSensors()

    def fetch_sensor_object_list(self, sensor_id: int) -> list:
        """Return list of object IDs detected by sensor *sensor_id*."""
        buf = (c_int * 100)()
        n = self._lib.SE_FetchSensorObjectList(sensor_id, buf)
        return list(buf[: max(n, 0)])

    # --- route ---

    def get_number_of_route_points(self, object_id: int) -> int:
        return self._lib.SE_GetNumberOfRoutePoints(object_id)

    def get_route_point(self, object_id: int, route_index: int):
        info = RouteInfo()
        if self._lib.SE_GetRoutePoint(object_id, route_index, byref(info)) < 0:
            return None
        return info

    def get_route_total_length(self, object_id: int) -> float:
        return self._lib.SE_GetRouteTotalLength(object_id)

    # --- action injection ---

    def inject_speed_action(self, action: SE_SpeedActionStruct) -> None:
        self._lib.SE_InjectSpeedAction(byref(action))

    def inject_lane_change_action(self, action: SE_LaneChangeActionStruct) -> None:
        self._lib.SE_InjectLaneChangeAction(byref(action))

    def inject_lane_offset_action(self, action: SE_LaneOffsetActionStruct) -> None:
        self._lib.SE_InjectLaneOffsetAction(byref(action))

    def injected_action_ongoing(self, action_type: int = -1) -> bool:
        return bool(self._lib.SE_InjectedActionOngoing(action_type))

    # --- OSI ---

    def osi_file_open(self, filename: str = "") -> None:
        self._lib.SE_EnableOSIFile(filename.encode() if filename else b"")

    def osi_file_close(self) -> None:
        self._lib.SE_DisableOSIFile()

    def osi_file_flush(self) -> None:
        self._lib.SE_FlushOSIFile()

    def osi_set_timestamp(self, nanoseconds: int) -> int:
        return self._lib.SE_OSISetTimeStamp(nanoseconds)

    def get_osi_ground_truth(self) -> bytes:
        """Return serialised OSI GroundTruth protobuf bytes."""
        size = c_int()
        data = self._lib.SE_GetOSIGroundTruth(byref(size))
        if data is None or size.value <= 0:
            return b""
        return bytes(
            (c_ubyte * size.value).from_address(ctypes.addressof(data.contents))
            if hasattr(data, "contents")
            else b""
        )

    def get_osi_lane_boundary_ids(self, object_id: int) -> LaneBoundaryId:
        ids = LaneBoundaryId()
        self._lib.SE_GetOSILaneBoundaryIds(object_id, byref(ids))
        return ids

    def set_osi_tolerances(self, max_longitudinal: float, max_lateral: float) -> int:
        return self._lib.SE_SetOSITolerances(max_longitudinal, max_lateral)

    # --- viewer ---

    def viewer_show_feature(self, feature_type: int, enable: bool) -> None:
        self._lib.SE_ViewerShowFeature(feature_type, enable)

    def set_camera_mode(self, mode: int) -> int:
        return self._lib.SE_SetCameraMode(mode)

    def set_camera_object_focus(self, object_id: int) -> int:
        return self._lib.SE_SetCameraObjectFocus(object_id)

    def get_object_in_camera_focus(self) -> int:
        return self._lib.SE_GetObjectInCameraFocus()

    def get_camera_pos(self) -> tuple:
        """Returns (x, y, z, h, p, r)."""
        x, y, z, h, p, r = (c_double() for _ in range(6))
        self._lib.SE_GetCameraPos(
            byref(x), byref(y), byref(z), byref(h), byref(p), byref(r)
        )
        return (x.value, y.value, z.value, h.value, p.value, r.value)

    # --- simple vehicle factory ---

    def create_simple_vehicle(
        self,
        x: float,
        y: float,
        h: float,
        length: float,
        speed: float,
    ) -> SimpleVehicle:
        """Allocate a 2-D bicycle model. Caller owns it; use as context manager."""
        handle = self._lib.SE_SimpleVehicleCreate(x, y, h, length, speed)
        if handle is None:
            raise RuntimeError("SE_SimpleVehicleCreate returned NULL")
        return SimpleVehicle(handle, self._lib)

    # --- image capture ---

    def save_images_to_ram(self, state: bool) -> int:
        return self._lib.SE_SaveImagesToRAM(state)

    def save_images_to_file(self, nr_of_frames: int) -> int:
        return self._lib.SE_SaveImagesToFile(nr_of_frames)

    def fetch_image(self) -> SE_Image:
        img = SE_Image()
        if self._lib.SE_FetchImage(byref(img)) < 0:
            return None
        return img

    # --- callbacks ---

    def register_storyboard_callback(self, fn) -> None:
        """
        fn(name: str, element_type: int, state: int, full_path: str)

        Use ELEMENT_TYPES[element_type] and ELEMENT_STATES[state] to decode.
        """

        def _wrapper(name, element_type, state, full_path):
            fn(name.decode(), element_type, state, full_path.decode())

        self._storyboard_cb = _StoryboardCbType(_wrapper)
        self._lib.SE_RegisterStoryBoardElementStateChangeCallback(self._storyboard_cb)

    def register_condition_callback(self, fn) -> None:
        """fn(name: str, timestamp: float)"""

        def _wrapper(name, timestamp):
            fn(name.decode(), timestamp)

        self._condition_cb = _ConditionCbType(_wrapper)
        self._lib.SE_RegisterConditionCallback(self._condition_cb)

    def register_object_callback(self, object_id: int, fn) -> None:
        """
        fn(state: ScenarioObjectState)

        Called after each simulation frame for the specified object.
        Can override position by calling report_object_pos* inside the callback.
        """

        def _wrapper(state_ptr, _user_data):
            fn(state_ptr.contents)

        cb = _ObjectCbType(_wrapper)
        self._object_cbs[object_id] = cb  # keep reference alive
        self._lib.SE_RegisterObjectCallback(object_id, cb, None)

    def register_parameter_declaration_callback(self, fn) -> None:
        """fn() - called after ParameterDeclarations are parsed, before Init block."""

        def _wrapper(_user_data):
            fn()

        self._param_decl_cb = _ParamDeclCbType(_wrapper)
        self._lib.SE_RegisterParameterDeclarationCallback(self._param_decl_cb, None)

    # --- parameter distribution ---

    def set_parameter_distribution(self, filename: str) -> int:
        return self._lib.SE_SetParameterDistribution(filename.encode())

    def reset_parameter_distribution(self) -> None:
        self._lib.SE_ResetParameterDistribution()

    def get_number_of_permutations(self) -> int:
        return self._lib.SE_GetNumberOfPermutations()

    def select_permutation(self, index: int) -> int:
        return self._lib.SE_SelectPermutation(index)

    def get_permutation_index(self) -> int:
        return self._lib.SE_GetPermutationIndex()

    # --- back-compat aliases (original esmini.py names) ---

    def stepDT(self, dt: float) -> int:
        return self.step_dt(dt)

    def getSimulationTime(self) -> float:
        return self.get_simulation_time()

    def getODRFilename(self) -> str:
        return self.get_odr_filename()

    def getSceneGraphFilename(self) -> str:
        return self.get_scene_graph_filename()

    def getNumberOfObjects(self) -> int:
        return self.get_number_of_objects()

    def getObjectName(self, index: int) -> str:
        return self.get_object_name(self.get_id(index))

    def getObjectState(self, index: int) -> ScenarioObjectState:
        return self.get_object_state_by_index(index)

    def reportObjectPos(self, object_id, x, y, z, h, p, r):
        return self.report_object_pos(object_id, x, y, z, h, p, r)

    def reportObjectRoadPos(self, object_id, roadId, laneId, laneOffset, s):
        return self.report_object_road_pos(object_id, roadId, laneId, laneOffset, s)

    def getRoadInfoAtDistance(self, object_id, lookahead_distance, lookAheadMode):
        return self.get_road_info_at_distance(
            object_id, lookahead_distance, lookAheadMode
        )

    def addPath(self, path):
        return self.add_path(path)

    def clearPaths(self):
        self.clear_paths()

    def OSIFileOpen(self, filename):
        self.osi_file_open(filename)

    def registerStoryboardCallback(self, fn):
        self.register_storyboard_callback(fn)

    def registerConditionCallback(self, fn):
        self.register_condition_callback(fn)


# ---------------------------------------------------------------------------
# RoadManagerLib
# ---------------------------------------------------------------------------


class RoadManagerLib:
    """
    Python wrapper around libesminiRMLib - standalone road-network queries.

    Load an OpenDRIVE file directly (no scenario required):

        rm = RoadManagerLib("my_map.xodr")
        h  = rm.create_position()
        rm.set_lane_position(h, road_id=1, lane_id=-1, lane_offset=0.0, s=10.0)
        data = rm.get_position_data(h)
        rm.delete_position(h)
        rm.close()

    Interoperability with EsminiLib - use the same road network:

        sim = EsminiLib.from_file("scenario.xosc", use_viewer=0)
        rm  = RoadManagerLib(sim.get_odr_filename())
    """

    @staticmethod
    def _load_rm_lib(lib_dir: str) -> ctypes.CDLL:
        """Load esminiRMLib, falling back to esminiLib if RM symbols are embedded there."""
        _register_dll_dir(lib_dir)
        for stem in ("esminiRMLib", "esminiLib"):
            try:
                lib = ctypes.CDLL(_lib_path(lib_dir, stem))
                # Verify RM_Init is actually exported - esminiLib does NOT export
                # RM_* symbols, so this guard prevents a later AttributeError in
                # _declare_signatures when only esminiLib is present.
                _ = lib.RM_Init
                return lib
            except Exception:
                continue
        raise OSError(
            f"Could not load esminiRMLib (or esminiLib with RM_Init) from {lib_dir!r}"
        )

    def __init__(self, odr_file: str, lib_dir: str = None):
        self._lib_dir = lib_dir or _default_lib_dir()
        self._lib = self._load_rm_lib(self._lib_dir)
        self._declare_signatures()
        if self._lib.RM_Init(odr_file.encode()) < 0:
            raise RuntimeError(f"RM_Init failed for {odr_file!r}")

    @classmethod
    def from_string(cls, xodr_xml: str, lib_dir: str = None) -> "RoadManagerLib":
        """Initialise from an OpenDRIVE XML string."""
        obj = cls.__new__(cls)
        obj._lib_dir = lib_dir or _default_lib_dir()
        obj._lib = cls._load_rm_lib(obj._lib_dir)
        obj._declare_signatures()
        if obj._lib.RM_InitWithString(xodr_xml.encode()) < 0:
            raise RuntimeError("RM_InitWithString failed - check the XML content")
        return obj

    # --------------------------------------------------------- context manager

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def __del__(self):
        try:
            self._lib.RM_Close()
        except Exception:
            pass

    # ---------------------------------------------------- ctypes declarations

    def _declare_signatures(self):
        lib = self._lib

        lib.RM_Init.argtypes = [c_char_p]
        lib.RM_Init.restype = c_int

        lib.RM_InitWithString.argtypes = [c_char_p]
        lib.RM_InitWithString.restype = c_int

        lib.RM_Close.argtypes = []
        lib.RM_Close.restype = c_int

        lib.RM_SetLogFilePath.argtypes = [c_char_p]
        lib.RM_SetLogFilePath.restype = None

        lib.RM_CreatePosition.argtypes = []
        lib.RM_CreatePosition.restype = c_int

        lib.RM_GetNrOfPositions.argtypes = []
        lib.RM_GetNrOfPositions.restype = c_int

        lib.RM_DeletePosition.argtypes = [c_int]
        lib.RM_DeletePosition.restype = c_int

        lib.RM_CopyPosition.argtypes = [c_int]
        lib.RM_CopyPosition.restype = c_int

        lib.RM_SetObjectPositionMode.argtypes = [c_int, c_int, c_int]
        lib.RM_SetObjectPositionMode.restype = None

        lib.RM_SetObjectPositionModeDefault.argtypes = [c_int, c_int]
        lib.RM_SetObjectPositionModeDefault.restype = None

        lib.RM_SetSnapLaneTypes.argtypes = [c_int, c_int]
        lib.RM_SetSnapLaneTypes.restype = c_int

        lib.RM_SetLockOnLane.argtypes = [c_int, c_bool]
        lib.RM_SetLockOnLane.restype = c_int

        lib.RM_GetNumberOfRoads.argtypes = []
        lib.RM_GetNumberOfRoads.restype = c_int

        lib.RM_GetSpeedUnit.argtypes = []
        lib.RM_GetSpeedUnit.restype = c_int

        lib.RM_GetIdOfRoadFromIndex.argtypes = [c_uint]
        lib.RM_GetIdOfRoadFromIndex.restype = c_uint

        lib.RM_GetRoadLength.argtypes = [c_uint]
        lib.RM_GetRoadLength.restype = c_double

        lib.RM_GetRoadIdString.argtypes = [c_uint]
        lib.RM_GetRoadIdString.restype = c_char_p

        lib.RM_GetRoadIdFromString.argtypes = [c_char_p]
        lib.RM_GetRoadIdFromString.restype = c_uint

        lib.RM_GetJunctionIdString.argtypes = [c_uint]
        lib.RM_GetJunctionIdString.restype = c_char_p

        lib.RM_GetJunctionIdFromString.argtypes = [c_char_p]
        lib.RM_GetJunctionIdFromString.restype = c_uint

        lib.RM_GetRoadNumberOfLanes.argtypes = [c_uint, c_double, c_int]
        lib.RM_GetRoadNumberOfLanes.restype = c_int

        lib.RM_GetRoadNumberOfDrivableLanes.argtypes = [c_uint, c_double]
        lib.RM_GetRoadNumberOfDrivableLanes.restype = c_int

        lib.RM_GetLaneIdByIndex.argtypes = [
            c_uint,
            c_int,
            c_double,
            c_int,
            POINTER(c_int),
        ]
        lib.RM_GetLaneIdByIndex.restype = c_int

        lib.RM_GetDrivableLaneIdByIndex.argtypes = [
            c_uint,
            c_int,
            c_double,
            POINTER(c_int),
        ]
        lib.RM_GetDrivableLaneIdByIndex.restype = c_int

        lib.RM_GetNumberOfRoadsOverlapping.argtypes = [c_int]
        lib.RM_GetNumberOfRoadsOverlapping.restype = c_int

        lib.RM_GetOverlappingRoadId.argtypes = [c_int, c_uint]
        lib.RM_GetOverlappingRoadId.restype = c_uint

        lib.RM_SetLanePosition.argtypes = [
            c_int,
            c_uint,
            c_int,
            c_double,
            c_double,
            c_bool,
        ]
        lib.RM_SetLanePosition.restype = c_int

        lib.RM_SetRoadPosition.argtypes = [c_int, c_uint, c_double, c_double, c_bool]
        lib.RM_SetRoadPosition.restype = c_int

        lib.RM_SetS.argtypes = [c_int, c_double]
        lib.RM_SetS.restype = c_int

        lib.RM_SetWorldPosition.argtypes = [
            c_int,
            c_double,
            c_double,
            c_double,
            c_double,
            c_double,
            c_double,
        ]
        lib.RM_SetWorldPosition.restype = c_int

        lib.RM_SetWorldXYHPosition.argtypes = [c_int, c_double, c_double, c_double]
        lib.RM_SetWorldXYHPosition.restype = c_int

        lib.RM_SetWorldXYZHPosition.argtypes = [
            c_int,
            c_double,
            c_double,
            c_double,
            c_double,
        ]
        lib.RM_SetWorldXYZHPosition.restype = c_int

        lib.RM_SetWorldPositionMode.argtypes = [
            c_int,
            c_double,
            c_double,
            c_double,
            c_double,
            c_double,
            c_double,
            c_int,
        ]
        lib.RM_SetWorldPositionMode.restype = c_int

        lib.RM_SetH.argtypes = [c_int, c_double]
        lib.RM_SetH.restype = c_int

        lib.RM_SetHMode.argtypes = [c_int, c_double, c_int]
        lib.RM_SetHMode.restype = c_int

        lib.RM_SetRoadId.argtypes = [c_int, c_uint]
        lib.RM_SetRoadId.restype = c_int

        lib.RM_PositionMoveForward.argtypes = [c_int, c_double, c_double]
        lib.RM_PositionMoveForward.restype = c_int

        lib.RM_GetPositionData.argtypes = [c_int, POINTER(RM_PositionData)]
        lib.RM_GetPositionData.restype = c_int

        lib.RM_GetSpeedLimit.argtypes = [c_int]
        lib.RM_GetSpeedLimit.restype = c_double

        lib.RM_GetLaneInfo.argtypes = [
            c_int,
            c_double,
            POINTER(RM_RoadLaneInfo),
            c_int,
            c_bool,
        ]
        lib.RM_GetLaneInfo.restype = c_int

        lib.RM_GetProbeInfo.argtypes = [
            c_int,
            c_double,
            POINTER(RM_RoadProbeInfo),
            c_int,
            c_bool,
        ]
        lib.RM_GetProbeInfo.restype = c_int

        lib.RM_GetLaneWidth.argtypes = [c_int, c_int, POINTER(c_double)]
        lib.RM_GetLaneWidth.restype = c_int

        lib.RM_GetLaneWidthByRoadId.argtypes = [
            c_uint,
            c_int,
            c_double,
            POINTER(c_double),
        ]
        lib.RM_GetLaneWidthByRoadId.restype = c_int

        lib.RM_GetLaneType.argtypes = [c_int, c_int]
        lib.RM_GetLaneType.restype = c_int

        lib.RM_GetInLaneType.argtypes = [c_int]
        lib.RM_GetInLaneType.restype = c_int

        lib.RM_GetLaneTypeByRoadId.argtypes = [c_uint, c_int, c_double]
        lib.RM_GetLaneTypeByRoadId.restype = c_int

        lib.RM_SubtractAFromB.argtypes = [c_int, c_int, POINTER(RM_PositionDiff)]
        lib.RM_SubtractAFromB.restype = c_int

        lib.RM_GetNumberOfRoadSigns.argtypes = [c_uint]
        lib.RM_GetNumberOfRoadSigns.restype = c_int

        lib.RM_GetRoadSign.argtypes = [c_uint, c_uint, POINTER(RM_RoadSign)]
        lib.RM_GetRoadSign.restype = c_int

        lib.RM_GetNumberOfRoadSignValidityRecords.argtypes = [c_uint, c_uint]
        lib.RM_GetNumberOfRoadSignValidityRecords.restype = c_int

        lib.RM_GetRoadSignValidityRecord.argtypes = [
            c_uint,
            c_uint,
            c_uint,
            POINTER(RM_RoadObjValidity),
        ]
        lib.RM_GetRoadSignValidityRecord.restype = c_int

        lib.RM_GetOpenDriveGeoReference.argtypes = [POINTER(RM_GeoReference)]
        lib.RM_GetOpenDriveGeoReference.restype = c_int

        lib.RM_SetOption.argtypes = [c_char_p]
        lib.RM_SetOption.restype = c_int

        lib.RM_UnsetOption.argtypes = [c_char_p]
        lib.RM_UnsetOption.restype = c_int

        lib.RM_SetOptionValue.argtypes = [c_char_p, c_char_p]
        lib.RM_SetOptionValue.restype = c_int

        lib.RM_GetOptionValue.argtypes = [c_char_p]
        lib.RM_GetOptionValue.restype = c_char_p

        lib.RM_GetOptionSet.argtypes = [c_char_p]
        lib.RM_GetOptionSet.restype = c_bool

    # -------------------------------------------------------------- wrappers

    def close(self) -> None:
        self._lib.RM_Close()

    def set_log_file_path(self, path: str) -> None:
        self._lib.RM_SetLogFilePath(path.encode())

    # --- position objects ---

    def create_position(self) -> int:
        """Allocate a new position object; returns an integer handle."""
        h = self._lib.RM_CreatePosition()
        if h < 0:
            raise RuntimeError("RM_CreatePosition failed")
        return h

    def get_nr_of_positions(self) -> int:
        return self._lib.RM_GetNrOfPositions()

    def delete_position(self, handle: int) -> int:
        return self._lib.RM_DeletePosition(handle)

    def copy_position(self, handle: int) -> int:
        """Return a new handle that is a copy of *handle*."""
        new_h = self._lib.RM_CopyPosition(handle)
        if new_h < 0:
            raise RuntimeError("RM_CopyPosition failed")
        return new_h

    def set_snap_lane_types(self, handle: int, lane_types: int) -> int:
        return self._lib.RM_SetSnapLaneTypes(handle, lane_types)

    def set_lock_on_lane(self, handle: int, mode: bool) -> int:
        return self._lib.RM_SetLockOnLane(handle, mode)

    # --- road topology ---

    def get_number_of_roads(self) -> int:
        return self._lib.RM_GetNumberOfRoads()

    def get_id_of_road_from_index(self, index: int) -> int:
        return self._lib.RM_GetIdOfRoadFromIndex(index)

    def get_road_length(self, road_id: int) -> float:
        return self._lib.RM_GetRoadLength(road_id)

    def get_road_id_string(self, road_id: int) -> str:
        result = self._lib.RM_GetRoadIdString(road_id)
        return result.decode() if result else ""

    def get_road_id_from_string(self, road_id_str: str) -> int:
        return self._lib.RM_GetRoadIdFromString(road_id_str.encode())

    def get_road_number_of_lanes(
        self, road_id: int, s: float, type_mask: int = -1
    ) -> int:
        return self._lib.RM_GetRoadNumberOfLanes(road_id, s, type_mask)

    def get_road_number_of_drivable_lanes(self, road_id: int, s: float) -> int:
        return self._lib.RM_GetRoadNumberOfDrivableLanes(road_id, s)

    def get_lane_id_by_index(
        self,
        road_id: int,
        lane_index: int,
        s: float,
        type_mask: int = -1,
    ) -> int:
        """Return lane ID at *lane_index*; raises on failure."""
        lane_id = c_int()
        if (
            self._lib.RM_GetLaneIdByIndex(
                road_id, lane_index, s, type_mask, byref(lane_id)
            )
            < 0
        ):
            raise IndexError(f"lane index {lane_index} out of range on road {road_id}")
        return lane_id.value

    def get_drivable_lane_id_by_index(
        self, road_id: int, lane_index: int, s: float
    ) -> int:
        lane_id = c_int()
        if (
            self._lib.RM_GetDrivableLaneIdByIndex(
                road_id, lane_index, s, byref(lane_id)
            )
            < 0
        ):
            raise IndexError(
                f"drivable lane index {lane_index} out of range on road {road_id}"
            )
        return lane_id.value

    def get_speed_unit(self) -> int:
        return self._lib.RM_GetSpeedUnit()

    # --- set position ---

    def set_lane_position(
        self,
        handle: int,
        road_id: int,
        lane_id: int,
        lane_offset: float,
        s: float,
        align: bool = True,
    ) -> int:
        return self._lib.RM_SetLanePosition(
            handle, road_id, lane_id, lane_offset, s, align
        )

    def set_road_position(
        self,
        handle: int,
        road_id: int,
        s: float,
        t: float,
        align: bool = True,
    ) -> int:
        return self._lib.RM_SetRoadPosition(handle, road_id, s, t, align)

    def set_s(self, handle: int, s: float) -> int:
        return self._lib.RM_SetS(handle, s)

    def set_world_position(
        self,
        handle: int,
        x: float,
        y: float,
        z: float,
        h: float,
        p: float,
        r: float,
    ) -> int:
        return self._lib.RM_SetWorldPosition(handle, x, y, z, h, p, r)

    def set_world_xyh_position(self, handle: int, x: float, y: float, h: float) -> int:
        return self._lib.RM_SetWorldXYHPosition(handle, x, y, h)

    def set_world_xyzh_position(
        self,
        handle: int,
        x: float,
        y: float,
        z: float,
        h: float,
    ) -> int:
        return self._lib.RM_SetWorldXYZHPosition(handle, x, y, z, h)

    def set_h(self, handle: int, h: float) -> int:
        return self._lib.RM_SetH(handle, h)

    def set_h_mode(self, handle: int, h: float, mode: int) -> int:
        return self._lib.RM_SetHMode(handle, h, mode)

    def set_road_id(self, handle: int, road_id: int) -> int:
        return self._lib.RM_SetRoadId(handle, road_id)

    def position_move_forward(
        self,
        handle: int,
        dist: float,
        junction_selector_angle: float = -1.0,
    ) -> int:
        return self._lib.RM_PositionMoveForward(handle, dist, junction_selector_angle)

    # --- query position ---

    def get_position_data(self, handle: int):
        """Return RM_PositionData for *handle*, or None on failure."""
        data = RM_PositionData()
        if self._lib.RM_GetPositionData(handle, byref(data)) < 0:
            return None
        return data

    def get_speed_limit(self, handle: int) -> float:
        return self._lib.RM_GetSpeedLimit(handle)

    def get_lane_info(
        self,
        handle: int,
        lookahead_dist: float,
        look_ahead_mode: int = 0,
        in_driving_direction: bool = True,
    ):
        """Return RM_RoadLaneInfo at *lookahead_dist* ahead, or None."""
        info = RM_RoadLaneInfo()
        if (
            self._lib.RM_GetLaneInfo(
                handle,
                lookahead_dist,
                byref(info),
                look_ahead_mode,
                in_driving_direction,
            )
            < 0
        ):
            return None
        return info

    def get_probe_info(
        self,
        handle: int,
        lookahead_dist: float,
        look_ahead_mode: int = 0,
        in_driving_direction: bool = True,
    ):
        """Return RM_RoadProbeInfo at *lookahead_dist* ahead, or None."""
        info = RM_RoadProbeInfo()
        if (
            self._lib.RM_GetProbeInfo(
                handle,
                lookahead_dist,
                byref(info),
                look_ahead_mode,
                in_driving_direction,
            )
            < 0
        ):
            return None
        return info

    def get_lane_width(self, handle: int, lane_id: int) -> float:
        width = c_double()
        if self._lib.RM_GetLaneWidth(handle, lane_id, byref(width)) < 0:
            return 0.0
        return width.value

    def get_lane_width_by_road_id(self, road_id: int, lane_id: int, s: float) -> float:
        width = c_double()
        if self._lib.RM_GetLaneWidthByRoadId(road_id, lane_id, s, byref(width)) < 0:
            return 0.0
        return width.value

    def get_lane_type(self, handle: int, lane_id: int) -> int:
        return self._lib.RM_GetLaneType(handle, lane_id)

    def get_in_lane_type(self, handle: int) -> int:
        return self._lib.RM_GetInLaneType(handle)

    def get_lane_type_by_road_id(self, road_id: int, lane_id: int, s: float) -> int:
        return self._lib.RM_GetLaneTypeByRoadId(road_id, lane_id, s)

    def subtract_a_from_b(self, handle_a: int, handle_b: int):
        """Compute the delta between two position objects. Returns RM_PositionDiff or None."""
        diff = RM_PositionDiff()
        if self._lib.RM_SubtractAFromB(handle_a, handle_b, byref(diff)) < 0:
            return None
        return diff

    # --- road signs ---

    def get_number_of_road_signs(self, road_id: int) -> int:
        return self._lib.RM_GetNumberOfRoadSigns(road_id)

    def get_road_sign(self, road_id: int, sign_index: int):
        sign = RM_RoadSign()
        if self._lib.RM_GetRoadSign(road_id, sign_index, byref(sign)) < 0:
            return None
        return sign

    def get_number_of_road_sign_validity_records(
        self, road_id: int, sign_index: int
    ) -> int:
        return self._lib.RM_GetNumberOfRoadSignValidityRecords(road_id, sign_index)

    def get_road_sign_validity_record(
        self,
        road_id: int,
        sign_index: int,
        validity_index: int,
    ):
        v = RM_RoadObjValidity()
        if (
            self._lib.RM_GetRoadSignValidityRecord(
                road_id, sign_index, validity_index, byref(v)
            )
            < 0
        ):
            return None
        return v

    # --- geo reference ---

    def get_open_drive_geo_reference(self):
        ref = RM_GeoReference()
        if self._lib.RM_GetOpenDriveGeoReference(byref(ref)) < 0:
            return None
        return ref

    # --- options ---

    def set_option(self, name: str) -> int:
        return self._lib.RM_SetOption(name.encode())

    def unset_option(self, name: str) -> int:
        return self._lib.RM_UnsetOption(name.encode())

    def set_option_value(self, name: str, value: str) -> int:
        return self._lib.RM_SetOptionValue(name.encode(), value.encode())

    def get_option_value(self, name: str) -> str:
        result = self._lib.RM_GetOptionValue(name.encode())
        return result.decode() if result else ""

    def get_option_set(self, name: str) -> bool:
        return self._lib.RM_GetOptionSet(name.encode())

    # --- back-compat aliases ---

    def getNumberOfRoads(self) -> int:
        return self.get_number_of_roads()

    def getIdOfRoadFromIndex(self, index: int) -> int:
        return self.get_id_of_road_from_index(index)

    def getRoadLength(self, road_id: int) -> float:
        return self.get_road_length(road_id)

    def getNumberOfLanesAtS(self, road_id: int, s: float) -> int:
        return self.get_road_number_of_drivable_lanes(road_id, s)

    def getLaneIdByIndex(self, road_id: int, s: float, lane_index: int) -> int:
        return self.get_drivable_lane_id_by_index(road_id, lane_index, s)

    def setLanePosition(self, handle, road_id, lane_id, lane_offset, s, align=True):
        return self.set_lane_position(handle, road_id, lane_id, lane_offset, s, align)

    def setWorldPosition(self, handle, x, y, z, h, p, r):
        return self.set_world_position(handle, x, y, z, h, p, r)

    def setWorldXYHPosition(self, handle, x, y, h):
        return self.set_world_xyh_position(handle, x, y, h)

    def getPositionData(self, handle):
        return self.get_position_data(handle)

    def getSpeedLimit(self, handle):
        return self.get_speed_limit(handle)

    def getLaneInfo(
        self, handle, lookahead_dist, look_ahead_mode=0, in_driving_direction=True
    ):
        return self.get_lane_info(
            handle, lookahead_dist, look_ahead_mode, in_driving_direction
        )

    def getProbeInfo(
        self, handle, lookahead_dist, look_ahead_mode=0, in_driving_direction=True
    ):
        return self.get_probe_info(
            handle, lookahead_dist, look_ahead_mode, in_driving_direction
        )

    def getNumberOfRoadSigns(self, road_id):
        return self.get_number_of_road_signs(road_id)

    def getRoadSign(self, road_id, sign_index):
        return self.get_road_sign(road_id, sign_index)

    def createPosition(self):
        return self.create_position()

    def deletePosition(self, handle):
        return self.delete_position(handle)
