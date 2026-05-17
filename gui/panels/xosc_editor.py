"""
XoscEditorPanel - syntax-highlighted, foldable .xosc (XML) editor.

Features
--------
* XML syntax highlighting (tags, attributes, values, comments, PIs)
* Line-number gutter + indent-based code folding (click ▾/▸ to toggle)
* Auto-save to a hidden sibling temp file on every edit (debounced 500 ms)
* Undo / Redo via QPlainTextEdit's built-in document history
* Load & Restart - flushes the temp file and feeds it to the simulation
* Save - overwrites the source .xosc file with the temp file contents
* Search - incremental find with forward / backward navigation and highlights
* highlight_element(name) - programmatically selects the first occurrence
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSlot
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QTextEdit

from .editor import XmlEditorPanel


class XoscEditorPanel(XmlEditorPanel):
    """
    Dockable .xosc editor panel.

    Call ``load_file(path)`` to populate the editor.
    Call ``reset()`` before loading a different scenario.
    Call ``highlight_element(name)`` to programmatically jump to a token.
    """

    # Maps esmini ELEMENT_TYPES strings → XOSC XML tag names used in search
    _ETYPE_TO_TAG: dict[str, str] = {
        "STORY_BOARD": "Storyboard",
        "STORY": "Story",
        "ACT": "Act",
        "MANEUVER_GROUP": "ManeuverGroup",
        "MANEUVER": "Maneuver",
        "EVENT": "Event",
        "ACTION": "Action",
    }

    def __init__(self, controller, parent=None) -> None:
        super().__init__(controller, parent)
        self._reload_btn.setToolTip(
            "Save edits to the temp file and reload the simulation from it.\n"
            "The original .xosc is NOT changed."
        )
        self._save_btn.setToolTip("Overwrite the original .xosc file with your edits.")
        controller.storyboard_event.connect(self._on_storyboard_event)
        controller.condition_triggered.connect(self._on_condition_triggered)

    # ── Load & Restart ────────────────────────────────────────────────

    @pyqtSlot()
    def _load_and_restart(self) -> None:
        self._save_timer.stop()
        self._auto_save()
        if self._tmp_path and self._tmp_path.exists():
            self._controller.load_scenario(str(self._tmp_path))

    # ── object / element highlight (called from object inspector) ─────

    def highlight_object(self, name: str) -> None:
        """
        Highlight every attribute value equal to *name* (e.g. name="Ego",
        entityRef="Ego") across the whole document in amber.
        """
        if self._src_path is None:
            return

        doc = self._editor.document()
        tok_fmt = self._amber_token_fmt()

        extras: list = []
        first_cursor: QTextCursor | None = None

        for quoted in (f'"{name}"', f"'{name}'"):
            cursor = QTextCursor(doc)
            while True:
                cursor = doc.find(quoted, cursor)
                if cursor.isNull():
                    break
                sel = QTextEdit.ExtraSelection()
                sel.cursor = QTextCursor(cursor)
                sel.format = tok_fmt
                extras.append(sel)
                if first_cursor is None:
                    first_cursor = QTextCursor(cursor)

        self._apply_event_highlights(extras, first_cursor)

    def highlight_element(self, name: str, elem_type: str = "") -> None:
        """
        Find the XML element whose name attribute equals *name* and highlight it.

        Search order:
          1. Line containing both ``<Tag`` (derived from elem_type) and
             ``name="X"`` - the most precise match.
          2. Bare ``name="X"`` / ``name='X'`` attribute anywhere in the document.
          3. Raw string *name* as a last resort.

        The matched token is highlighted in amber and the editor scrolls to it.
        The highlight persists until the next event or until reset().
        """
        if self._src_path is None:
            return

        cursor = self._find_element(name, elem_type)
        if cursor.isNull():
            return

        tok_sel = QTextEdit.ExtraSelection()
        tok_sel.cursor = QTextCursor(cursor)
        tok_sel.format = self._amber_token_fmt()

        line_cur = QTextCursor(cursor)
        line_cur.clearSelection()
        line_sel = QTextEdit.ExtraSelection()
        line_sel.cursor = line_cur
        line_sel.format = self._line_highlight_fmt()

        self._editor._event_extras = [line_sel, tok_sel]

        # setTextCursor triggers cursorPositionChanged → _highlight_current_line,
        # which rebuilds setExtraSelections([cur_line] + event_extras + search_extras).
        self._editor.setTextCursor(cursor)
        self._editor.ensureCursorVisible()
        self._editor.focus_folds()

    def _find_element(self, name: str, elem_type: str = "") -> QTextCursor:
        """
        Return a QTextCursor selecting the best match for *name* in the document.

        Strategy (first hit wins):
          1. Same-line match: line contains ``<XmlTag`` AND ``name="name"``
          2. Attribute-value match: ``name="name"`` or ``name='name'``
          3. Bare string match: ``name`` anywhere
        Returns a null cursor when nothing is found.
        """
        doc = self._editor.document()
        xml_tag = self._ETYPE_TO_TAG.get(elem_type, "")

        # ── strategy 1: same-line tag + attribute ─────────────────────
        if xml_tag:
            attr_dq = f'name="{name}"'
            attr_sq = f"name='{name}'"
            block = doc.begin()
            while block.isValid():
                line = block.text()
                if f"<{xml_tag}" in line:
                    for attr in (attr_dq, attr_sq):
                        idx = line.find(attr)
                        if idx >= 0:
                            cur = QTextCursor(block)
                            cur.setPosition(block.position() + idx)
                            cur.setPosition(
                                block.position() + idx + len(attr),
                                QTextCursor.MoveMode.KeepAnchor,
                            )
                            return cur
                block = block.next()

        # ── strategy 2: attribute-value anywhere ──────────────────────
        for attr in (f'name="{name}"', f"name='{name}'"):
            cur = doc.find(attr)
            if not cur.isNull():
                return cur

        # ── strategy 3: bare string ───────────────────────────────────
        return doc.find(name)  # may be null - caller checks

    # ── storyboard / condition highlight slots ────────────────────────

    @pyqtSlot(float, str, str, str)
    def _on_storyboard_event(
        self, _t: float, name: str, etype: str, _estate: str
    ) -> None:
        self.highlight_element(name, etype)

    @pyqtSlot(float, str)
    def _on_condition_triggered(self, _timestamp: float, name: str) -> None:
        self.highlight_element(name, "Condition")
