"""The capture UI: a frozen screenshot per screen, Lightshot-style selection, toolbar and annotations.

Annotations are stored in logical (widget) coordinates and drawn by one function, both on screen
and into the exported image, so what you see is exactly what gets copied or saved.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path

from PySide6.QtCore import QLineF, QObject, QPointF, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (QColor, QCursor, QFont, QFontMetricsF, QGuiApplication, QImage, QPainter,
                           QPainterPath, QPen, QPolygonF)
from PySide6.QtWidgets import (QButtonGroup, QFileDialog, QFrame, QHBoxLayout, QMessageBox, QToolButton,
                               QWidget)

from dshot import icons
from dshot.capture import ScreenShot
from dshot.ocr import OcrJob


class Tool(Enum):
    SELECT = auto()
    RECTANGLE = auto()
    ARROW = auto()
    PEN = auto()
    TEXT = auto()


PALETTE = [QColor("#ff0000"), QColor("#1e90ff"), QColor("#32cd32"), QColor("#ffff00"), QColor("#ffffff")]
STROKE_WIDTH = 2.5
TEXT_PIXEL_SIZE = 20
DIM = QColor(0, 0, 0, 110)
MIN_SELECTION = 6


@dataclass
class Mark:
    tool: Tool
    color: QColor
    points: list[QPointF] = field(default_factory=list)
    text: str = ""


def text_font() -> QFont:
    font = QFont()
    font.setPixelSize(TEXT_PIXEL_SIZE)
    font.setBold(True)
    return font


def normalized(a: QPointF, b: QPointF) -> QRectF:
    return QRectF(a, b).normalized()


def draw_mark(painter: QPainter, mark: Mark) -> None:
    pen = QPen(mark.color, STROKE_WIDTH, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    if mark.tool is Tool.RECTANGLE and len(mark.points) >= 2:
        painter.drawRect(normalized(mark.points[0], mark.points[-1]))
    elif mark.tool is Tool.ARROW and len(mark.points) >= 2:
        start, end = mark.points[0], mark.points[-1]
        line = QLineF(start, end)
        if line.length() < 4:
            return
        # Stop the shaft inside the head so the tip stays sharp.
        angle = math.atan2(end.y() - start.y(), end.x() - start.x())
        head = 14.0
        wing = 0.45
        tip_back = QPointF(end.x() - head * 0.8 * math.cos(angle), end.y() - head * 0.8 * math.sin(angle))
        painter.drawLine(QLineF(start, tip_back))
        left = QPointF(end.x() - head * math.cos(angle - wing), end.y() - head * math.sin(angle - wing))
        right = QPointF(end.x() - head * math.cos(angle + wing), end.y() - head * math.sin(angle + wing))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(mark.color)
        painter.drawPolygon(QPolygonF([end, left, right]))
    elif mark.tool is Tool.PEN and mark.points:
        if len(mark.points) == 1:
            painter.drawPoint(mark.points[0])
        else:
            path = QPainterPath(mark.points[0])
            for p in mark.points[1:]:
                path.lineTo(p)
            painter.drawPath(path)
    elif mark.tool is Tool.TEXT and mark.text:
        painter.setFont(text_font())
        metrics = QFontMetricsF(painter.font())
        origin = mark.points[0]
        for i, line in enumerate(mark.text.split("\n")):
            painter.drawText(QPointF(origin.x(), origin.y() + metrics.ascent() + i * metrics.lineSpacing()), line)


def text_bounds(mark: Mark) -> QRectF:
    metrics = QFontMetricsF(text_font())
    lines = mark.text.split("\n")
    width = max((metrics.horizontalAdvance(line) for line in lines), default=0)
    return QRectF(mark.points[0], QPointF(mark.points[0].x() + max(width, 8),
                                          mark.points[0].y() + metrics.lineSpacing() * len(lines)))


def compose(shot_image: QImage, view_size, selection: QRectF, marks: list[Mark] | None) -> QImage:
    """Crops the selection out of the screenshot at full resolution and paints the annotations on it."""
    sx = shot_image.width() / view_size.width()
    sy = shot_image.height() / view_size.height()
    crop = QRect(round(selection.x() * sx), round(selection.y() * sy),
                 max(1, round(selection.width() * sx)), max(1, round(selection.height() * sy)))
    crop = crop.intersected(shot_image.rect())
    out = shot_image.copy(crop).convertToFormat(QImage.Format.Format_ARGB32)
    if marks:
        painter = QPainter(out)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.translate(-crop.x(), -crop.y())
        painter.scale(sx, sy)
        painter.setClipRect(selection)
        for mark in marks:
            draw_mark(painter, mark)
        painter.end()
    return out


class Toolbar(QFrame):
    STYLE = """
        QFrame#toolbar { background: #1f222a; border: 1px solid #5a6069; border-radius: 7px; }
        QToolButton { background: transparent; border: none; border-radius: 5px; padding: 0; }
        QToolButton:hover { background: #3a3f49; }
        QToolButton:checked { background: #4a505a; }
        QFrame#separator { background: #4a505a; }
    """

    def __init__(self, overlay: "OverlayWindow"):
        super().__init__(overlay)
        self.setObjectName("toolbar")
        self.setStyleSheet(self.STYLE)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)
        self._layout = layout
        self.modes = QButtonGroup(self)
        self.modes.setExclusive(True)
        self.mode_buttons: dict[Tool, QToolButton] = {}
        for tool, icon, tip in ((Tool.RECTANGLE, icons.RECTANGLE, "Rectangle"), (Tool.ARROW, icons.ARROW, "Arrow"),
                                (Tool.PEN, icons.PEN, "Pen"), (Tool.TEXT, icons.TEXT, "Text")):
            button = self._button(icons.stroke_icon(icon), tip, lambda _=False, t=tool: overlay.set_tool(t))
            button.setCheckable(True)
            self.modes.addButton(button)
            self.mode_buttons[tool] = button
        self.color_button = self._button(icons.color_icon(overlay.color), "Color", overlay.next_color)
        self._separator()
        self._button(icons.stroke_icon(icons.UNDO), "Undo (Ctrl+Z)", overlay.undo)
        self._separator()
        self._button(icons.stroke_icon(icons.OCR), "Copy text - OCR (English/Spanish)", overlay.extract_text)
        self._button(icons.stroke_icon(icons.COPY), "Copy image (Ctrl+C)", overlay.copy_image)
        self._button(icons.stroke_icon(icons.SAVE), "Save as PNG (Ctrl+S)", overlay.save_image)
        self._separator()
        self._button(icons.stroke_icon(icons.CLOSE), "Close (Esc)", overlay.session.close)
        self.adjustSize()
        self.hide()

    def _button(self, icon, tip, slot) -> QToolButton:
        button = QToolButton(self)
        button.setIcon(icon)
        button.setToolTip(tip)
        button.setFixedSize(30, 30)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.clicked.connect(slot)
        self._layout.addWidget(button)
        return button

    def _separator(self) -> None:
        line = QFrame(self)
        line.setObjectName("separator")
        line.setFixedSize(1, 18)
        self._layout.addSpacing(3)
        self._layout.addWidget(line)
        self._layout.addSpacing(3)


class OverlayWindow(QWidget):
    def __init__(self, session: "CaptureSession", shot: ScreenShot):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.Tool)
        self.session = session
        self.shot = shot
        self.setWindowTitle("dshot")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setScreen(shot.screen)
        self.setGeometry(shot.geometry)

        self.tool = Tool.SELECT
        self.color_index = 0
        self.selection = QRectF()
        self.marks: list[Mark] = []
        self._drag_start: QPointF | None = None
        self._active: Mark | None = None
        self._editing: Mark | None = None
        self._busy = False
        self.toolbar = Toolbar(self)

    # ----- state -----
    @property
    def color(self) -> QColor:
        return PALETTE[self.color_index]

    @property
    def has_selection(self) -> bool:
        return self.tool is not Tool.SELECT

    def set_tool(self, tool: Tool) -> None:
        self.commit_text()
        self.tool = tool
        if tool in self.toolbar.mode_buttons:
            self.toolbar.mode_buttons[tool].setChecked(True)

    def next_color(self) -> None:
        self.color_index = (self.color_index + 1) % len(PALETTE)
        self.toolbar.color_button.setIcon(icons.color_icon(self.color))
        if self._editing:
            self._editing.color = self.color
            self.update()

    def clear_selection(self) -> None:
        self.commit_text()
        self.tool = Tool.SELECT
        self.selection = QRectF()
        self.marks.clear()
        self.toolbar.hide()
        self.update()

    def undo(self) -> None:
        if self._editing:
            return
        if self.marks:
            self.marks.pop()
            self.update()

    # ----- text -----
    def begin_text(self, pos: QPointF) -> None:
        self._editing = Mark(Tool.TEXT, self.color, [pos], "")
        self.update()

    def commit_text(self) -> None:
        if self._editing is None:
            return
        mark, self._editing = self._editing, None
        if mark.text.strip():
            mark.text = mark.text.rstrip()
            self.marks.append(mark)
        self.update()

    # ----- painting -----
    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.drawImage(QRectF(self.rect()), self.shot.image, QRectF(self.shot.image.rect()))
        dim = QPainterPath()
        dim.setFillRule(Qt.FillRule.OddEvenFill)
        dim.addRect(QRectF(self.rect()))
        if not self.selection.isEmpty():
            dim.addRect(self.selection)
        painter.fillPath(dim, DIM)
        if self.selection.isEmpty():
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.save()
        painter.setClipRect(self.selection)
        for mark in self.marks + ([self._active] if self._active else []):
            draw_mark(painter, mark)
        if self._editing:
            draw_mark(painter, self._editing)
        painter.restore()

        # Lightshot-style border: white outer line, dark inner line, readable on any content.
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        outer = self.selection.toAlignedRect()
        painter.setPen(QPen(QColor("white"), 1))
        painter.drawRect(outer.adjusted(0, 0, -1, -1))
        painter.setPen(QPen(QColor(0, 0, 0, 140), 1))
        painter.drawRect(outer.adjusted(1, 1, -2, -2))

        if self._editing:
            # Dashed box and caret around the text being typed.
            bounds = text_bounds(self._editing).adjusted(-3, -2, 3, 2)
            # Two-tone dashes stay visible on light and dark content.
            painter.setPen(QPen(QColor(255, 255, 255, 190), 1))
            painter.drawRect(bounds)
            painter.setPen(QPen(QColor(0, 0, 0, 170), 1, Qt.PenStyle.DashLine))
            painter.drawRect(bounds)
            metrics = QFontMetricsF(text_font())
            lines = self._editing.text.split("\n")
            origin = self._editing.points[0]
            caret_x = origin.x() + metrics.horizontalAdvance(lines[-1]) + 1
            caret_y = origin.y() + (len(lines) - 1) * metrics.lineSpacing()
            painter.setPen(QPen(self._editing.color, 1.5))
            painter.drawLine(QPointF(caret_x, caret_y + 2), QPointF(caret_x, caret_y + metrics.height() - 2))

    # ----- mouse -----
    def mousePressEvent(self, event) -> None:
        if self._busy or event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()
        # Clicking anywhere outside the text being typed finishes it, as in Lightshot.
        self.commit_text()
        if self.tool is Tool.SELECT:
            self.session.start_selection(self)
            self._drag_start = pos
            self.selection = QRectF(pos, pos)
            self.toolbar.hide()
            self.update()
            return
        if not self.selection.contains(pos):
            return
        if self.tool is Tool.TEXT:
            self.begin_text(pos)
            return
        self._drag_start = pos
        self._active = Mark(self.tool, self.color, [pos, pos] if self.tool is not Tool.PEN else [pos])

    def mouseMoveEvent(self, event) -> None:
        if self._drag_start is None:
            return
        pos = event.position()
        if self.tool is Tool.SELECT:
            self.selection = normalized(self._drag_start, pos).intersected(QRectF(self.rect()))
        elif self._active:
            pos = QPointF(min(max(pos.x(), self.selection.left()), self.selection.right()),
                          min(max(pos.y(), self.selection.top()), self.selection.bottom()))
            if self._active.tool is Tool.PEN:
                self._active.points.append(pos)
            else:
                self._active.points[-1] = pos
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        if self._drag_start is None or event.button() != Qt.MouseButton.LeftButton:
            return
        self._drag_start = None
        if self.tool is Tool.SELECT:
            if self.selection.width() < MIN_SELECTION or self.selection.height() < MIN_SELECTION:
                self.selection = QRectF()
                self.update()
                return
            self.set_tool(Tool.RECTANGLE)  # Once a region is chosen, dragging inside it draws.
            self.place_toolbar()
        elif self._active:
            self.marks.append(self._active)
            self._active = None
        self.update()

    def place_toolbar(self) -> None:
        bar = self.toolbar
        bar.adjustSize()
        x = min(max(self.selection.left(), 0), max(0, self.width() - bar.width()))
        y = self.selection.bottom() + 9
        if y + bar.height() > self.height():
            y = self.selection.top() - bar.height() - 9
        if y < 0:  # No room above or below: put it inside the selection.
            y = self.selection.bottom() - bar.height() - 9
        bar.move(round(x), round(max(0, y)))
        bar.show()
        bar.raise_()

    # ----- keyboard -----
    def keyPressEvent(self, event) -> None:
        key, mods = event.key(), event.modifiers()
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        if key == Qt.Key.Key_Escape:
            # First Esc finishes the text being typed; the next one closes the capture.
            if self._editing:
                self.commit_text()
            else:
                self.session.close()
            return
        if self._busy:
            return
        if ctrl and self.has_selection:
            if key == Qt.Key.Key_C:
                self.copy_image()
            elif key == Qt.Key.Key_S:
                self.save_image()
            elif key == Qt.Key.Key_Z:
                self.undo()
            elif key == Qt.Key.Key_V and self._editing:
                self._editing.text += QGuiApplication.clipboard().text()
                self.update()
            return
        if self._editing:
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._editing.text += "\n"
            elif key == Qt.Key.Key_Backspace:
                self._editing.text = self._editing.text[:-1]
            elif event.text() and event.text().isprintable():
                self._editing.text += event.text()
            self.update()

    # ----- actions -----
    def composed(self, annotations: bool = True) -> QImage:
        self.commit_text()
        return compose(self.shot.image, self.size(), self.selection, self.marks if annotations else None)

    def copy_image(self) -> None:
        if not self.has_selection or self._busy:
            return
        QGuiApplication.clipboard().setImage(self.composed())
        self.session.close()

    def save_image(self) -> None:
        if not self.has_selection or self._busy:
            return
        image = self.composed()
        pictures = Path.home() / "Pictures"
        default = (pictures if pictures.is_dir() else Path.home()) / f"dshot_{datetime.now():%Y%m%d_%H%M%S}.png"
        # Hide the fullscreen overlay so the file dialog is never stuck behind it.
        self.session.hide()
        path, _ = QFileDialog.getSaveFileName(None, "Save screenshot", str(default), "PNG image (*.png)")
        if not path:
            self.session.show()
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        if image.save(path, "PNG"):
            self.session.close()
        else:
            self.session.show()
            QMessageBox.warning(self, "dshot", f"Could not save {path}.")

    def extract_text(self) -> None:
        if not self.has_selection or self._busy:
            return
        self._busy = True
        self.setCursor(Qt.CursorShape.WaitCursor)
        job = OcrJob(self.composed(annotations=False), self)
        job.finished.connect(self._ocr_done)
        job.failed.connect(self._ocr_failed)
        job.start()

    def _ocr_done(self, text: str) -> None:
        self._busy = False
        self.setCursor(Qt.CursorShape.CrossCursor)
        if not text:
            QMessageBox.information(self, "dshot", "No text found. Try a larger region or text with better contrast.")
            return
        QGuiApplication.clipboard().setText(text)
        self.session.notify("Text copied", text if len(text) <= 120 else text[:117] + "...")
        self.session.close()

    def _ocr_failed(self, message: str) -> None:
        self._busy = False
        self.setCursor(Qt.CursorShape.CrossCursor)
        QMessageBox.warning(self, "dshot", f"Text recognition failed: {message}")


class CaptureSession(QObject):
    """One capture: an overlay per screen; a selection lives on a single screen at a time."""

    finished = Signal()
    notification = Signal(str, str)

    def __init__(self, shots: list[ScreenShot]):
        super().__init__()
        self.overlays = [OverlayWindow(self, shot) for shot in shots]
        self._closed = False

    def show(self) -> None:
        for overlay in self.overlays:
            overlay.showFullScreen()
        # Focus the screen under the mouse so keyboard shortcuts work straight away.
        target = next((o for o in self.overlays if o.geometry().contains(QCursor.pos())), self.overlays[0])
        target.activateWindow()
        target.raise_()
        target.setFocus()

    def hide(self) -> None:
        for overlay in self.overlays:
            overlay.hide()

    def start_selection(self, owner: OverlayWindow) -> None:
        for overlay in self.overlays:
            if overlay is not owner and not overlay.selection.isEmpty():
                overlay.clear_selection()
        owner.activateWindow()
        owner.setFocus()

    def notify(self, title: str, message: str) -> None:
        self.notification.emit(title, message)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for overlay in self.overlays:
            overlay.close()
        self.overlays.clear()
        # Let Qt finish delivering events to the closed windows before the session goes away.
        QTimer.singleShot(0, self.finished.emit)
