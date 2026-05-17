# Credits and Licenses

OpenScenarioDrive is developed and maintained by **Hamid Ebadi** at [Infotiv](https://www.infotiv.se).
Source: <https://github.com/ebadi/OpenScenarioDrive> License: **BSD 3-Clause License**

______________________________________________________________________

## Runtime Dependencies

These libraries are bundled in or required by the distributed application.

### esmini

- **Version:** latest release (resolved at build time)
- **License:** Mozilla Public License 2.0 (MPL-2.0)
- **Copyright:** esmini contributors
- **Source:** <https://github.com/esmini/esmini>
- **License text:** <https://github.com/esmini/esmini/blob/master/LICENSE>

MPL-2.0 is a file-level copyleft license compatible with GPL-3.0 (per MPL-2.0 §3.3). Modified
MPL-licensed files must be distributed under MPL-2.0; the rest of the application is unaffected.

______________________________________________________________________

### PyQt6

- **Version:** ≥ 6.4.0
- **License:** GNU General Public License v3 (GPL-3.0-only) **or** Riverbank Commercial License
- **Copyright:** Riverbank Computing Limited
- **Source:** <https://www.riverbankcomputing.com/software/pyqt/>
- **License text:** <https://www.gnu.org/licenses/gpl-3.0.txt>

PyQt6 is dual-licensed. Unlike Qt itself, no LGPL option is available. Open-source distribution of
this application is governed by GPL-3.0. Commercial / proprietary distribution requires a Riverbank
Commercial License.

______________________________________________________________________

### Qt 6

- **Version:** 6.x (bundled via the `PyQt6-Qt6` wheel)
- **License:** GNU Lesser General Public License v3 (LGPL-3.0-only) for most modules
- **Copyright:** The Qt Company Ltd.
- **Source:** <https://www.qt.io>
- **License text:** <https://www.gnu.org/licenses/lgpl-3.0.txt>

The Qt libraries are accessed through PyQt6 bindings; the effective license governing the combined
work is GPL-3.0 (from PyQt6 above).

______________________________________________________________________

### PyQt6-sip

- **Version:** ≥ 13.8
- **License:** BSD 2-Clause "Simplified" License
- **Copyright:** Phil Thompson, Riverbank Computing Ltd.
- **Source:** <https://github.com/Python-SIP/sip>

______________________________________________________________________

### OpenSceneGraph (OSG)

- **Version:** bundled with esmini release binaries (version reflected in the `osgPlugins-x.y.z/`
  directory)
- **License:** OpenSceneGraph Public License v1.0 (OSGPL) - LGPL-2.1-only with wxWindows exception
- **Copyright:** Robert Osfield and OSG contributors
- **Source:** <https://openscenegraph.github.io/openscenegraph.io/>
- **License text:** <https://github.com/openscenegraph/OpenSceneGraph/blob/master/LICENSE.txt>

The wxWindows exception removes the relinking requirement for applications that merely link against
OSG, making it compatible with GPL-3.0 and proprietary applications alike.

______________________________________________________________________

### XCB / X11 Libraries (Linux only)

The following system libraries are bundled in the Linux AppImage to satisfy Qt 6's XCB platform
plugin:

| Library            | License |
| ------------------ | ------- |
| libxcb-cursor      | MIT     |
| libxcb-icccm       | MIT     |
| libxcb-image       | MIT     |
| libxcb-keysyms     | MIT     |
| libxcb-randr       | MIT     |
| libxcb-render-util | MIT     |
| libxcb-shape       | MIT     |
| libxcb-xinerama    | MIT     |
| libxcb-xkb         | MIT     |
| libxkbcommon       | MIT     |
| libxkbcommon-x11   | MIT     |

Copyright: X.Org Foundation, XCB contributors, and respective authors. Source:
<https://xcb.freedesktop.org> / <https://xkbcommon.org>

______________________________________________________________________

### Python

- **Version:** 3.11+
- **License:** Python Software Foundation License v2 (PSF-2.0)
- **Copyright:** Python Software Foundation
- **Source:** <https://www.python.org>
- **License text:** <https://docs.python.org/3/license.html>

______________________________________________________________________

## Build Tools

Used only during CI packaging; not present in distributed binaries.

| Tool                      | Version | License                                     | Notes                                                                      |
| ------------------------- | ------- | ------------------------------------------- | -------------------------------------------------------------------------- |
| PyInstaller               | 6.x     | GPL-2.0-or-later WITH PyInstaller-exception | The Bootloader Exception means frozen executables are not GPL-contaminated |
| pyinstaller-hooks-contrib | 2026.x  | GPL-2.0-or-later / Apache-2.0               | Provides hooks for correct PyQt6 bundling                                  |

______________________________________________________________________

## Development / Test Dependencies

Used only for running the test suite; not shipped in any artifact.

| Package   | License                    | Notes                        |
| --------- | -------------------------- | ---------------------------- |
| pytest    | MIT                        | Test framework               |
| iniconfig | MIT                        | pytest dependency            |
| pluggy    | MIT                        | pytest plugin engine         |
| packaging | Apache-2.0 OR BSD-2-Clause | pytest version utilities     |
| Pygments  | BSD-2-Clause               | pytest terminal highlighting |

______________________________________________________________________

## Licensing Summary

| Dependency         | SPDX License                   | Distribution impact                                                                 |
| ------------------ | ------------------------------ | ----------------------------------------------------------------------------------- |
| esmini             | MPL-2.0                        | Modified esmini files must remain MPL-2.0; compatible with GPL-3.0                  |
| PyQt6              | GPL-3.0-only                   | Open-source distribution must be GPL-3.0; commercial use requires Riverbank license |
| Qt 6               | LGPL-3.0-only                  | Superseded by PyQt6's GPL-3.0 in this context                                       |
| PyQt6-sip          | BSD-2-Clause                   | Permissive; no constraints                                                          |
| OpenSceneGraph     | LGPL-2.1 + wxWindows exception | wxWindows exception permits linking without LGPL obligation                         |
| XCB / X11 libs     | MIT                            | Permissive; no constraints                                                          |
| Python             | PSF-2.0                        | Permissive; compatible with GPL-3.0                                                 |
| PyInstaller        | GPL-2.0+ WITH exception        | Bootloader exception: distributed binaries are unaffected                           |
| pytest / dev tools | MIT / Apache-2.0 / BSD         | Dev-only; no impact on distributed artifacts                                        |
