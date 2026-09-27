"""
Data models for Drox Screen Studio annotations.
Supports freehand pen, highlighter, lines, arrows, rectangles,
ellipses, numbered step badges, and text annotations.
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QColor, QPen, QBrush, QPainter, QFont, QPolygonF
from PyQt6.QtCore import Qt
import math


@dataclass
class FreehandStroke:
    points: List[QPointF] = field(default_factory=list)
    color: QColor = field(default_factory=lambda: QColor(255, 60, 60))
    width: float = 4.0
    is_highlighter: bool = False

    def draw(self, painter: QPainter):
        if len(self.points) < 2:
            if len(self.points) == 1:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(self.color))
                r = self.width / 2.0
                painter.drawEllipse(self.points[0], r, r)
            return

        pen = QPen(self.color, self.width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        for i in range(len(self.points) - 1):
            painter.drawLine(self.points[i], self.points[i + 1])


@dataclass
class LineShape:
    start: QPointF
    end: QPointF
    color: QColor = field(default_factory=lambda: QColor(255, 60, 60))
    width: float = 4.0

    def draw(self, painter: QPainter):
        pen = QPen(self.color, self.width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawLine(self.start, self.end)


@dataclass
class ArrowShape:
    start: QPointF
    end: QPointF
    color: QColor = field(default_factory=lambda: QColor(255, 60, 60))
    width: float = 4.0

    def draw(self, painter: QPainter):
        pen = QPen(self.color, self.width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawLine(self.start, self.end)

        dx = self.end.x() - self.start.x()
        dy = self.end.y() - self.start.y()
        length = math.hypot(dx, dy)
        if length < 5:
            return

        angle = math.atan2(dy, dx)
        arrow_size = max(14.0, self.width * 3.5)

        p1 = QPointF(
            self.end.x() - arrow_size * math.cos(angle - math.pi / 6),
            self.end.y() - arrow_size * math.sin(angle - math.pi / 6)
        )
        p2 = QPointF(
            self.end.x() - arrow_size * math.cos(angle + math.pi / 6),
            self.end.y() - arrow_size * math.sin(angle + math.pi / 6)
        )

        arrow_head = QPolygonF([self.end, p1, p2])
        painter.setBrush(QBrush(self.color))
        painter.drawPolygon(arrow_head)


@dataclass
class RectShape:
    start: QPointF
    end: QPointF
    color: QColor = field(default_factory=lambda: QColor(255, 60, 60))
    width: float = 4.0
    filled: bool = False

    def draw(self, painter: QPainter):
        rect = QRectF(self.start, self.end).normalized()
        pen = QPen(self.color, self.width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap, Qt.PenJoinStyle.MiterJoin)
        painter.setPen(pen)
        if self.filled:
            fill_col = QColor(self.color)
            fill_col.setAlpha(60)
            painter.setBrush(QBrush(fill_col))
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)


@dataclass
class EllipseShape:
    start: QPointF
    end: QPointF
    color: QColor = field(default_factory=lambda: QColor(255, 60, 60))
    width: float = 4.0
    filled: bool = False

    def draw(self, painter: QPainter):
        rect = QRectF(self.start, self.end).normalized()
        pen = QPen(self.color, self.width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        if self.filled:
            fill_col = QColor(self.color)
            fill_col.setAlpha(60)
            painter.setBrush(QBrush(fill_col))
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(rect)


@dataclass
class StepBadge:
    center: QPointF
    number: int
    color: QColor = field(default_factory=lambda: QColor(255, 75, 75))
    radius: float = 16.0

    def draw(self, painter: QPainter):
        # Outer glow/shadow
        painter.setPen(Qt.PenStyle.NoPen)
        shadow_col = QColor(0, 0, 0, 80)
        painter.setBrush(QBrush(shadow_col))
        painter.drawEllipse(self.center + QPointF(1.5, 2.0), self.radius, self.radius)

        # Main badge circle
        painter.setBrush(QBrush(self.color))
        border_pen = QPen(QColor(255, 255, 255, 230), 2.5)
        painter.setPen(border_pen)
        painter.drawEllipse(self.center, self.radius, self.radius)

        # Number inside badge
        painter.setPen(QColor(255, 255, 255))
        font = QFont("Arial", int(self.radius * 0.9), QFont.Weight.Bold)
        painter.setFont(font)
        rect = QRectF(
            self.center.x() - self.radius,
            self.center.y() - self.radius,
            self.radius * 2,
            self.radius * 2
        )
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(self.number))


@dataclass
class TextAnnotation:
    position: QPointF
    text: str
    color: QColor = field(default_factory=lambda: QColor(255, 255, 255))
    font_size: int = 20

    def draw(self, painter: QPainter):
        if not self.text:
            return

        font = QFont("Segoe UI", self.font_size, QFont.Weight.DemiBold)
        painter.setFont(font)

        # Subtle dark backdrop box so text is readable on any slide or background
        fm = painter.fontMetrics()
        lines = self.text.split("\n")
        w = max(fm.horizontalAdvance(line) for line in lines) + 16
        h = (fm.height() * len(lines)) + 10

        bg_rect = QRectF(self.position.x() - 4, self.position.y() - fm.ascent() - 4, w, h)
        painter.setPen(QPen(QColor(255, 255, 255, 50), 1.0))
        painter.setBrush(QBrush(QColor(15, 20, 30, 200)))
        painter.drawRoundedRect(bg_rect, 6, 6)

        painter.setPen(self.color)
        y = self.position.y()
        for line in lines:
            painter.drawText(int(self.position.x() + 4), int(y), line)
            y += fm.height()
