"""
XodrEditorPanel - syntax-highlighted, foldable .xodr (XML) editor.

The file path is delivered via the controller's odr_filename_ready signal
once the simulation worker resolves it with sim.get_odr_filename().
"""

from __future__ import annotations

import shutil

from PyQt6.QtCore import pyqtSlot
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QMessageBox, QTextEdit

from .editor import XmlEditorPanel


class XodrEditorPanel(XmlEditorPanel):
    """
    Dockable .xodr editor panel.

    Call ``load_file(path)`` to populate the editor.
    Call ``reset()`` before loading a different scenario.
    """

    def __init__(self, controller, parent=None) -> None:
        super().__init__(controller, parent)
        self._reload_btn.setToolTip(
            "Save edits to the .xodr file and reload the simulation.\n"
            "The edited .xodr is written back to the original path so the\n"
            "scenario can pick it up on restart."
        )
        self._save_btn.setToolTip("Overwrite the original .xodr file with your edits.")

    # ── Road highlighting ─────────────────────────────────────────────

    def highlight_road(self, road_id: int) -> None:
        """
        Highlight the ``<road … id="road_id" …>`` line in the XODR that
        matches *road_id*.  Only ``<road`` elements are matched, so lane
        IDs and junction IDs with the same number are not highlighted.
        Clears any previous highlight when called with a new road_id.
        """
        self._editor._event_extras = []

        if self._src_path is None:
            self._editor._highlight_current_line()
            return

        doc = self._editor.document()
        tok_fmt = self._amber_token_fmt()
        line_fmt = self._line_highlight_fmt()

        extras: list = []
        first_cursor: QTextCursor | None = None

        for quoted in (f'id="{road_id}"', f"id='{road_id}'"):
            block = doc.begin()
            while block.isValid():
                line = block.text()
                if "<road" in line:
                    idx = line.find(quoted)
                    if idx >= 0:
                        line_cur = QTextCursor(block)
                        line_cur.clearSelection()
                        line_sel = QTextEdit.ExtraSelection()
                        line_sel.cursor = line_cur
                        line_sel.format = line_fmt
                        extras.append(line_sel)

                        tok_cur = QTextCursor(block)
                        tok_cur.setPosition(block.position() + idx)
                        tok_cur.setPosition(
                            block.position() + idx + len(quoted),
                            QTextCursor.MoveMode.KeepAnchor,
                        )
                        tok_sel = QTextEdit.ExtraSelection()
                        tok_sel.cursor = tok_cur
                        tok_sel.format = tok_fmt
                        extras.append(tok_sel)

                        if first_cursor is None:
                            first_cursor = QTextCursor(tok_cur)
                block = block.next()

        self._apply_event_highlights(extras, first_cursor)

    # ── Load & Restart ────────────────────────────────────────────────

    @pyqtSlot()
    def _load_and_restart(self) -> None:
        """Write edits to the source .xodr and restart the simulation."""
        self._save_timer.stop()
        self._auto_save()
        if not (self._tmp_path and self._tmp_path.exists() and self._src_path):
            return
        try:
            shutil.copy2(self._tmp_path, self._src_path)
        except OSError as exc:
            QMessageBox.warning(self, "Save failed", str(exc))
            return
        self._controller.restart()
