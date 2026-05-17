"""
editor.py - shared XML editor primitives.

Provides:
  _XmlHighlighter  - regex-based XML syntax highlighter
  _Gutter          - line-number + fold-triangle gutter widget
  _XmlEdit         - QPlainTextEdit with gutter, folding, and auto-indent
  XmlEditorPanel   - base dockable panel (toolbar, search, auto-save)

Subclass XmlEditorPanel and implement _load_and_restart() to build
scenario-specific editors (XoscEditorPanel, XodrEditorPanel).
"""

from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path

from PyQt6.QtCore import QRect, QSize, Qt, QTimer, pyqtSlot
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QKeySequence,
    QPainter,
    QPalette,
    QShortcut,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextFormat,
)
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

_log = logging.getLogger(f"OpenScenarioDrive.{__name__}")

# ─────────────────────────────────────────────────────────────────────────────
# Syntax highlighter
# ─────────────────────────────────────────────────────────────────────────────


class _XmlHighlighter(QSyntaxHighlighter):
    """Regex-based XML syntax highlighter with multi-line comment support."""

    def __init__(self, document: QTextDocument) -> None:
        super().__init__(document)
        self._rules: list[tuple[re.Pattern, QTextCharFormat]] = []
        self._comment_start = re.compile(r"<!--")
        self._comment_end = re.compile(r"-->")
        self._comment_fmt = self._fmt("#7f848e", italic=True)
        self._build_rules()

    @staticmethod
    def _fmt(color: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
        f = QTextCharFormat()
        f.setForeground(QColor(color))
        if bold:
            f.setFontWeight(700)
        if italic:
            f.setFontItalic(True)
        return f

    def _build_rules(self) -> None:
        r = self._rules.append
        r((re.compile(r"<\?[^?]*\?>"), self._fmt("#c792ea")))  # PI
        r(
            (re.compile(r"<!\[CDATA\[.*?\]\]>", re.DOTALL), self._fmt("#89ddff"))
        )  # CDATA
        r(
            (re.compile(r"<!DOCTYPE[^>]*>"), self._fmt("#7f848e", italic=True))
        )  # DOCTYPE
        r((re.compile(r"</|/>|<|>"), self._fmt("#89b4fa", bold=True)))  # brackets
        r(
            (
                re.compile(r"(?<=</)[A-Za-z][A-Za-z0-9_:-]*"),
                self._fmt("#89dceb", bold=True),
            )
        )  # closing tag names
        r(
            (
                re.compile(r"(?<=<)[A-Za-z][A-Za-z0-9_:-]*"),
                self._fmt("#89dceb", bold=True),
            )
        )  # opening tag names
        r(
            (re.compile(r"\b[A-Za-z_][A-Za-z0-9_:-]*(?=\s*=)"), self._fmt("#cba6f7"))
        )  # attr names
        r((re.compile(r'"[^"]*"'), self._fmt("#a6e3a1")))  # double-quoted values
        r((re.compile(r"'[^']*'"), self._fmt("#a6e3a1")))  # single-quoted values

    def highlightBlock(self, text: str) -> None:
        for pattern, fmt in self._rules:
            for m in pattern.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), fmt)

        # Multi-line comment state machine
        self.setCurrentBlockState(0)
        start = 0
        if self.previousBlockState() != 1:
            m = self._comment_start.search(text)  # type: ignore[assignment]
            if not m:
                return
            start = m.start()

        while start >= 0:
            m_end = self._comment_end.search(text, start)
            if m_end:
                self.setFormat(start, m_end.end() - start, self._comment_fmt)
                nxt = self._comment_start.search(text, m_end.end())
                start = nxt.start() if nxt else -1
            else:
                self.setCurrentBlockState(1)
                self.setFormat(start, len(text) - start, self._comment_fmt)
                break


# ─────────────────────────────────────────────────────────────────────────────
# Gutter widget (line numbers + fold triangles)
# ─────────────────────────────────────────────────────────────────────────────


class _Gutter(QWidget):
    def __init__(self, editor: _XmlEdit) -> None:
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self._editor._gutter_width(), 0)

    def paintEvent(self, event) -> None:
        self._editor._paint_gutter(event)

    def mousePressEvent(self, event) -> None:
        self._editor._gutter_click(event)


# ─────────────────────────────────────────────────────────────────────────────
# Editor widget
# ─────────────────────────────────────────────────────────────────────────────


class _XmlEdit(QPlainTextEdit):
    _FOLD_OPEN = "▾"
    _FOLD_CLOSE = "▸"
    _FOLD_ICON_W = 18  # pixels reserved for the fold triangle

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Base, QColor("#1e1e2e"))
        pal.setColor(QPalette.ColorRole.Text, QColor("#cdd6f4"))
        pal.setColor(QPalette.ColorRole.Window, QColor("#1e1e2e"))
        pal.setColor(QPalette.ColorRole.WindowText, QColor("#cdd6f4"))
        self.setPalette(pal)

        font = QFont("Monospace", 13)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        self.setTabStopDistance(QFontMetrics(font).horizontalAdvance(" ") * 4)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        self._gutter = _Gutter(self)
        self._folds: dict[int, int] = {}  # start_block_no → end_block_no
        self._folded: set[int] = set()
        self._event_extras: list = []  # highlight from storyboard / condition
        self._search_extras: list = []

        self.blockCountChanged.connect(self._update_gutter_width)
        self.updateRequest.connect(self._update_gutter)
        self.cursorPositionChanged.connect(self._highlight_current_line)

        self._update_gutter_width()
        self._highlight_current_line()

    # ── gutter geometry ───────────────────────────────────────────────

    def _gutter_width(self) -> int:
        digits = max(3, len(str(max(1, self.blockCount()))))
        return (
            QFontMetrics(self.font()).horizontalAdvance("9") * digits
            + self._FOLD_ICON_W
            + 6
        )

    def _update_gutter_width(self, _=None) -> None:
        self.setViewportMargins(self._gutter_width(), 0, 0, 0)

    def _update_gutter(self, rect: QRect, dy: int) -> None:
        if dy:
            self._gutter.scroll(0, dy)
        else:
            self._gutter.update(0, rect.y(), self._gutter.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_gutter_width()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._gutter.setGeometry(
            QRect(cr.left(), cr.top(), self._gutter_width(), cr.height())
        )

    def _is_highlighted_block(self, block_no: int) -> bool:
        """Return True if *block_no* overlaps any event or search extra selection."""
        doc = self.document()
        block = doc.findBlockByNumber(block_no)
        if not block.isValid():
            return False
        ps = block.position()
        pe = ps + max(0, block.length() - 1)
        for sel in self._event_extras + self._search_extras:
            a = min(sel.cursor.anchor(), sel.cursor.position())
            b = max(sel.cursor.anchor(), sel.cursor.position())
            if a <= pe and b >= ps:
                return True
        return False

    def _paint_gutter(self, event) -> None:
        painter = QPainter(self._gutter)
        painter.fillRect(event.rect(), QColor("#181825"))

        fh = self.fontMetrics().height()
        num_w = self._gutter_width() - self._FOLD_ICON_W

        block = self.firstVisibleBlock()
        block_no = block.blockNumber()
        top = int(
            self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        )
        bottom = top + int(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                # Line number - amber when highlighted, dim gray otherwise
                num_color = (
                    QColor("#f9e2af")
                    if self._is_highlighted_block(block_no)
                    else QColor("#6c7086")
                )
                painter.setPen(num_color)
                painter.drawText(
                    0,
                    top,
                    num_w,
                    fh,
                    Qt.AlignmentFlag.AlignRight,
                    str(block_no + 1),
                )
                # Fold triangle
                if block_no in self._folds:
                    painter.setPen(QColor("#89b4fa"))
                    sym = (
                        self._FOLD_CLOSE
                        if block_no in self._folded
                        else self._FOLD_OPEN
                    )
                    painter.drawText(
                        num_w + 2,
                        top,
                        self._FOLD_ICON_W - 2,
                        fh,
                        Qt.AlignmentFlag.AlignLeft,
                        sym,
                    )

            block = block.next()
            block_no += 1
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())

    def _gutter_click(self, event) -> None:
        num_w = self._gutter_width() - self._FOLD_ICON_W
        if event.position().x() < num_w:
            return
        y = int(event.position().y())
        block = self.firstVisibleBlock()
        top = int(
            self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        )
        bottom = top + int(self.blockBoundingRect(block).height())
        while block.isValid():
            if top <= y <= bottom:
                if block.blockNumber() in self._folds:
                    self._toggle_fold(block.blockNumber())
                return
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())

    # ── current-line highlight ────────────────────────────────────────

    def _highlight_current_line(self) -> None:
        sel = QTextEdit.ExtraSelection()
        sel.format.setBackground(QColor("#313244"))
        sel.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        sel.cursor = self.textCursor()
        sel.cursor.clearSelection()
        self.setExtraSelections([sel] + self._event_extras + self._search_extras)

    # ── auto-indent ───────────────────────────────────────────────────

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            cursor = self.textCursor()
            line = cursor.block().text()
            indent = len(line) - len(line.lstrip())
            stripped = line.rstrip()
            # Extra indent after an opening tag (not self-closing, not comment close)
            if (
                stripped.endswith(">")
                and not stripped.endswith("/>")
                and not stripped.endswith("-->")
            ):
                indent += 4
            super().keyPressEvent(event)
            self.insertPlainText(" " * indent)
        else:
            super().keyPressEvent(event)

    # ── code folding ─────────────────────────────────────────────────

    def detect_folds(self) -> None:
        """Build the fold map by analysing indentation levels."""
        self._folds.clear()
        self._folded.clear()

        doc = self.document()
        n = doc.blockCount()

        # -1 means blank / whitespace-only line
        indents: list[int] = []
        for i in range(n):
            txt = doc.findBlockByNumber(i).text()
            indents.append(len(txt) - len(txt.lstrip()) if txt.strip() else -1)

        for i in range(n - 1):
            if indents[i] < 0:
                continue
            # Find the next non-blank line
            j = i + 1
            while j < n and indents[j] < 0:
                j += 1
            if j >= n or indents[j] <= indents[i]:
                continue
            # i is a fold start - scan forward for the matching dedent
            target = indents[i]
            k = j + 1
            while k < n:
                if indents[k] >= 0 and indents[k] <= target:
                    break
                k += 1
            end_bn = k - 1
            # Skip trailing blank lines
            while end_bn > i and indents[end_bn] < 0:
                end_bn -= 1
            if end_bn > i:
                self._folds[i] = end_bn

        self._gutter.update()

    def _toggle_fold(self, start_bn: int) -> None:
        end_bn = self._folds.get(start_bn)
        if end_bn is None:
            return

        doc = self.document()
        folding = start_bn not in self._folded

        if folding:
            self._folded.add(start_bn)
        else:
            self._folded.discard(start_bn)

        block = doc.findBlockByNumber(start_bn + 1)
        while block.isValid() and block.blockNumber() <= end_bn:
            block.setVisible(not folding)
            block = block.next()

        sb = doc.findBlockByNumber(start_bn + 1)
        eb = doc.findBlockByNumber(end_bn)
        if sb.isValid() and eb.isValid():
            doc.markContentsDirty(
                sb.position(),
                eb.position() + eb.length() - sb.position(),
            )
        self.viewport().update()
        self._gutter.update()

    def focus_folds(self) -> None:
        """Expand folds that contain an event highlight; collapse all others."""
        if not self._folds:
            return

        doc = self.document()
        highlighted: set[int] = set()
        for sel in self._event_extras:
            a = min(sel.cursor.anchor(), sel.cursor.position())
            b = max(sel.cursor.anchor(), sel.cursor.position())
            blk = doc.findBlock(a)
            while blk.isValid() and blk.position() <= b:
                highlighted.add(blk.blockNumber())
                blk = blk.next()

        if not highlighted:
            return

        dirty_start: int | None = None
        dirty_end: int | None = None

        for start_bn in sorted(self._folds):
            end_bn = self._folds[start_bn]
            want_folded = not any(start_bn <= bn <= end_bn for bn in highlighted)
            is_folded = start_bn in self._folded

            if want_folded == is_folded:
                continue

            if want_folded:
                self._folded.add(start_bn)
            else:
                self._folded.discard(start_bn)

            blk = doc.findBlockByNumber(start_bn + 1)
            while blk.isValid() and blk.blockNumber() <= end_bn:
                blk.setVisible(not want_folded)
                blk = blk.next()

            sb_pos = doc.findBlockByNumber(start_bn + 1).position()
            eb = doc.findBlockByNumber(end_bn)
            eb_pos = eb.position() + eb.length()
            if dirty_start is None or sb_pos < dirty_start:
                dirty_start = sb_pos
            if dirty_end is None or eb_pos > dirty_end:
                dirty_end = eb_pos

        if dirty_start is not None:
            doc.markContentsDirty(dirty_start, dirty_end - dirty_start)  # type: ignore[operator]
            self.viewport().update()
            self._gutter.update()


# ─────────────────────────────────────────────────────────────────────────────
# Base panel
# ─────────────────────────────────────────────────────────────────────────────


class XmlEditorPanel(QWidget):
    """
    Base dockable XML editor panel.

    Provides toolbar (Undo / Redo / Load & Restart / Save), incremental
    search, debounced auto-save to a sibling temp file, and fold detection.

    Subclass and implement ``_load_and_restart()`` for scenario-specific
    reload behaviour.
    """

    def __init__(self, controller, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller
        self._src_path: Path | None = None
        self._tmp_path: Path | None = None
        self._search_results: list[int] = []
        self._search_idx: int = 0

        self._build_ui()

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(500)
        self._save_timer.timeout.connect(self._auto_save)
        self._editor.document().contentsChanged.connect(self._save_timer.start)

    # ── UI construction ───────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        # ── toolbar row ───────────────────────────────────────────────
        bar = QHBoxLayout()
        bar.setSpacing(4)

        self._undo_btn = QPushButton("↩ Undo  [Ctrl+Z]")
        self._undo_btn.setMinimumWidth(120)
        self._undo_btn.setEnabled(False)
        bar.addWidget(self._undo_btn)

        self._redo_btn = QPushButton("↪ Redo  [Ctrl+Y]")
        self._redo_btn.setMinimumWidth(120)
        self._redo_btn.setEnabled(False)
        bar.addWidget(self._redo_btn)

        bar.addStretch()

        self._reload_btn = QPushButton("▶ Load & Restart  [Ctrl+↵]")
        self._reload_btn.setMinimumWidth(200)
        self._reload_btn.setEnabled(False)
        bar.addWidget(self._reload_btn)

        self._save_btn = QPushButton("Save  [Ctrl+S]")
        self._save_btn.setMinimumWidth(100)
        self._save_btn.setEnabled(False)
        bar.addWidget(self._save_btn)

        root.addLayout(bar)

        # ── search row ────────────────────────────────────────────────
        search_row = QHBoxLayout()
        search_row.setSpacing(4)

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search…  [Ctrl+F]")
        self._search_edit.returnPressed.connect(self._find_next)
        search_row.addWidget(self._search_edit)

        prev_btn = QPushButton("▲")
        prev_btn.setFixedWidth(28)
        prev_btn.setToolTip("Previous match")
        prev_btn.clicked.connect(self._find_prev)
        search_row.addWidget(prev_btn)

        next_btn = QPushButton("▼")
        next_btn.setFixedWidth(28)
        next_btn.setToolTip("Next match")
        next_btn.clicked.connect(self._find_next)
        search_row.addWidget(next_btn)

        self._match_lbl = QLabel("")
        self._match_lbl.setFixedWidth(80)
        self._match_lbl.setStyleSheet("color: #a6adc8; font-size: 9px;")
        search_row.addWidget(self._match_lbl)

        self._search_widget = QWidget()
        self._search_widget.setLayout(search_row)
        root.addWidget(self._search_widget)

        # ── editor ────────────────────────────────────────────────────
        self._editor = _XmlEdit(self)
        self._highlighter = _XmlHighlighter(self._editor.document())
        root.addWidget(self._editor)

        # ── wire signals ──────────────────────────────────────────────
        self._undo_btn.clicked.connect(self._editor.undo)
        self._redo_btn.clicked.connect(self._editor.redo)
        self._editor.document().undoAvailable.connect(self._undo_btn.setEnabled)
        self._editor.document().redoAvailable.connect(self._redo_btn.setEnabled)
        self._reload_btn.clicked.connect(self._load_and_restart)
        self._save_btn.clicked.connect(self._save_to_source)
        self._search_edit.textChanged.connect(self._run_search)

        # ── panel-scoped keyboard shortcuts ───────────────────────────
        # Ctrl+Z / Ctrl+Y are handled natively by QPlainTextEdit;
        # the shortcuts below only cover actions the editor doesn't own.
        sc_save = QShortcut(QKeySequence("Ctrl+S"), self)
        sc_save.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc_save.activated.connect(self._save_to_source)

        sc_run = QShortcut(QKeySequence("Ctrl+Return"), self)
        sc_run.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc_run.activated.connect(self._load_and_restart)

        sc_find = QShortcut(QKeySequence("Ctrl+F"), self)
        sc_find.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc_find.activated.connect(self._focus_search)

    def _focus_search(self) -> None:
        self._search_edit.setFocus()
        self._search_edit.selectAll()

    # ── shared highlight helpers ──────────────────────────────────────

    @staticmethod
    def _amber_token_fmt() -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setBackground(QColor("#f9e2af"))
        fmt.setForeground(QColor("#1e1e2e"))
        return fmt

    @staticmethod
    def _line_highlight_fmt() -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setBackground(QColor("#2d2d44"))
        fmt.setProperty(QTextFormat.Property.FullWidthSelection, True)
        return fmt

    def _apply_event_highlights(
        self, extras: list, first_cursor: QTextCursor | None
    ) -> None:
        """Commit *extras* as event highlights and scroll to *first_cursor*."""
        self._editor._event_extras = extras
        if first_cursor is not None:
            self._editor.setTextCursor(first_cursor)
            self._editor.ensureCursorVisible()
        else:
            self._editor._highlight_current_line()
        self._editor.focus_folds()

    # ── public API ────────────────────────────────────────────────────

    def load_file(self, path: str) -> None:
        """Read *path* into the editor and initialise the temp-file path."""
        src = Path(path)
        if not src.exists():
            return

        self._src_path = src
        self._tmp_path = src.parent / f".{src.stem}_edit{src.suffix}"

        doc = self._editor.document()
        doc.contentsChanged.disconnect(self._save_timer.start)
        self._editor.setPlainText(src.read_text(encoding="utf-8", errors="replace"))
        doc.setModified(False)
        doc.contentsChanged.connect(self._save_timer.start)

        shutil.copy2(src, self._tmp_path)

        self._reload_btn.setEnabled(True)
        self._save_btn.setEnabled(True)

        QTimer.singleShot(0, self._editor.detect_folds)

    def reset(self) -> None:
        """Clear editor state - call before loading a new source file."""
        self._save_timer.stop()
        self._editor.clear()
        self._editor._folds.clear()
        self._editor._folded.clear()
        self._editor._event_extras.clear()
        self._editor._search_extras.clear()
        self._src_path = None
        self._tmp_path = None
        self._search_results.clear()
        self._match_lbl.setText("")
        self._reload_btn.setEnabled(False)
        self._save_btn.setEnabled(False)

    # ── to be implemented by subclasses ──────────────────────────────

    @pyqtSlot()
    def _load_and_restart(self) -> None:
        raise NotImplementedError

    # ── auto-save ─────────────────────────────────────────────────────

    def _auto_save(self) -> None:
        if self._tmp_path is None:
            return
        try:
            self._tmp_path.write_text(self._editor.toPlainText(), encoding="utf-8")
        except OSError as exc:
            _log.warning("Auto-save to %s failed: %s", self._tmp_path, exc)

    # ── Save ──────────────────────────────────────────────────────────

    @pyqtSlot()
    def _save_to_source(self) -> None:
        if not self._src_path or not self._tmp_path:
            return
        self._save_timer.stop()
        self._auto_save()
        try:
            shutil.copy2(self._tmp_path, self._src_path)
        except OSError as exc:
            QMessageBox.warning(self, "Save failed", str(exc))

    # ── Search ────────────────────────────────────────────────────────

    def _run_search(self, text: str) -> None:
        self._editor._search_extras.clear()
        self._search_results.clear()
        self._search_idx = 0

        if not text:
            self._match_lbl.setText("")
            self._editor._highlight_current_line()
            return

        hit_fmt = self._amber_token_fmt()

        doc = self._editor.document()
        cursor = QTextCursor(doc)

        while True:
            cursor = doc.find(text, cursor)
            if cursor.isNull():
                break
            self._search_results.append(cursor.anchor())
            sel = QTextEdit.ExtraSelection()
            sel.cursor = QTextCursor(cursor)
            sel.format = hit_fmt
            self._editor._search_extras.append(sel)

        self._editor._highlight_current_line()

        if self._search_results:
            self._jump_to_result(0)
        else:
            self._match_lbl.setText("not found")

    def _jump_to_result(self, idx: int) -> None:
        if not self._search_results:
            return
        self._search_idx = idx % len(self._search_results)
        pos = self._search_results[self._search_idx]
        text = self._search_edit.text()
        cur = QTextCursor(self._editor.document())
        cur.setPosition(pos)
        cur.setPosition(pos + len(text), QTextCursor.MoveMode.KeepAnchor)
        self._editor.setTextCursor(cur)
        self._editor.ensureCursorVisible()
        self._match_lbl.setText(f"{self._search_idx + 1}/{len(self._search_results)}")

    @pyqtSlot()
    def _find_next(self) -> None:
        if not self._search_results:
            self._run_search(self._search_edit.text())
        else:
            self._jump_to_result(self._search_idx + 1)

    @pyqtSlot()
    def _find_prev(self) -> None:
        if self._search_results:
            self._jump_to_result(self._search_idx - 1)
