"""
Fullscreen Transparent Canvas Overlay for Drox Screen Studio.
Supports Transparent Desktop Mode, Whiteboard, Blackboard, Grid Mode,
Spotlight, Laser Pointer, Freehand, Highlighter, Shapes, Text, and Badges.
"""

import sys
import time
import math
import ctypes
from typing import List, Optional, Tuple
from PyQt6.QtWidgets import QWidget, QApplication, QLineEdit
from PyQt6.QtCore import Qt, QPointF, QRectF, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QRadialGradient, 
    QPainterPath, QCursor
)

from models import (
    FreehandStroke, LineShape, ArrowShape, RectShape, 
    EllipseShape, StepBadge, TextAnnotation
)

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020


def set_window_click_through(hwnd: int, enable: bool):
    """Enable or disable mouse click-through on Windows (64-bit safe)."""
    if sys.platform != "win32" or not hwnd:
        return
    try:
        user32 = ctypes.windll.user32
        GetWindowLongPtr = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
        SetWindowLongPtr = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)

        GetWindowLongPtr.restype = ctypes.c_ssize_t
        GetWindowLongPtr.argtypes = [ctypes.c_void_p, ctypes.c_int]
        SetWindowLongPtr.restype = ctypes.c_ssize_t
        SetWindowLongPtr.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]

        style = GetWindowLongPtr(hwnd, GWL_EXSTYLE)
        if enable:
            SetWindowLongPtr(hwnd, GWL_EXSTYLE, style | WS_EX_TRANSPARENT | WS_EX_LAYERED)
        else:
            SetWindowLongPtr(hwnd, GWL_EXSTYLE, style & ~WS_EX_TRANSPARENT)
    except Exception as e:
        print(f"Click-through error: {e}")


class OverlayCanvas(QWidget):
    """
    Ultra-responsive fullscreen drawing canvas supporting transparent overlay,
    whiteboard, blackboard, laser pointer, and spotlight mode.
    """
    mode_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        # We use Frameless + StaysOnTop.
        # NOTE: Do NOT use Qt.WindowType.Tool here so it receives proper mouse & keyboard events on Windows.
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Canvas State
        self.current_tool = "PEN"  # CURSOR, PEN, HIGHLIGHTER, LASER, SPOTLIGHT, ARROW, LINE, RECT, ELLIPSE, BADGE, TEXT, ERASER
        self.board_mode = "TRANSPARENT"  # TRANSPARENT, WHITEBOARD, BLACKBOARD, GRID_WHITE, GRID_DARK
        self.is_click_through = False
        self.toolbar = None

        # Current Drawing Parameters
        self.current_color = QColor(239, 68, 68)  # Vibrant red
        self.current_width = 4.0
        self.eraser_radius = 24.0
        self.badge_counter = 1

        # Spotlight & Laser state
        self.mouse_pos = QPointF(-100, -100)
        self.spotlight_radius = 140.0
        self.laser_trail: List[Tuple[QPointF, float]] = []

        # Drawing elements & Undo/Redo
        self.items: List[object] = []
        self.redo_stack: List[object] = []
        self.active_stroke: Optional[FreehandStroke] = None
        self.start_point: Optional[QPointF] = None
        self.current_point: Optional[QPointF] = None
        self.is_drawing = False

        # Embedded In-Place Text Editor
        self.text_editor: Optional[QLineEdit] = None
        self.text_editor_pos = QPointF(0, 0)

        # 60 FPS Animation Timer for Laser pointer trail fade
        self.anim_timer = QTimer(self)
        self.anim_timer.setInterval(16)
        self.anim_timer.timeout.connect(self._on_animation_frame)
        self.anim_timer.start()

        self._update_geometry()

    def _update_geometry(self):
        """Cover entire primary screen."""
        screen = QApplication.primaryScreen()
        if screen:
            geom = screen.geometry()
            self.setGeometry(geom)

    def set_tool(self, tool: str):
        """Switch active annotation tool."""
        self.current_tool = tool
        self._commit_text_editor()

        # If user switches to CURSOR tool, enable click-through
        if tool == "CURSOR":
            self.set_click_through(True)
        else:
            self.set_click_through(False)

        # Custom cursors
        if tool == "ERASER":
            self.setCursor(Qt.CursorShape.CrossCursor)
        elif tool == "TEXT":
            self.setCursor(Qt.CursorShape.IBeamCursor)
        elif tool in ("PEN", "HIGHLIGHTER", "ARROW", "LINE", "RECT", "ELLIPSE", "BADGE"):
            self.setCursor(Qt.CursorShape.CrossCursor)
        elif tool in ("LASER", "SPOTLIGHT"):
            self.setCursor(Qt.CursorShape.BlankCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

        self.update()

    def set_click_through(self, enable: bool):
        """Pass mouse clicks through to desktop applications."""
        self.is_click_through = enable
        self.update_mask()
        self.update()

    def update_mask(self):
        """Updates click-through mask so toolbar and notification toast remain interactive."""
        if not self.is_click_through:
            self.clearMask()
            return

        from PyQt6.QtGui import QRegion
        reg = QRegion()
        if hasattr(self, 'toolbar') and self.toolbar and self.toolbar.isVisible():
            reg = reg.united(QRegion(self.toolbar.geometry()))
        if hasattr(self, 'toast') and self.toast and self.toast.isVisible():
            reg = reg.united(QRegion(self.toast.geometry()))
        self.setMask(reg)

    def set_board_mode(self, mode: str):
        """Set board background mode."""
        self.board_mode = mode
        if mode != "TRANSPARENT" and self.is_click_through:
            self.set_click_through(False)
            self.current_tool = "PEN"
            self.mode_changed.emit("PEN")
        self.update()

    def set_color(self, color: QColor):
        """Update current active color."""
        self.current_color = QColor(color)
        self.update()

    def set_width(self, width: float):
        """Update stroke width."""
        self.current_width = float(width)
        self.update()

    def reset_badge_counter(self):
        """Reset step badge counter back to 1."""
        self.badge_counter = 1

    def undo(self):
        """Undo last annotation action."""
        if self.items:
            item = self.items.pop()
            self.redo_stack.append(item)
            if isinstance(item, StepBadge) and self.badge_counter > 1:
                self.badge_counter -= 1
            self.update()

    def redo(self):
        """Redo previously undone annotation."""
        if self.redo_stack:
            item = self.redo_stack.pop()
            self.items.append(item)
            if isinstance(item, StepBadge):
                self.badge_counter = max(self.badge_counter, item.number + 1)
            self.update()

    def clear_canvas(self):
        """Clear all drawn annotations."""
        if self.items:
            self.redo_stack.append(list(self.items))
            self.items.clear()
            self.badge_counter = 1
            self.update()

    def _on_animation_frame(self):
        """60 FPS refresh frame for laser trails and smooth effects."""
        now = time.time()
        if self.laser_trail:
            self.laser_trail = [(pt, t) for (pt, t) in self.laser_trail if (now - t) < 0.55]
            self.update()

    # --- Mouse Event Handlers ---

    def mousePressEvent(self, event):
        if self.is_click_through:
            event.ignore()
            return

        # Safeguard: If click is inside toolbar area, let toolbar handle it
        if hasattr(self, 'toolbar') and self.toolbar and self.toolbar.geometry().contains(event.position().toPoint()):
            event.ignore()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            self.is_drawing = True
            self.start_point = pos
            self.current_point = pos

            if self.current_tool == "PEN":
                self.active_stroke = FreehandStroke(
                    points=[pos],
                    color=QColor(self.current_color),
                    width=self.current_width,
                    is_highlighter=False
                )
            elif self.current_tool == "HIGHLIGHTER":
                hl_col = QColor(self.current_color)
                hl_col.setAlpha(90)
                self.active_stroke = FreehandStroke(
                    points=[pos],
                    color=hl_col,
                    width=max(18.0, self.current_width * 3.5),
                    is_highlighter=True
                )
            elif self.current_tool == "BADGE":
                badge = StepBadge(
                    center=pos,
                    number=self.badge_counter,
                    color=QColor(self.current_color),
                    radius=max(14.0, self.current_width * 3.5)
                )
                self.items.append(badge)
                self.redo_stack.clear()
                self.badge_counter += 1
                self.is_drawing = False
                self.update()
            elif self.current_tool == "TEXT":
                self._open_text_editor(pos)
                self.is_drawing = False
            elif self.current_tool == "ERASER":
                self._erase_at(pos)
                self.update()

        elif event.button() == Qt.MouseButton.RightButton:
            # Right click quick toggle: switch back to CURSOR / Pass-through!
            if self.current_tool != "CURSOR":
                self.set_tool("CURSOR")
                self.mode_changed.emit("CURSOR")

    def mouseMoveEvent(self, event):
        pos = event.position()
        self.mouse_pos = pos

        # Update Laser trail
        if self.current_tool == "LASER":
            self.laser_trail.append((pos, time.time()))

        if self.is_drawing and (event.buttons() & Qt.MouseButton.LeftButton):
            self.current_point = pos
            if self.current_tool in ("PEN", "HIGHLIGHTER") and self.active_stroke:
                self.active_stroke.points.append(pos)
                self.update()
            elif self.current_tool in ("ARROW", "LINE", "RECT", "ELLIPSE"):
                self.update()
            elif self.current_tool == "ERASER":
                self._erase_at(pos)
                self.update()
        else:
            if self.current_tool in ("SPOTLIGHT", "LASER"):
                self.update()

    def mouseReleaseEvent(self, event):
        if not self.is_drawing:
            return

        if event.button() == Qt.MouseButton.LeftButton:
            self.is_drawing = False
            end_pos = event.position()

            if self.current_tool in ("PEN", "HIGHLIGHTER") and self.active_stroke:
                if len(self.active_stroke.points) > 0:
                    self.items.append(self.active_stroke)
                    self.redo_stack.clear()
                self.active_stroke = None
            elif self.current_tool == "LINE" and self.start_point:
                if (end_pos - self.start_point).manhattanLength() > 2:
                    self.items.append(LineShape(self.start_point, end_pos, QColor(self.current_color), self.current_width))
                    self.redo_stack.clear()
            elif self.current_tool == "ARROW" and self.start_point:
                if (end_pos - self.start_point).manhattanLength() > 2:
                    self.items.append(ArrowShape(self.start_point, end_pos, QColor(self.current_color), self.current_width))
                    self.redo_stack.clear()
            elif self.current_tool == "RECT" and self.start_point:
                if (end_pos - self.start_point).manhattanLength() > 2:
                    self.items.append(RectShape(self.start_point, end_pos, QColor(self.current_color), self.current_width, filled=False))
                    self.redo_stack.clear()
            elif self.current_tool == "ELLIPSE" and self.start_point:
                if (end_pos - self.start_point).manhattanLength() > 2:
                    self.items.append(EllipseShape(self.start_point, end_pos, QColor(self.current_color), self.current_width, filled=False))
                    self.redo_stack.clear()

            self.start_point = None
            self.current_point = None
            self.update()

    def wheelEvent(self, event):
        """Scroll wheel adjusts spotlight radius or brush thickness."""
        delta = event.angleDelta().y()
        if self.current_tool == "SPOTLIGHT":
            if delta > 0:
                self.spotlight_radius = min(400.0, self.spotlight_radius + 15.0)
            else:
                self.spotlight_radius = max(60.0, self.spotlight_radius - 15.0)
            self.update()
        else:
            if delta > 0:
                self.current_width = min(40.0, self.current_width + 1.0)
            else:
                self.current_width = max(1.0, self.current_width - 1.0)
            self.update()

    def keyPressEvent(self, event):
        """Native Qt keyboard shortcuts handler."""
        # If typing in the text editor, don't intercept keys
        if self.text_editor and self.text_editor.hasFocus():
            super().keyPressEvent(event)
            return

        key = event.key()
        modifiers = event.modifiers()

        # F2 or Ctrl+Space: Toggle Mouse Pass-Through mode
        if key == Qt.Key.Key_F2 or (modifiers == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_Space):
            if hasattr(self, 'toolbar') and self.toolbar:
                if self.current_tool == "CURSOR":
                    self.toolbar.select_tool("PEN")
                else:
                    self.toolbar.select_tool("CURSOR")
            return

        # Escape key: Switch to Mouse mode
        if key == Qt.Key.Key_Escape:
            if hasattr(self, 'toolbar') and self.toolbar:
                self.toolbar.select_tool("CURSOR")
            return

        # Ctrl shortcuts
        if modifiers == Qt.KeyboardModifier.ControlModifier:
            if key == Qt.Key.Key_Z:
                self.undo()
                return
            elif key == Qt.Key.Key_Y:
                self.redo()
                return
            elif key == Qt.Key.Key_S:
                if hasattr(self, 'parent_app') and hasattr(self.parent_app, 'take_screenshot'):
                    self.parent_app.take_screenshot()
                return

        # Single key tool shortcuts
        tool_map = {
            Qt.Key.Key_P: "PEN",
            Qt.Key.Key_H: "HIGHLIGHTER",
            Qt.Key.Key_L: "LASER",
            Qt.Key.Key_S: "SPOTLIGHT",
            Qt.Key.Key_A: "ARROW",
            Qt.Key.Key_I: "LINE",
            Qt.Key.Key_R: "RECT",
            Qt.Key.Key_C: "ELLIPSE",  # C for Circle
            Qt.Key.Key_O: "ELLIPSE",  # O also for Circle
            Qt.Key.Key_B: "BADGE",
            Qt.Key.Key_T: "TEXT",     # T for Text
            Qt.Key.Key_E: "ERASER",
        }
        if key in tool_map and hasattr(self, 'toolbar') and self.toolbar:
            self.toolbar.select_tool(tool_map[key])
            return

        # Clear canvas (Delete key)
        if key == Qt.Key.Key_Delete:
            self.clear_canvas()
            return

        super().keyPressEvent(event)

    # --- In-Place Text Editor ---

    def _open_text_editor(self, pos: QPointF):
        self._commit_text_editor()
        if hasattr(self, 'parent_app') and hasattr(self.parent_app, 'set_typing_mode'):
            self.parent_app.set_typing_mode(True)

        editor = QLineEdit(self)
        editor.setStyleSheet("""
            QLineEdit {
                background: rgba(15, 20, 30, 230);
                color: #FFFFFF;
                border: 2px solid #3B82F6;
                border-radius: 6px;
                padding: 4px 8px;
                font-family: 'Segoe UI';
                font-size: 18px;
                font-weight: 600;
            }
        """)
        editor.setFont(QFont("Segoe UI", 18, QFont.Weight.DemiBold))
        editor.setPlaceholderText("Type note & press Enter (Hotkeys paused)...")
        editor.setGeometry(int(pos.x()), int(pos.y() - 15), 340, 42)
        editor.show()
        editor.setFocus()
        editor.returnPressed.connect(self._commit_text_editor)
        self.text_editor = editor
        self.text_editor_pos = pos

    def _commit_text_editor(self):
        if hasattr(self, 'parent_app') and hasattr(self.parent_app, 'set_typing_mode'):
            self.parent_app.set_typing_mode(False)

        if self.text_editor:
            text = self.text_editor.text().strip()
            if text:
                ann = TextAnnotation(
                    position=self.text_editor_pos + QPointF(0, 20),
                    text=text,
                    color=QColor(self.current_color),
                    font_size=18
                )
                self.items.append(ann)
                self.redo_stack.clear()
            self.text_editor.deleteLater()
            self.text_editor = None
            self.update()

    # --- Eraser Logic ---

    def _erase_at(self, pos: QPointF):
        """Erase any drawn items touching pos."""
        r = self.eraser_radius
        remaining = []
        for item in self.items:
            hit = False
            if isinstance(item, FreehandStroke):
                for pt in item.points:
                    if (pt - pos).manhattanLength() < r:
                        hit = True
                        break
            elif isinstance(item, (LineShape, ArrowShape)):
                mid = (item.start + item.end) / 2.0
                if (item.start - pos).manhattanLength() < r or (item.end - pos).manhattanLength() < r or (mid - pos).manhattanLength() < r:
                    hit = True
            elif isinstance(item, (RectShape, EllipseShape)):
                rect = QRectF(item.start, item.end).normalized()
                if rect.adjusted(-r, -r, r, r).contains(pos):
                    hit = True
            elif isinstance(item, StepBadge):
                if (item.center - pos).manhattanLength() < (item.radius + r):
                    hit = True
            elif isinstance(item, TextAnnotation):
                if (item.position - pos).manhattanLength() < 40:
                    hit = True

            if not hit:
                remaining.append(item)

        if len(remaining) != len(self.items):
            self.items = remaining
            self.update()

    # --- Painting Routine ---

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        w = self.width()
        h = self.height()

        # 1. Background Fill
        if self.board_mode == "WHITEBOARD":
            painter.fillRect(0, 0, w, h, QColor(255, 255, 255))
        elif self.board_mode == "BLACKBOARD":
            painter.fillRect(0, 0, w, h, QColor(24, 30, 38))
        elif self.board_mode == "GRID_WHITE":
            painter.fillRect(0, 0, w, h, QColor(250, 252, 255))
            self._draw_grid(painter, w, h, QColor(210, 220, 235))
        elif self.board_mode == "GRID_DARK":
            painter.fillRect(0, 0, w, h, QColor(22, 27, 34))
            self._draw_grid(painter, w, h, QColor(48, 54, 61))
        else:
            # Transparent desktop overlay mode:
            # CRITICAL: If click-through is OFF, we MUST paint an invisible alpha=1 pixel surface
            # so Windows DWM catches mouse clicks instead of sending them to the background app!
            if not self.is_click_through:
                painter.fillRect(0, 0, w, h, QColor(0, 0, 0, 1))

        # 2. Draw Committed Annotations
        for item in self.items:
            item.draw(painter)

        # 3. Draw Active Freehand Stroke
        if self.active_stroke:
            self.active_stroke.draw(painter)

        # 4. Draw Active Shape Preview
        if self.is_drawing and self.start_point and self.current_point:
            if self.current_tool == "LINE":
                LineShape(self.start_point, self.current_point, self.current_color, self.current_width).draw(painter)
            elif self.current_tool == "ARROW":
                ArrowShape(self.start_point, self.current_point, self.current_color, self.current_width).draw(painter)
            elif self.current_tool == "RECT":
                RectShape(self.start_point, self.current_point, self.current_color, self.current_width, filled=False).draw(painter)
            elif self.current_tool == "ELLIPSE":
                EllipseShape(self.start_point, self.current_point, self.current_color, self.current_width, filled=False).draw(painter)

        # 5. Draw Spotlight Effect
        if self.current_tool == "SPOTLIGHT":
            self._draw_spotlight(painter, w, h)

        # 6. Draw Laser Pointer
        if self.current_tool == "LASER":
            self._draw_laser(painter)

        # 7. Draw Eraser Circle Indicator
        if self.current_tool == "ERASER" and not self.is_click_through:
            pen = QPen(QColor(240, 68, 68, 220), 2.0, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(QBrush(QColor(240, 68, 68, 40)))
            painter.drawEllipse(self.mouse_pos, self.eraser_radius, self.eraser_radius)

    def _draw_grid(self, painter: QPainter, w: int, h: int, grid_color: QColor):
        pen = QPen(grid_color, 1.0)
        painter.setPen(pen)
        step = 32
        for x in range(0, w, step):
            painter.drawLine(x, 0, x, h)
        for y in range(0, h, step):
            painter.drawLine(0, y, w, y)

    def _draw_spotlight(self, painter: QPainter, w: int, h: int):
        """Dark vignette around whole screen with a clear spotlight hole."""
        path = QPainterPath()
        path.addRect(0, 0, w, h)

        spot_circle = QPainterPath()
        spot_circle.addEllipse(self.mouse_pos, self.spotlight_radius, self.spotlight_radius)

        dark_overlay = path.subtracted(spot_circle)
        painter.fillPath(dark_overlay, QBrush(QColor(0, 0, 0, 190)))

        # Soft glowing ring border on spotlight
        ring_pen = QPen(QColor(255, 255, 255, 120), 3.0)
        painter.setPen(ring_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(self.mouse_pos, self.spotlight_radius, self.spotlight_radius)

    def _draw_laser(self, painter: QPainter):
        """Glowing laser dot with smooth fading tail."""
        now = time.time()
        # Draw fading trail
        if len(self.laser_trail) > 1:
            for i in range(len(self.laser_trail) - 1):
                pt1, t1 = self.laser_trail[i]
                pt2, t2 = self.laser_trail[i + 1]
                age = now - t1
                alpha = int(max(0, 255 * (1.0 - (age / 0.55))))
                if alpha > 0:
                    tail_pen = QPen(QColor(255, 30, 30, alpha), 6.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
                    painter.setPen(tail_pen)
                    painter.drawLine(pt1, pt2)

        # Draw glowing laser core
        painter.setPen(Qt.PenStyle.NoPen)
        outer_grad = QRadialGradient(self.mouse_pos, 22)
        outer_grad.setColorAt(0.0, QColor(255, 40, 40, 220))
        outer_grad.setColorAt(0.5, QColor(255, 20, 20, 100))
        outer_grad.setColorAt(1.0, QColor(255, 0, 0, 0))
        painter.setBrush(QBrush(outer_grad))
        painter.drawEllipse(self.mouse_pos, 22, 22)

        # White-hot inner core
        painter.setBrush(QBrush(QColor(255, 255, 255, 250)))
        painter.drawEllipse(self.mouse_pos, 4.5, 4.5)
