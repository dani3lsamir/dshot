"""Toolbar icons: the same 16x16 stroke paths as the Windows build, rendered with QtSvg."""

from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer

ASSETS = Path(__file__).resolve().parent / "assets"

RECTANGLE = "M2.5,3.5 H13.5 V12.5 H2.5 Z"
ARROW = "M3,13 L13,3 M7.5,3 H13 V8.5"
PEN = "M2.5,13.5 L3.5,10 L10.5,3 A1.4,1.4 0 0 1 13,5.5 L6,12.5 Z M9,4.5 L11.5,7"
TEXT = "M3,3 H13 M8,3 V13.5 M6,13.5 H10"
UNDO = "M5.5,3.5 L2.5,6.5 L5.5,9.5 M2.5,6.5 H9.5 A3.5,3.5 0 0 1 9.5,13.5 H6.5"
OCR = "M2,5.5 V2 H5.5 M10.5,2 H14 V5.5 M14,10.5 V14 H10.5 M5.5,14 H2 V10.5 M5.5,5.5 H10.5 M8,5.5 V10.5"
COPY = "M6,6 H13.5 V13.5 H6 Z M3.5,10.5 H2.5 V2.5 H10.5 V3.5"
SAVE = "M2.5,2.5 H11 L13.5,5 V13.5 H2.5 Z M5,2.5 V6 H10 V2.5 M5,13.5 V9.5 H11 V13.5"
CLOSE = "M4,4 L12,12 M12,4 L4,12"

# Rendered at 2x so icons stay sharp on HiDPI screens; Qt scales them down to 16 px elsewhere.
_SCALE = 2


def stroke_icon(path_data: str, color: str = "#ffffff") -> QIcon:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">'
        f'<path d="{path_data}" fill="none" stroke="{color}" stroke-width="1.5" '
        'stroke-linecap="round" stroke-linejoin="round"/></svg>'
    )
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    pixmap = QPixmap(16 * _SCALE, 16 * _SCALE)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(_SCALE)
    return QIcon(pixmap)


def color_icon(color: QColor) -> QIcon:
    """Filled circle showing the current annotation color."""
    pixmap = QPixmap(16 * _SCALE, 16 * _SCALE)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(_SCALE, _SCALE)
    painter.setPen(QPen(QColor("white"), 1.4))
    painter.setBrush(color)
    painter.drawEllipse(QRectF(2, 2, 12, 12))
    painter.end()
    pixmap.setDevicePixelRatio(_SCALE)
    return QIcon(pixmap)


def app_icon(light: bool = False) -> QIcon:
    """The dshot logo; the light variant stays visible on dark panels."""
    return QIcon(str(ASSETS / ("dshot-light.png" if light else "dshot.png")))
