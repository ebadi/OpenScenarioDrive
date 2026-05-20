# OpenScenarioDrive Editor

![OpenScenarioDrive](installer/icon_small.png)

[![Build Installers](https://github.com/ebadi/OpenScenarioDrive/actions/workflows/build.yml/badge.svg)](https://github.com/ebadi/OpenScenarioDrive/actions/workflows/build.yml)

[![Download](https://img.shields.io/github/v/release/ebadi/OpenScenarioDrive?label=Download&logo=github)](../../releases/latest) &nbsp; <a href="../../releases/latest"><img src="installer/windows.svg" height="20" alt="Windows"/></a> <a href="../../releases/latest"><img src="installer/macos.svg" height="20" alt="macOS"/></a> <a href="../../releases/latest"><img src="installer/linux.svg" height="20" alt="Linux"/></a>

A PyQt6-based graphical controller and editor for OpenSCENARIO .xosc files. The application provides
a real-time simulation control interface with integrated XML editors for `.xosc` and `.xodr` files.

## Running the Application

Two modes are available depending on your goal.

### Option A - Pre-built Release (recommended for end users)

Download the latest release from the [GitHub Releases page](../../releases/latest). Each release is
built automatically by GitHub Actions and contains native installers for each platform.

#### Windows - Installer

Run `OpenScenarioDrive-Windows-Setup.exe` and follow the installer wizard.

> **Windows SmartScreen warning:** Because the installer is not code-signed, Windows Defender
> SmartScreen may show a "Windows protected your PC" dialog. Click **More info** and then **Run
> anyway** to proceed with the installation.

#### macOS - DMG

Open `OpenScenarioDrive-macOS.dmg`, drag **OpenScenarioDrive** to Applications, then launch it.

#### Linux - AppImage

The Linux release artifact is a ZIP that contains:

- `OpenScenarioDrive-Linux-x86_64.AppImage` - self-contained executable

Extract the ZIP and keep both items in the same directory, then run:

```bash
chmod +x ./OpenScenarioDrive-Linux-x86_64.AppImage
./OpenScenarioDrive-Linux-x86_64.AppImage
```

### Option B - Development with Docker

Please see [DEVELOPMENT.md](DEVELOPMENT.md)

## Features

### Simulation Control

- **Play / Pause / Restart / single-step** - scenario control
- **Rewind** - scrub through recorded frame history without re-running the simulation
- **Configurable time step** - adjust the simulation `dt` in the UI (0.001 s – 1.0 s)
- **Pause on event** - automatically pause when a storyboard event or condition fires

### Object Inspection

- Live list of all active actors/objects in the scenario
- Select any actor to view and edit its 3D position (X, Y, Z) and orientation (heading, pitch, roll)
- Apply position changes to the running simulation

### OpenScenario Editor

- XML syntax highlighting (tags, attributes, values)
- Line-number gutter with indent-based code folding (click ▾/▸ to toggle blocks)
- **Auto-save** - edits are flushed to a temporary file every 500 ms (no data loss on crash)
- **Undo / Redo** - full document history via undo stack
- **Search** - incremental find with forward/backward navigation and match highlighting
- **Dynamic highlighting** - when the simulation pauses on a storyboard event or condition trigger,
  the relevant XML element is automatically located, scrolled to, and highlighted

### OpenDrive Editor

- Same XML editor features as the OpenScenario editor
- Road ID cross-highlighting: selecting an actor highlights the matching `<road>` element

### Scenario Parameters

The **Parameters** panel lists every `<ParameterDeclaration>` exposed by the loaded scenario.

| Column | Description                                                        |
| ------ | ------------------------------------------------------------------ |
| Name   | Parameter name as declared in the `.xosc` file                     |
| Value  | Editable field - click any cell in this column to change the value |

To change a parameter click any cell in the **Value** column and type the new value and then click
**Apply and Restart** - the simulator restarts with the new values applied.

### Additional Panels

| Panel                 | Description                                                                             |
| --------------------- | --------------------------------------------------------------------------------------- |
| **Top-Down Viewport** | 2D bird's-eye view of the road network and moving actors                                |
| **World Properties**  | Current simulation time and active object count                                         |
| **Events**            | Colour-coded live log of storyboard state changes (blue) and condition triggers (green) |

## Credits

The scenario and road network files (`.xosc`, `.xodr`) bundled with this application are sourced from the [esmini](https://github.com/esmini/esmini) project (Environment Simulator Minimalistic) and are used under their respective licenses. Many thanks to the esmini contributors for providing these open resources.

[![License](https://img.shields.io/badge/License-BSD_3--Clause-blue.svg)](LICENSE.txt)