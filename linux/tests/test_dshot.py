"""Headless tests: run with QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests"""

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QEvent, QEventLoop, QPointF, QRect, QRectF, QSize, Qt, QTimer  # noqa: E402
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QMouseEvent, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from dshot.capture import ScreenShot, crop_rects, split_virtual_desktop  # noqa: E402
from dshot.ocr import OcrJob, clean  # noqa: E402
from dshot.overlay import CaptureSession, Mark, Tool, compose  # noqa: E402

app = QApplication.instance() or QApplication([])


def text_image(lines, width=900, height=220) -> QImage:
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    font = QFont("DejaVu Sans")
    font.setPixelSize(30)
    painter.setFont(font)
    painter.setPen(QColor("black"))
    for i, line in enumerate(lines):
        painter.drawText(20, 60 + i * 60, line)
    painter.end()
    return image


def run_ocr(image: QImage) -> str:
    loop = QEventLoop()
    result = {}
    job = OcrJob(image)
    job.finished.connect(lambda text: (result.setdefault("text", text), loop.quit()))
    job.failed.connect(lambda err: (result.setdefault("error", err), loop.quit()))
    QTimer.singleShot(0, job.start)
    QTimer.singleShot(30000, loop.quit)
    loop.exec()
    if "error" in result:
        raise AssertionError(result["error"])
    return result.get("text", "")


class GeometryTests(unittest.TestCase):
    def test_crop_rects_side_by_side_scaled(self):
        # Two 1920x1080 logical screens captured by the portal at 2x.
        rects = crop_rects(7680, 2160, [QRect(0, 0, 1920, 1080), QRect(1920, 0, 1920, 1080)])
        self.assertEqual(rects, [QRect(0, 0, 3840, 2160), QRect(3840, 0, 3840, 2160)])

    def test_crop_rects_negative_origin(self):
        rects = crop_rects(3000, 1080, [QRect(-1080, 0, 1080, 1080), QRect(0, 0, 1920, 1080)])
        self.assertEqual(rects, [QRect(0, 0, 1080, 1080), QRect(1080, 0, 1920, 1080)])

    def test_single_screen_portal_image_is_not_copied(self):
        screen = QGuiApplication.primaryScreen()
        full = QImage(screen.geometry().size() * 2, QImage.Format.Format_RGB32)
        shots = split_virtual_desktop(full, [screen])
        self.assertEqual(shots[0].image.cacheKey(), full.cacheKey())

    def test_portal_image_is_made_opaque_for_fast_painting(self):
        screen = QGuiApplication.primaryScreen()
        full = QImage(screen.geometry().size(), QImage.Format.Format_ARGB32)  # As loaded from a PNG.
        full.fill(QColor("#2d6cdf"))
        shot = split_virtual_desktop(full, [screen])[0]
        self.assertEqual(shot.image.format(), QImage.Format.Format_RGB32)
        self.assertEqual(QColor(shot.image.pixel(5, 5)), QColor("#2d6cdf"))

    def test_compose_crops_at_device_resolution_with_marks(self):
        # Screen shown at 400x200 logical, captured at 2x (800x400 pixels), solid blue.
        shot = QImage(800, 400, QImage.Format.Format_RGB32)
        shot.fill(QColor("blue"))
        selection = QRectF(100, 50, 100, 60)
        mark = Mark(Tool.RECTANGLE, QColor("red"), [QPointF(110, 60), QPointF(190, 100)])
        out = compose(shot, QSize(400, 200), selection, [mark])
        self.assertEqual((out.width(), out.height()), (200, 120))
        # The rectangle's left edge (logical x=110) lands at pixel 20 of the crop.
        self.assertGreater(QColor(out.pixel(20, 60)).red(), 200)
        self.assertEqual(QColor(out.pixel(100, 60)).blue(), 255)  # Inside the rectangle: untouched.
        plain = compose(shot, QSize(400, 200), selection, None)
        self.assertEqual(QColor(plain.pixel(20, 60)).blue(), 255)


class OcrTests(unittest.TestCase):
    def test_english_and_spanish(self):
        text = run_ocr(text_image(["The quick brown fox jumps", "Hola, ¿cómo estás? Año señal"]))
        for word in ("quick", "brown", "fox", "Hola", "cómo", "Año", "señal"):
            self.assertIn(word, text)

    def test_small_capture_is_upscaled(self):
        image = text_image(["Small text 2026"], width=300, height=60).scaled(
            150, 30, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.assertIn("2026", run_ocr(image))

    def test_clean(self):
        self.assertEqual(clean("a  \n\n\n\nb\f"), "a\n\nb")


class OverlayTests(unittest.TestCase):
    def make_session(self):
        screen = QGuiApplication.primaryScreen()
        image = QImage(screen.geometry().size(), QImage.Format.Format_RGB32)
        image.fill(QColor("#2d6cdf"))
        return CaptureSession([ScreenShot(screen, screen.geometry(), image)])

    def test_selection_toolbar_and_undo(self):
        session = self.make_session()
        overlay = session.overlays[0]
        overlay.selection = QRectF(100, 100, 300, 200)
        overlay.set_tool(Tool.RECTANGLE)
        overlay.place_toolbar()
        self.assertTrue(overlay.toolbar.isVisibleTo(overlay))
        self.assertTrue(overlay.toolbar.mode_buttons[Tool.RECTANGLE].isChecked())
        # Toolbar sits just below the selection.
        self.assertEqual(overlay.toolbar.y(), 309)
        overlay.marks.append(Mark(Tool.ARROW, QColor("red"), [QPointF(120, 120), QPointF(300, 250)]))
        overlay.undo()
        self.assertEqual(overlay.marks, [])
        session.close()

    def test_selecting_on_another_monitor_clears_the_first(self):
        screen = QGuiApplication.primaryScreen()
        shots = []
        for color in ("#2d6cdf", "#df2d2d"):  # Two monitors.
            image = QImage(screen.geometry().size(), QImage.Format.Format_RGB32)
            image.fill(QColor(color))
            shots.append(ScreenShot(screen, screen.geometry(), image))
        session = CaptureSession(shots)
        first, second = session.overlays
        first.selection = QRectF(10, 10, 200, 100)
        first.set_tool(Tool.RECTANGLE)
        first.marks.append(Mark(Tool.RECTANGLE, QColor("red"), [QPointF(20, 20), QPointF(60, 60)]))
        press = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(50, 50), QPointF(50, 50), Qt.MouseButton.LeftButton,
                            Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        second.mousePressEvent(press)
        self.assertTrue(first.selection.isEmpty())
        self.assertEqual(first.marks, [])
        self.assertIs(first.tool, Tool.SELECT)
        # The export comes from the monitor that holds the selection.
        second.selection = QRectF(0, 0, 40, 30)
        second.set_tool(Tool.RECTANGLE)
        second.copy_image()
        self.assertEqual(QColor(QGuiApplication.clipboard().image().pixel(5, 5)), QColor("#df2d2d"))
        self.assertEqual(session.overlays, [])  # Closing one overlay ends the capture on every monitor.

    def test_drag_repaints_only_around_the_selection(self):
        session = self.make_session()
        overlay = session.overlays[0]
        overlay.resize(800, 600)
        areas = []
        overlay.update = lambda *args: areas.append(args)

        def mouse(kind, x, y):
            buttons = Qt.MouseButton.LeftButton if kind != QEvent.Type.MouseButtonRelease else Qt.MouseButton.NoButton
            return QMouseEvent(kind, QPointF(x, y), QPointF(x, y), Qt.MouseButton.LeftButton, buttons,
                               Qt.KeyboardModifier.NoModifier)

        overlay.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, 100, 100))
        areas.clear()
        overlay.mouseMoveEvent(mouse(QEvent.Type.MouseMove, 200, 150))
        overlay.mouseMoveEvent(mouse(QEvent.Type.MouseMove, 180, 170))
        self.assertEqual(areas[-1], (QRect(98, 98, 104, 74),))  # Old and new selection, plus the border.
        overlay.mouseReleaseEvent(mouse(QEvent.Type.MouseButtonRelease, 180, 170))
        self.assertEqual(overlay.selection, QRectF(100, 100, 80, 70))
        session.close()

    def test_text_commit_and_copy(self):
        session = self.make_session()
        overlay = session.overlays[0]
        overlay.selection = QRectF(50, 50, 400, 200)
        overlay.set_tool(Tool.TEXT)
        overlay.begin_text(QPointF(60, 60))
        overlay._editing.text = "Hola\nworld  "
        overlay.next_color()
        overlay.copy_image()  # Commits the text, copies, closes.
        self.assertEqual(overlay.marks[0].text, "Hola\nworld")
        self.assertEqual(overlay.marks[0].color, QColor("#1e90ff"))
        copied = QGuiApplication.clipboard().image()
        self.assertEqual((copied.width(), copied.height()), (400, 200))


if __name__ == "__main__":
    unittest.main()
