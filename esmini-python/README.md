# esmini Python API

`esmini-python` is a standalone Python package that wraps the
[esmini](https://github.com/esmini/esmini) simulation libraries, exposing the full `esminiLib` and
`esminiRMLib` C APIs through Python `ctypes`.

```
sim = EsminiLib.from_file("scenario.xosc")
odr = sim.get_odr_filename()            # path the engine loaded
rm  = RoadManagerLib(odr)               # same road network in RM
```

## Installation

```bash
# Editable install - changes to the source are reflected immediately
pip install -e ./esmini-python

# Or a regular install
pip install ./esmini-python
```

## Directory Layout

```
esmini-python/
├── pyproject.toml          # Package metadata (name: esmini-python)
└── esmini/
    └── __init__.py         # EsminiLib + RoadManagerLib + SimpleVehicle
```

The wrapper expects the shared libraries in a directory pointed to by `ESMINI_LIB_DIR`:

```
<lib-dir>/
├── libesminiLib.so      (Linux)   / libesminiLib.dylib (macOS) / esminiLib.dll (Win)
├── libesminiRMLib.so    (Linux)   / …
└── resources/           (optional bundled resources)
    ├── xosc/
    └── xodr/
```

Override the default search path with the `ESMINI_LIB_DIR` environment variable.

______________________________________________________________________

## Building the Libraries inside Docker

```bash
docker compose build          # Downloads esmini source and compiles
docker compose run test       # Runs the full test suite
```

______________________________________________________________________

## Usage Guide

### Basic - Headless scenario simulation

```python
from esmini import EsminiLib

with EsminiLib.from_file("resources/xosc/cut-in_simple.xosc", use_viewer=0) as sim:
    while not sim.get_quit_flag():
        sim.step_dt(0.05)                         # fixed 50 ms step
        n = sim.get_number_of_objects()
        for idx in range(n):
            obj_id = sim.get_id(idx)
            state  = sim.get_object_state(obj_id)
            print(f"[{sim.get_simulation_time():.2f}s] "
                  f"{sim.get_object_name(obj_id)}: "
                  f"x={state.x:.1f}  y={state.y:.1f}  v={state.speed:.1f} m/s")
```

### Road-network queries (standalone)

```python
from esmini import RoadManagerLib

with RoadManagerLib("resources/xodr/straight_500m.xodr") as rm:
    road_id = rm.get_id_of_road_from_index(0)
    print(f"Road length: {rm.get_road_length(road_id):.1f} m")

    h = rm.create_position()
    rm.set_lane_position(h, road_id=road_id, lane_id=-1, lane_offset=0.0, s=100.0)
    data = rm.get_position_data(h)
    print(f"World pos: x={data.x:.2f}  y={data.y:.2f}  h={data.h:.3f}")

    ahead = rm.get_lane_info(h, lookahead_dist=30.0)
    print(f"30 m ahead: curvature={ahead.curvature:.6f}  speed_limit={ahead.speed_limit} m/s")
    rm.delete_position(h)
```

### SE + RM interoperability

```python
from esmini import EsminiLib, RoadManagerLib
import os

# 1. Run the scenario for a few steps
sim     = EsminiLib.from_file("cut-in_simple.xosc", use_viewer=0)
for _   in range(20):
    sim.step_dt(0.05)

# 2. Get the road the Ego is on
ego_id  = sim.get_id_by_name("Ego")
state   = sim.get_object_state(ego_id)
odr     = sim.get_odr_filename()          # absolute path to the loaded .xodr

# 3. Use RoadManagerLib on the same network
rm      = RoadManagerLib(odr)
h       = rm.create_position()
rm.set_lane_position(h, state.roadId, state.laneId, state.laneOffset, state.s)
probe   = rm.get_probe_info(h, lookahead_dist=50.0)
print(f"Heading to target: {probe.relative_h:.3f} rad")
rm.delete_position(h)
rm.close()
sim.close()
```

### External controller (ExternalController pattern)

```python
from esmini import EsminiLib
import math

def my_controller(state):
    """Called after each step - update the object position externally."""
    # Pure Python PID / ML model / ROS bridge goes here
    pass

with EsminiLib.from_file("cut-in_external.xosc", use_viewer=0) as sim:
    ego_id = sim.get_id_by_name("Ego")
    sim.register_object_callback(ego_id, my_controller)
    while not sim.get_quit_flag():
        sim.step_dt(0.05)
```

### Simple Vehicle kinematic model

```python
from esmini import EsminiLib

with EsminiLib.from_file("scenario.xosc", use_viewer=0) as sim:
    with sim.create_simple_vehicle(x=0, y=0, h=0, length=4.5, speed=0) as sv:
        for _ in range(200):
            sv.control_analog(dt=0.05, throttle=0.8, steering=0.1)
        state = sv.get_state()
        print(f"Final: x={state.x:.1f}  y={state.y:.1f}  speed={state.speed:.1f}")
```

### Storyboard and condition callbacks

```python
from esmini import EsminiLib, ELEMENT_TYPES, ELEMENT_STATES

with EsminiLib.from_file("cut-in_simple.xosc", use_viewer=0) as sim:
    sim.register_storyboard_callback(
        lambda name, etype, estate, path:
            print(f"[SB] {name} → {ELEMENT_TYPES[etype]} : {ELEMENT_STATES[estate]}")
    )
    sim.register_condition_callback(
        lambda name, ts: print(f"[COND] {name} triggered at t={ts:.3f} s")
    )
    while not sim.get_quit_flag():
        sim.step_dt(0.05)
```

### Action injection

```python
from esmini import EsminiLib, SE_SpeedActionStruct, SE_LaneChangeActionStruct

with EsminiLib.from_file("cut-in_simple.xosc", use_viewer=0) as sim:
    for _ in range(40):          # run 2 s
        sim.step_dt(0.05)

    ego_id = sim.get_id_by_name("Ego")

    # Inject a speed change: accelerate to 30 m/s linearly over 2 s
    spd        = SE_SpeedActionStruct()
    spd.id     = ego_id
    spd.speed  = 30.0
    spd.transition_shape = 1   # linear
    spd.transition_dim   = 2   # time
    spd.transition_value = 2.0
    sim.inject_speed_action(spd)

    while not sim.get_quit_flag():
        sim.step_dt(0.05)
```

## Running the Tests

### Why tests are skipped locally

Running `pytest` directly without building the shared libraries first produces:

```
SKIPPED (libesminiLib not found in .../esmini - set ESMINI_LIB_DIR)
```

The wrapper needs `libesminiLib.so` and `libesminiRMLib.so` on disk. Either
[build them locally](#building-the-libraries) and export `ESMINI_LIB_DIR`, or use Docker below - the
image compiles everything automatically.

______________________________________________________________________

#### Using docker compose

```bash
# Build the image (compiles esmini from source - takes ~5 minutes on first run)
docker compose build

# Run the full test suite
docker compose run --rm test

# Run a specific subset
docker compose run --rm test-rm          # RoadManagerLib only
docker compose run --rm test-lib         # EsminiLib only
docker compose run --rm test-integration # Integration tests only
```

#### Pinning to a specific esmini release

By default the image builds from the `master` branch. Pass `ESMINI_REF` to pin to a tag or commit:

```bash
docker build --build-arg ESMINI_REF=v3.0.4 -t esmini-python-api:v3.0.4 .
```

______________________________________________________________________

## API Reference

### `EsminiLib`

#### Initialisation

| Method                                                                                            | Description                                 |
| ------------------------------------------------------------------------------------------------- | ------------------------------------------- |
| `EsminiLib(osc_file, disable_ctrls, use_viewer, threads, record_file, lib_dir)`                   | Legacy constructor - uses `SE_InitWithArgs` |
| `EsminiLib.from_file(osc_file, disable_ctrls, use_viewer, threads, record, lib_dir, extra_paths)` | Direct `SE_Init` - preferred                |
| `EsminiLib.from_string(xosc_xml, ...)`                                                            | Initialise from in-memory XML string        |
| `close()`                                                                                         | Stop simulation and free memory             |

#### Simulation loop

| Method                       | Returns               | Description                        |
| ---------------------------- | --------------------- | ---------------------------------- |
| `step_dt(dt)`                | `int` (0=ok, -1=done) | Advance by fixed `dt` seconds      |
| `step()`                     | `bool`                | Advance by elapsed wall-clock time |
| `get_simulation_time()`      | `float`               | Current simulation time (s)        |
| `get_simulation_time_step()` | `float`               | Last step size (s)                 |
| `get_quit_flag()`            | `int` (0/1/-1)        | 1 when scenario is complete        |
| `get_pause_flag()`           | `int`                 | 1 when paused via viewer           |

#### Object queries

| Method                                          | Returns               | Description                  |
| ----------------------------------------------- | --------------------- | ---------------------------- |
| `get_number_of_objects()`                       | `int`                 | Entity count                 |
| `get_id(index)`                                 | `int`                 | Object ID from 0-based index |
| `get_id_by_name(name)`                          | `int`                 | Object ID from entity name   |
| `get_object_state(object_id)`                   | `ScenarioObjectState` | Full state struct            |
| `get_object_state_by_index(index)`              | `ScenarioObjectState` | Convenience wrapper          |
| `get_object_name(object_id)`                    | `str`                 | Entity name                  |
| `get_object_type_name(object_id)`               | `str`                 | Type name (Vehicle, etc.)    |
| `get_object_model_filename(object_id)`          | `str`                 | 3D model filename            |
| `get_object_odometer(object_id)`                | `float`               | Travelled distance (m)       |
| `get_object_velocity_global_xyz(object_id)`     | `(vx, vy, vz)`        | Linear velocity (m/s)        |
| `get_object_angular_velocity(object_id)`        | `(h_r, p_r, r_r)`     | Angular velocity (rad/s)     |
| `get_object_acceleration(object_id)`            | `float`               | Scalar acceleration (m/s²)   |
| `get_object_number_of_collisions(object_id)`    | `int`                 | Active collision count       |
| `get_object_number_of_wheels(object_id)`        | `int`                 | Wheel count                  |
| `get_object_wheel_data(object_id, wheel_index)` | `WheelData`           | Wheel geometry               |

#### Position reporting (external control)

| Method                                                    | Returns | Description                       |
| --------------------------------------------------------- | ------- | --------------------------------- |
| `report_object_pos(id, x, y, z, h, p, r)`                 | `int`   | Set Cartesian position            |
| `report_object_pos_xyh(id, x, y, h)`                      | `int`   | Set x/y/heading; z aligns to road |
| `report_object_road_pos(id, road_id, lane_id, offset, s)` | `int`   | Set road-coordinate position      |
| `report_object_speed(id, speed)`                          | `int`   | Override longitudinal speed       |
| `report_object_vel(id, vx, vy, vz)`                       | `int`   | Report full velocity vector       |

#### Road information

| Method                                                 | Returns                  | Description                     |
| ------------------------------------------------------ | ------------------------ | ------------------------------- |
| `get_road_info_at_distance(id, dist, mode, direction)` | `RoadInfo \| None`       | Lookahead point data            |
| `get_road_info_along_route(id, dist, mode, direction)` | `RoadInfo \| None`       | Lookahead along assigned route  |
| `get_distance_to_object(id_a, id_b, free_space)`       | `SEPositionDiff \| None` | Distance between two objects    |
| `get_speed_unit()`                                     | `int`                    | 0=undef, 1=km/h, 2=m/s, 3=mph   |
| `get_odr_filename()`                                   | `str`                    | OpenDRIVE file used by scenario |

#### Parameters & variables

| Method                                            | Returns        | Description              |
| ------------------------------------------------- | -------------- | ------------------------ |
| `get_number_of_parameters()`                      | `int`          | Declared parameter count |
| `get_parameter_name(index)`                       | `(name, type)` | Name + type code         |
| `get_parameter_int/double/string/bool(name)`      | typed          | Read typed parameter     |
| `set_parameter_int/double/string/bool(name, val)` | `int`          | Write typed parameter    |
| `get_number_of_variables()`                       | `int`          | Declared variable count  |
| `get_variable_int/double(name)`                   | typed          | Read typed variable      |
| `set_variable_int/double(name, val)`              | `int`          | Write typed variable     |

#### Callbacks

| Method                                        | Signature                                  | Description              |
| --------------------------------------------- | ------------------------------------------ | ------------------------ |
| `register_storyboard_callback(fn)`            | `fn(name, element_type, state, full_path)` | Storyboard state changes |
| `register_condition_callback(fn)`             | `fn(name, timestamp)`                      | Condition triggers       |
| `register_object_callback(object_id, fn)`     | `fn(state: ScenarioObjectState)`           | Per-frame object state   |
| `register_parameter_declaration_callback(fn)` | `fn()`                                     | Pre-init parameter hook  |

#### Action injection

| Method                                                 | Description                            |
| ------------------------------------------------------ | -------------------------------------- |
| `inject_speed_action(SE_SpeedActionStruct)`            | Override speed trajectory              |
| `inject_lane_change_action(SE_LaneChangeActionStruct)` | Trigger lane change                    |
| `inject_lane_offset_action(SE_LaneOffsetActionStruct)` | Apply lateral offset                   |
| `injected_action_ongoing(action_type=-1)`              | Check if any injected action is active |

#### Simple Vehicle

| Method                                           | Description                               |
| ------------------------------------------------ | ----------------------------------------- |
| `create_simple_vehicle(x, y, h, length, speed)`  | Returns `SimpleVehicle` context manager   |
| `sv.control_binary(dt, throttle, steering)`      | Discrete [-1, 0, 1] inputs                |
| `sv.control_analog(dt, throttle, steering)`      | Continuous [-1..1] inputs                 |
| `sv.control_acc_and_steer(dt, acc, steer_angle)` | Explicit acc + steer angle                |
| `sv.control_target(dt, target_speed, heading)`   | Speed-target controller                   |
| `sv.get_state()`                                 | `SimpleVehicleState` with x/y/z/h/p/speed |
| `sv.set_speed(speed)`                            | Set speed directly                        |
| `sv.set_max_speed(speed)`                        | Speed cap (km/h)                          |

______________________________________________________________________

### `RoadManagerLib`

#### Initialisation

| Method                                 | Description          |
| -------------------------------------- | -------------------- |
| `RoadManagerLib(odr_file, lib_dir)`    | Load from file       |
| `RoadManagerLib.from_string(xodr_xml)` | Load from XML string |
| `close()`                              | Free road network    |

#### Road topology

| Method                                            | Returns | Description                |
| ------------------------------------------------- | ------- | -------------------------- |
| `get_number_of_roads()`                           | `int`   | Total road count           |
| `get_id_of_road_from_index(index)`                | `int`   | Road ID from 0-based index |
| `get_road_length(road_id)`                        | `float` | Road length (m)            |
| `get_road_number_of_lanes(road_id, s, type_mask)` | `int`   | Lane count at position `s` |
| `get_road_number_of_drivable_lanes(road_id, s)`   | `int`   | Drivable lane count        |
| `get_drivable_lane_id_by_index(road_id, idx, s)`  | `int`   | Lane ID from index         |
| `get_speed_unit()`                                | `int`   | Speed unit code            |

#### Position object lifecycle

| Method                    | Returns      | Description                    |
| ------------------------- | ------------ | ------------------------------ |
| `create_position()`       | `int` handle | Allocate a new position object |
| `delete_position(handle)` | `int`        | Free a position object         |
| `copy_position(handle)`   | `int` handle | Clone a position               |
| `get_nr_of_positions()`   | `int`        | Active position count          |

#### Setting positions

| Method                                                          | Description                 |
| --------------------------------------------------------------- | --------------------------- |
| `set_lane_position(h, road_id, lane_id, lane_offset, s, align)` | Place on a lane             |
| `set_road_position(h, road_id, s, t, align)`                    | Place using road s/t        |
| `set_s(h, s)`                                                   | Advance `s` on current road |
| `set_world_position(h, x, y, z, h, p, r)`                       | Place at world coordinates  |
| `set_world_xyh_position(h, x, y, heading)`                      | Place at x/y with heading   |
| `set_world_xyzh_position(h, x, y, z, heading)`                  | Place at x/y/z with heading |
| `position_move_forward(h, dist, junction_selector)`             | Advance along road          |

#### Querying positions

| Method                                          | Returns                    | Description                   |
| ----------------------------------------------- | -------------------------- | ----------------------------- |
| `get_position_data(handle)`                     | `RM_PositionData \| None`  | Full road+world coordinates   |
| `get_speed_limit(handle)`                       | `float`                    | Speed limit at position (m/s) |
| `get_lane_info(handle, dist, mode, direction)`  | `RM_RoadLaneInfo \| None`  | Lookahead lane data           |
| `get_probe_info(handle, dist, mode, direction)` | `RM_RoadProbeInfo \| None` | Lookahead with relative pos   |
| `get_lane_width(handle, lane_id)`               | `float`                    | Lane width (m)                |
| `get_lane_type(handle, lane_id)`                | `int`                      | Lane type bitmask             |
| `get_in_lane_type(handle)`                      | `int`                      | Type of lane the handle is in |
| `subtract_a_from_b(handle_a, handle_b)`         | `RM_PositionDiff \| None`  | Delta between two positions   |

#### Road signs

| Method                                                          | Returns                      | Description           |
| --------------------------------------------------------------- | ---------------------------- | --------------------- |
| `get_number_of_road_signs(road_id)`                             | `int`                        | Sign count on road    |
| `get_road_sign(road_id, sign_index)`                            | `RM_RoadSign \| None`        | Sign data             |
| `get_number_of_road_sign_validity_records(road_id, sign_index)` | `int`                        | Validity record count |
| `get_road_sign_validity_record(road_id, sign_index, val_index)` | `RM_RoadObjValidity \| None` | Lane validity range   |

______________________________________________________________________

## Data Structures

| Struct                      | Key Fields                                                                                   |
| --------------------------- | -------------------------------------------------------------------------------------------- |
| `ScenarioObjectState`       | `id, x, y, z, h, p, r, roadId, laneId, s, speed, width, length, height`                      |
| `RoadInfo`                  | `global_pos_x/y/z, local_pos_x/y/z, road_heading, curvature, speed_limit, roadId, laneId, s` |
| `RM_PositionData`           | `x, y, z, h, p, r, roadId, junctionId, laneId, laneOffset, s`                                |
| `RM_RoadLaneInfo`           | `pos (XYZ), heading, pitch, roll, width, curvature, speed_limit, roadId, laneId, s, t`       |
| `RM_RoadProbeInfo`          | `road_lane_info (RM_RoadLaneInfo), relative_pos (XYZ), relative_h`                           |
| `SimpleVehicleState`        | `x, y, z, h, p, speed, wheel_rotation, wheel_angle`                                          |
| `SE_SpeedActionStruct`      | `id, speed, transition_shape, transition_dim, transition_value`                              |
| `SE_LaneChangeActionStruct` | `id, mode, target, transition_shape, transition_dim, transition_value`                       |

______________________________________________________________________
