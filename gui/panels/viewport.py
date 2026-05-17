"""
TopDownViewport - 2D bird's-eye view of the simulation.

Rendering layers (back to front)
---------------------------------
  1. Background
  2. Grid
  3. Road surfaces  (thick gray polylines per lane)
  4. Lane markings  (thin dashed white lines on lane centrelines)
  5. Road signs     (red triangles with name label)
  6. Vehicles       (rotated rectangles with direction arrow + label)
  7. Scale bar

Controls
--------
  Scroll wheel      - zoom in / out
  Left-button drag  - pan
  Double-click      - re-enable auto-follow (centres on Ego)
"""

from __future__ import annotations

import math

from PyQt6.QtCore import QPoint, QPointF, Qt, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QMouseEvent,
    QPainter,
    QPen,
    QPolygonF,
    QWheelEvent,
)
from PyQt6.QtWidgets import QWidget

from ..controller.simulation_worker import ObjectSnapshot

# ── colours ────────────────────────────────────────────────────────────────
_BG = QColor(22, 22, 38)
_GRID = QColor(42, 42, 62)
_AXIS = QColor(70, 70, 100)
_ROAD_FILL = QColor(68, 68, 72)
_ROAD_EDGE = QColor(90, 90, 95)
_LANE_MARK = QColor(200, 200, 160)
_SIGN_BODY = QColor(210, 40, 40)
_SIGN_TEXT = QColor(255, 210, 80)
_LABEL_TEXT = QColor(220, 220, 230)
_SCALE_BAR = QColor(180, 180, 200)

_OBJ_COLORS = [
    QColor(80, 160, 255),  # blue   - Ego
    QColor(255, 110, 60),  # orange
    QColor(80, 220, 100),  # green
    QColor(240, 210, 50),  # yellow
    QColor(200, 90, 255),  # purple
    QColor(60, 220, 220),  # cyan
]


_SELECTED_OUTLINE = QColor(255, 255, 255)
_ROAD_SELECTED = QColor(100, 160, 255)  # blue tint for selected road/lane
_MIN_HIT_M = 3.0  # minimum object hit radius in world metres


def _point_segment_dist(
    px: float, py: float, ax: float, ay: float, bx: float, by: float
) -> float:
    """Shortest distance from point P to segment AB."""
    dx, dy = bx - ax, by - ay
    len_sq = dx * dx + dy * dy
    if len_sq == 0.0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / len_sq))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


class TopDownViewport(QWidget):
    object_clicked = pyqtSignal(int)  # emits object id on left-click
    road_clicked = pyqtSignal(int)  # emits road_id on left-click

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._objects: list[ObjectSnapshot] = []
        self._lane_strips: list = []  # [{points, width, lane_id, road_id}]
        self._signs: list = []  # [{x, y, h, name}]

        self._scale = 4.0  # pixels per metre
        self._pan_x = 0.0  # world-space centre (metres)
        self._pan_y = 0.0
        self._follow = True  # auto-centre on first object
        self._selected_id: int | None = None
        self._selected_road_id: int | None = None

        self._drag_start: QPoint | None = None
        self._drag_pan0 = (0.0, 0.0)

        self.setMinimumSize(400, 300)
        self.setMouseTracking(True)
        self.setToolTip("Scroll: zoom  |  Drag: pan  |  Double-click: re-centre")

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def reset(self) -> None:
        self._objects = []
        self._lane_strips = []
        self._signs = []
        self._follow = True
        self._selected_id = None
        self._selected_road_id = None
        self.update()

    def update_objects(self, snapshots: list[ObjectSnapshot]) -> None:
        if self._follow and snapshots:
            self._pan_x = snapshots[0].x
            self._pan_y = snapshots[0].y
        self._objects = snapshots
        self.update()

    def set_road_network(self, lane_strips: list, signs: list) -> None:
        self._lane_strips = lane_strips
        self._signs = signs
        self.update()

    def select_object(self, obj_id: int) -> None:
        """Highlight the object with *obj_id* in the viewport (no signal emitted)."""
        self._selected_id = obj_id
        self.update()

    def select_object_by_name(self, name: str) -> None:
        """Highlight the first object whose name equals *name* (no signal emitted)."""
        for snap in self._objects:
            if snap.name == name:
                self._selected_id = snap.id
                self.update()
                return

    def select_road(self, road_id: int) -> None:
        """Highlight *road_id* in the viewport (no signal emitted)."""
        self._selected_road_id = road_id
        self.update()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _s2w(self, sx: float, sy: float) -> tuple[float, float]:
        """Screen → world coordinates (inverse of _w2s)."""
        cx, cy = self.width() / 2, self.height() / 2
        return (
            self._pan_x + (sx - cx) / self._scale,
            self._pan_y - (sy - cy) / self._scale,
        )

    def _hit_test(self, sx: float, sy: float) -> int | None:
        """Return the id of the object under screen point (sx, sy), or None."""
        wx, wy = self._s2w(sx, sy)
        for snap in self._objects:
            dx = wx - snap.x
            dy = wy - snap.y
            cos_h = math.cos(snap.h)
            sin_h = math.sin(snap.h)
            local_x = dx * cos_h + dy * sin_h
            local_y = -dx * sin_h + dy * cos_h
            half_l = max(snap.length / 2, _MIN_HIT_M)
            half_w = max(snap.width / 2, _MIN_HIT_M)
            if abs(local_x) <= half_l and abs(local_y) <= half_w:
                return snap.id
        return None

    def _road_hit_test(self, sx: float, sy: float) -> int | None:
        """Return the road_id of the lane strip under screen point, or None."""
        wx, wy = self._s2w(sx, sy)
        for strip in self._lane_strips:
            pts = strip["points"]
            half_w = strip["width"] / 2 + 0.3  # small tolerance
            for i in range(len(pts) - 1):
                ax, ay = pts[i]
                bx, by = pts[i + 1]
                if _point_segment_dist(wx, wy, ax, ay, bx, by) <= half_w:
                    return strip["road_id"]
        return None

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        p.fillRect(self.rect(), _BG)
        self._draw_grid(p)
        self._draw_axes(p)
        self._draw_roads(p)
        self._draw_signs(p)
        self._draw_objects(p)
        self._draw_scale_bar(p)
        p.end()

    # ── helpers ────────────────────────────────────────────────────────

    def _w2s(self, wx: float, wy: float):
        """World → screen coordinates."""
        cx, cy = self.width() / 2, self.height() / 2
        return (
            cx + (wx - self._pan_x) * self._scale,
            cy - (wy - self._pan_y) * self._scale,  # Qt y is inverted
        )

    def _polyline(self, pts) -> QPolygonF:
        return QPolygonF([QPointF(*self._w2s(x, y)) for x, y in pts])

    # ── grid ───────────────────────────────────────────────────────────

    def _draw_grid(self, p: QPainter) -> None:
        step_m = self._nice_grid_step()
        step_px = step_m * self._scale
        if step_px < 10:
            return

        p.setPen(QPen(_GRID, 0.5))
        cx, cy = self.width() / 2, self.height() / 2

        x = (cx - self._pan_x * self._scale) % step_px
        while x < self.width():
            p.drawLine(int(x), 0, int(x), self.height())
            x += step_px

        y = (cy + self._pan_y * self._scale) % step_px
        while y < self.height():
            p.drawLine(0, int(y), self.width(), int(y))
            y += step_px

    def _draw_axes(self, p: QPainter) -> None:
        ox, oy = self._w2s(0, 0)
        p.setPen(QPen(_AXIS, 1.0, Qt.PenStyle.DashLine))
        p.drawLine(int(ox), 0, int(ox), self.height())
        p.drawLine(0, int(oy), self.width(), int(oy))

    # ── roads ──────────────────────────────────────────────────────────

    def _draw_roads(self, p: QPainter) -> None:
        if not self._lane_strips:
            return

        # Pass 1 - road surface (thick solid strokes)
        for strip in self._lane_strips:
            pts = strip["points"]
            if len(pts) < 2:
                continue
            w_px = max(4.0, strip["width"] * self._scale)
            pen = QPen(_ROAD_FILL, w_px)
            pen.setCapStyle(Qt.PenCapStyle.FlatCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.drawPolyline(self._polyline(pts))

        # Pass 2 - lane centreline markings (thin dashed, coloured by lane id)
        dash_w = max(0.8, self._scale * 0.05)
        for strip in self._lane_strips:
            pts = strip["points"]
            if len(pts) < 2:
                continue
            lane_id = strip.get("lane_id")
            if lane_id is None or lane_id == 0:
                color = QColor(255, 255, 255)
            elif lane_id < 0:
                color = QColor(200, 60, 60)
            else:
                color = QColor(60, 180, 80)
            dash_pen = QPen(color, dash_w)
            dash_pen.setStyle(Qt.PenStyle.DashLine)
            p.setPen(dash_pen)
            p.drawPolyline(self._polyline(pts))

        # Pass 3 - selected road highlight (blue, drawn on top)
        if self._selected_road_id is not None:
            for strip in self._lane_strips:
                if strip["road_id"] != self._selected_road_id:
                    continue
                pts = strip["points"]
                if len(pts) < 2:
                    continue
                w_px = max(4.0, strip["width"] * self._scale)
                hi_pen = QPen(_ROAD_SELECTED, w_px)
                hi_pen.setCapStyle(Qt.PenCapStyle.FlatCap)
                hi_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(hi_pen)
                p.drawPolyline(self._polyline(pts))

    # ── signs ──────────────────────────────────────────────────────────

    def _draw_signs(self, p: QPainter) -> None:
        if not self._signs or self._scale < 0.5:
            return

        sz = max(6, int(self._scale * 1.5))
        font = QFont("monospace", max(6, sz // 2))
        p.setFont(font)

        for sg in self._signs:
            sx, sy = self._w2s(sg["x"], sg["y"])
            if not (0 <= sx <= self.width() and 0 <= sy <= self.height()):
                continue  # outside viewport

            # Red warning triangle
            tri = QPolygonF(
                [
                    QPointF(sx, sy - sz),
                    QPointF(sx + sz, sy + sz * 0.6),
                    QPointF(sx - sz, sy + sz * 0.6),
                ]
            )
            p.setPen(QPen(_ROAD_EDGE, 1))
            p.setBrush(QBrush(_SIGN_BODY))
            p.drawPolygon(tri)

            # Name label
            name = sg["name"]
            if name and self._scale > 2.0:
                p.setPen(_SIGN_TEXT)
                p.drawText(int(sx) + sz + 2, int(sy) + 4, name[:12])

    # ── vehicles ───────────────────────────────────────────────────────

    def _draw_objects(self, p: QPainter) -> None:
        font = QFont("monospace", 8)
        p.setFont(font)

        for i, snap in enumerate(self._objects):
            sx, sy = self._w2s(snap.x, snap.y)
            color = _OBJ_COLORS[i % len(_OBJ_COLORS)]
            l_px = max(8.0, snap.length * self._scale)
            w_px = max(4.0, snap.width * self._scale)

            p.save()
            p.translate(sx, sy)
            p.rotate(-math.degrees(snap.h))

            # Body
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(color))
            p.drawRect(int(-l_px / 2), int(-w_px / 2), int(l_px), int(w_px))

            # Front direction arrow
            arrow_pen = QPen(color.lighter(180), max(1.5, l_px * 0.07))
            p.setPen(arrow_pen)
            p.drawLine(0, 0, int(l_px / 2), 0)

            # Selection outline
            if snap.id == self._selected_id:
                sel_pen = QPen(_SELECTED_OUTLINE, max(2.0, l_px * 0.06))
                p.setPen(sel_pen)
                p.setBrush(Qt.BrushStyle.NoBrush)
                margin = max(2.0, l_px * 0.08)
                p.drawRect(
                    int(-l_px / 2 - margin),
                    int(-w_px / 2 - margin),
                    int(l_px + 2 * margin),
                    int(w_px + 2 * margin),
                )

            p.restore()

            # Label (always upright)
            p.setPen(_LABEL_TEXT)
            lbl_x = int(sx) + int(l_px / 2) + 4
            p.drawText(lbl_x, int(sy) - 4, f"{snap.name}  {snap.speed:.1f} m/s")

    # ── scale bar ──────────────────────────────────────────────────────

    def _draw_scale_bar(self, p: QPainter) -> None:
        step_m = self._nice_grid_step()
        bar_px = int(step_m * self._scale)
        if bar_px < 10:
            return

        bx, by = 12, self.height() - 16
        p.setPen(QPen(_SCALE_BAR, 2))
        p.drawLine(bx, by, bx + bar_px, by)
        p.drawLine(bx, by - 4, bx, by + 4)
        p.drawLine(bx + bar_px, by - 4, bx + bar_px, by + 4)
        p.setFont(QFont("monospace", 8))
        p.drawText(bx, by - 6, f"{step_m:.0f} m")

    def _nice_grid_step(self) -> float:
        target_px = 80.0
        raw_m = target_px / max(self._scale, 1e-6)
        for step in [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000]:
            if step >= raw_m:
                return float(step)
        return 1000.0

    # ------------------------------------------------------------------
    # Mouse interaction
    # ------------------------------------------------------------------

    def wheelEvent(self, event: QWheelEvent) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
        self._scale = max(0.05, min(200.0, self._scale * factor))
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            sx, sy = event.pos().x(), event.pos().y()
            hit_id = self._hit_test(sx, sy)
            if hit_id is not None:
                self._selected_id = hit_id
                self.object_clicked.emit(hit_id)
                self.update()
                return
            road_id = self._road_hit_test(sx, sy)
            if road_id is not None:
                self._selected_road_id = road_id
                self.road_clicked.emit(road_id)
                self.update()
                return
            self._follow = False
            self._drag_start = event.pos()
            self._drag_pan0 = (self._pan_x, self._pan_y)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_start is not None:
            d = event.pos() - self._drag_start
            self._pan_x = self._drag_pan0[0] - d.x() / self._scale
            self._pan_y = self._drag_pan0[1] + d.y() / self._scale
            self.update()

    def mouseReleaseEvent(self, _event: QMouseEvent) -> None:
        self._drag_start = None

    def mouseDoubleClickEvent(self, _event: QMouseEvent) -> None:
        self._follow = True
