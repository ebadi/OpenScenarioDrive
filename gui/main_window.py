"""
MainWindow - QMainWindow with dockable panels.

Layout
------
  Toolbar row 1 : Open button + current file name / path
  Toolbar row 2 : PlaybackPanel  (transport + rewind scrubber + dt control +
                                  integrated sim time / object count)
  Centre        : TopDownViewport  (2D bird's-eye simulation view)
  Left dock     : ObjectInspectorPanel  (actor list + position editor)
  Right dock    : EventsPanel / Parameters / XOSC editor / XODR editor  (tabbed)

Drag-and-drop: drop a .xosc file anywhere on the window to load it.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QAction, QDragEnterEvent, QDropEvent, QKeySequence
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDockWidget,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStatusBar,
    QStyle,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .controller.simulation_controller import SimulationController
from .panels.events_panel import EventsPanel
from .panels.object_inspector import ObjectInspectorPanel
from .panels.parameter_editor import ParameterEditorPanel
from .panels.playback_panel import PlaybackPanel
from .panels.viewport import TopDownViewport
from .panels.xodr_editor import XodrEditorPanel
from .panels.xosc_editor import XoscEditorPanel


class MainWindow(QMainWindow):
    def __init__(
        self,
        lib_dir: str,
        resource_root: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("OpenScenarioDrive")
        self.resize(1400, 860)

        self._controller = SimulationController(self)
        self._controller.set_environment(lib_dir, resource_root)

        self._build_ui()
        self._connect_signals()
        self.setAcceptDrops(True)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self._build_toolbar()
        self._build_central()
        self._build_docks()
        self._build_status_bar()

    def _build_toolbar(self) -> None:
        # ── Row 1: open button + file info ──────────────────────────────
        tb = QToolBar("Main", self)
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(tb)

        open_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon)
        open_act = QAction(open_icon, "Open a new Scenario…", self)
        open_act.setShortcut(QKeySequence.StandardKey.Open)
        open_act.triggered.connect(self._open_scenario)
        tb.addAction(open_act)

        tb.addSeparator()

        self._file_label = QLabel("No scenario loaded")
        self._file_label.setStyleSheet("color: #a6adc8; padding-left: 4px;")
        self._file_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        tb.addWidget(self._file_label)

        about_btn = QPushButton("About")
        about_btn.setFixedWidth(60)
        about_btn.clicked.connect(self._show_about)
        tb.addWidget(about_btn)

        # ── Row 2: playback controls ─────────────────────────────────────
        pb_tb = QToolBar("Playback", self)
        pb_tb.setMovable(False)
        self.addToolBarBreak()
        self.addToolBar(pb_tb)

        self._playback = PlaybackPanel(self._controller, self)
        pb_tb.addWidget(self._playback)

    def _build_central(self) -> None:
        self._viewport = TopDownViewport(self)
        self.setCentralWidget(self._viewport)

    def _build_docks(self) -> None:
        # ── Object Inspector - left ─────────────────────────────────────
        self._inspector = ObjectInspectorPanel(self._controller, self)
        insp_dock = QDockWidget("Object Inspector", self)
        insp_dock.setWidget(self._inspector)
        insp_dock.setMinimumWidth(240)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, insp_dock)

        # ── Events log - right ──────────────────────────────────────────
        self._events = EventsPanel(self)
        events_dock = QDockWidget("Events", self)
        events_dock.setWidget(self._events)
        events_dock.setMinimumWidth(280)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, events_dock)

        # ── Parameter editor - right, tabbed with Events ─────────────────
        self._param_editor = ParameterEditorPanel(self._controller, self)
        param_dock = QDockWidget("Parameters", self)
        param_dock.setWidget(self._param_editor)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, param_dock)
        self.tabifyDockWidget(events_dock, param_dock)

        # ── XOSC editor - right, tabbed with Events / Parameters ────────
        self._xosc_editor = XoscEditorPanel(self._controller, self)
        xosc_dock = QDockWidget("OpenScenario Editor", self)
        xosc_dock.setWidget(self._xosc_editor)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, xosc_dock)
        self.tabifyDockWidget(param_dock, xosc_dock)

        # ── XODR editor - right, tabbed with XOSC editor ────────────────
        self._xodr_editor = XodrEditorPanel(self._controller, self)
        xodr_dock = QDockWidget("OpenDrive Editor", self)
        xodr_dock.setWidget(self._xodr_editor)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, xodr_dock)
        self.tabifyDockWidget(xosc_dock, xodr_dock)

        def _post_layout() -> None:
            self.resizeDocks(
                [xosc_dock], [self.width() // 2], Qt.Orientation.Horizontal
            )
            xosc_dock.raise_()

        QTimer.singleShot(0, _post_layout)

    def _build_status_bar(self) -> None:
        bar = QStatusBar(self)
        self.setStatusBar(bar)
        self._status_label = QLabel("No scenario loaded")
        bar.addWidget(self._status_label)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        c = self._controller
        c.scenario_loading.connect(self._on_scenario_loading)
        c.state_updated.connect(self._on_state_updated)
        c.road_network_ready.connect(self._viewport.set_road_network)
        c.odr_filename_ready.connect(self._xodr_editor.load_file)
        c.parameters_ready.connect(self._param_editor.load_parameters)
        c.storyboard_event.connect(self._events.on_storyboard_event)
        c.condition_triggered.connect(self._events.on_condition_triggered)
        c.sim_finished.connect(self._events.on_sim_finished)
        c.road_load_warning.connect(self._on_road_load_warning)
        c.error_occurred.connect(self._on_error)
        c.status_changed.connect(self._status_label.setText)
        c.sim_finished.connect(
            lambda: self._status_label.setText("Simulation finished")
        )
        self._inspector.object_selected.connect(self._xosc_editor.highlight_object)
        self._inspector.object_selected.connect(self._viewport.select_object_by_name)
        self._inspector.object_road_selected.connect(self._xodr_editor.highlight_road)
        self._inspector.object_road_selected.connect(self._viewport.select_road)
        self._viewport.object_clicked.connect(self._inspector.select_by_id)
        self._viewport.road_clicked.connect(self._xodr_editor.highlight_road)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @pyqtSlot()
    def _on_scenario_loading(self) -> None:
        """Reset simulation-derived panels before a new scenario starts."""
        self._viewport.reset()
        self._inspector.reset()
        self._playback.reset()
        self._events.clear()
        self._param_editor.reset()
        self._xodr_editor.reset()
        # Note: _xosc_editor is NOT reset here - it handles its own state.
        # reset() + load_file() are called from _load_scenario() so that
        # reloads triggered by the editor itself don't clobber its content.

    @pyqtSlot()
    def _open_scenario(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open OpenSCENARIO",
            "/app/esmini/resources/xosc",
            "OpenSCENARIO (*.xosc);;All files (*)",
        )
        if path:
            self._load_scenario(path)

    def load_scenario(self, path: str) -> None:
        self._load_scenario(path)

    def _load_scenario(self, path: str) -> None:
        """
        Load a new source .xosc file.

        Resets and repopulates the XOSC editor only when the path is a
        genuine source file - not a temp file created by the editor itself.
        """
        editor_tmp = (
            str(self._xosc_editor._tmp_path)
            if self._xosc_editor._tmp_path is not None
            else None
        )
        self._controller.load_scenario(path)
        if path != editor_tmp:
            self._xosc_editor.reset()
            self._xosc_editor.load_file(path)
            p = Path(path)
            self._file_label.setText(f"{p.name}   -   {p}")

    @pyqtSlot(float, list)
    def _on_state_updated(self, t: float, objects: list) -> None:
        self._viewport.update_objects(objects)
        self._inspector.update_objects(objects)

    @pyqtSlot(str)
    def _on_road_load_warning(self, message: str) -> None:
        QMessageBox.warning(self, "Road Network Unavailable", message)

    @pyqtSlot(str)
    def _on_error(self, message: str) -> None:
        QMessageBox.critical(self, "Simulation Error", message)

    @pyqtSlot()
    def _show_about(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("About")
        dlg.setMinimumWidth(380)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(10)

        title = QLabel("<b>OpenDrive Scenario Editor</b>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        info = QLabel(
            "This project is started and currently maintained by <b>Hamid Ebadi</b>.<br><br>"
            '<a href="https://github.com/ebadi/OpenScenarioDrive">'
            "https://github.com/ebadi/OpenScenarioDrive</a><br><br>"
            "Source license: BSD 3-Clause License<br>"
            "Distributed binary: GPL-3.0 (via PyQt6)<br><br>"
            "<b>Third-party content</b><br>"
            "Scenario and road network files (.xosc, .xodr) are sourced from the "
            '<a href="https://github.com/esmini/esmini">esmini</a> project '
            "and are used under their respective licenses.<br>"
        )
        info.setOpenExternalLinks(True)
        info.setWordWrap(True)
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(dlg.accept)
        layout.addWidget(buttons)

        dlg.exec()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            if any(
                u.isLocalFile() and u.toLocalFile().lower().endswith(".xosc")
                for u in event.mimeData().urls()
            ):
                event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            if url.isLocalFile():
                path = url.toLocalFile()
                if path.lower().endswith(".xosc"):
                    self._load_scenario(path)
                    event.acceptProposedAction()
                    break

    def closeEvent(self, event) -> None:
        self._controller._stop_worker()
        super().closeEvent(event)
