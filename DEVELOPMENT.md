### Development with Docker

Use this mode when contributing to the project or testing local changes. Docker builds esmini from
source and wires up all native library paths automatically.

#### Quick start

```bash
docker compose build
docker compose run test
docker compose run --rm -e SCENARIO=/app/esmini/resources/xosc/highway_merge_advanced.xosc gui
```

The application talks to esmini through [`esmini-python`](esmini-python) python package - a
self-contained Python [ctypes](https://docs.python.org/3/library/ctypes.html) wrapper around the
esmini native shared libraries (`libesminiLib` / `libesminiRMLib`). It is maintained here as part of
OpenScenarioDrive and is **not** part of the upstream esmini project. API documentation for the
wrapper is in [esmini-python/README.md](esmini-python/README.md).

> **esmini** is an open-source OpenSCENARIO player developed independently at
> <https://github.com/esmini/esmini>.

### Development setup (linting & pre-commit hooks)

After cloning and creating your Python environment, install the pre-commit hooks once:

```bash
pip install pre-commit
pre-commit install
```

The hooks (ruff lint/format, mypy, mdformat, conventional-commit check) will then run automatically
on every `git commit`. To run them manually against all files:

```bash
pre-commit run --all-files
```

#### Prerequisites

| Platform    | X11 server requirement                                                                                                      |
| ----------- | --------------------------------------------------------------------------------------------------------------------------- |
| **Linux**   | Run `xhost +local:docker` once per session                                                                                  |
| **macOS**   | Install [XQuartz](https://www.xquartz.org/), then run `xhost +localhost`                                                    |
| **Windows** | Install [VcXsrv](https://sourceforge.net/projects/vcxsrv/) or [X410](https://x410.app/) and enable "Disable access control" |

#### Architecture

```
gui/
├── __main__.py                  # Entry point
├── main_window.py               # QMainWindow - assembles all docks and toolbars
├── controller/
│   ├── simulation_controller.py # Main-thread mediator; owns SimulationWorker
│   └── simulation_worker.py     # QThread running the esmini step loop
├── panels/
│   ├── editor.py                # Base XmlEditorPanel (shared by xosc/xodr editors)
│   ├── xosc_editor.py           # .xosc editor with storyboard highlight integration
│   ├── xodr_editor.py           # .xodr editor with road highlight integration
│   ├── playback_panel.py        # Transport controls + rewind scrubber
│   ├── object_inspector.py      # Actor list + live position editor
│   ├── events_panel.py          # Storyboard / condition event log
│   ├── parameter_editor.py      # Scenario parameter editor
│   ├── viewport.py              # 2D top-down road/actor canvas
│   └── world_panel.py           # Sim time + world metadata
└── models/                      # Shared data models
esmini.py                        # Python ctypes wrapper for libesminiLib / libesminiRMLib
```

### Build the installer locally with `act` on Linux

[`act`](https://github.com/nektos/act) runs the GitHub Actions workflow on your machine inside
Docker, producing the same Linux AppImage that CI would publish - without pushing a tag or waiting
for a remote runner.

#### Prerequisites

- Docker with the daemon running
- The `act-build` image and its runner image pulled once (~1.5 GB):

```bash
docker compose build act-build
```

#### Run the build

Use the wrapper script - it resolves the esmini release tag on the host before invoking `act`, so no
`GITHUB_TOKEN` is required:

```bash
# Latest esmini release
./installer-act-build.sh

# Pin a specific esmini version
ESMINI_REF=v2.37.8 ./installer-act-build.sh
```

The AppImage is saved to `./dist/appimage/`

#### Why a wrapper script?

The workflow resolves the latest esmini tag by calling the GitHub API with `github.token`. When
running under `act` without a `GITHUB_TOKEN`, that call returns 401.
[`installer-act-build.sh`](installer-act-build.sh) fetches the tag on the host (unauthenticated,
fine for a public repo) and forwards it to `act` via `--input esmini_ref=<tag>`, so the workflow's
API call is skipped entirely.

#### How `act` works here

`act` uses Docker-out-of-Docker (DooD): the `act-build` container mounts the host Docker socket and
spawns runner containers as siblings. Both share `--network=host` so the act artifact server on
`127.0.0.1` is reachable from the runner without any extra DNS configuration. Project-level defaults
live in [`.actrc`](.actrc).

Only the Linux (`ubuntu-latest`) matrix job runs - the Windows job and the GitHub Release step are
skipped.

## Dependencies

All dependencies are installed automatically - inside the Docker image for development mode, and
bundled inside the AppImage / installer for packaged releases.
