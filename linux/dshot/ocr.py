"""Offline OCR with Tesseract (English and Spanish), run asynchronously so the UI stays responsive."""

import re
import shutil
import subprocess

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QObject, QProcess, Qt, QTimer, Signal
from PySide6.QtGui import QImage

PREFERRED_LANGUAGES = ("eng", "spa")
OCR_TIMEOUT_MS = 30_000

_cached_langs: str | None = None


class OcrError(Exception):
    pass


def installed_languages() -> set[str]:
    if shutil.which("tesseract") is None:
        raise OcrError("Tesseract is not installed. Run the dshot installer again, or install "
                       "'tesseract' with your package manager.")
    out = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True, timeout=15)
    # First line is a header ("List of available languages ...").
    return {line.strip() for line in out.stdout.splitlines()[1:] if line.strip()}


def ocr_languages() -> str:
    # The installed set does not change while dshot runs, so look it up once and reuse it.
    global _cached_langs
    if _cached_langs is not None:
        return _cached_langs
    langs = [lang for lang in PREFERRED_LANGUAGES if lang in installed_languages()]
    if not langs:
        raise OcrError("No English or Spanish OCR data found. Install tesseract-data-eng/-spa "
                       "(Arch, CachyOS) or tesseract-ocr-eng/-spa (Mint, Ubuntu).")
    _cached_langs = "+".join(langs)
    return _cached_langs


def prepare(image: QImage) -> bytes:
    """PNG bytes for Tesseract; small captures are upscaled, which noticeably improves accuracy."""
    if image.height() < 400:
        factor = 2 if image.height() >= 100 else 3
        image = image.scaled(image.width() * factor, image.height() * factor,
                             Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    buffer.close()
    return bytes(data)


def clean(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\f", "").splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


class OcrJob(QObject):
    """Runs `tesseract stdin stdout` in the background and emits the recognized text."""

    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, image: QImage, parent: QObject | None = None):
        super().__init__(parent)
        self._image = image
        self._cancelled = False
        self._process = QProcess(self)
        self._process.started.connect(self._on_started)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)
        self._timeout = QTimer(self)
        self._timeout.setSingleShot(True)
        self._timeout.timeout.connect(self._on_timeout)

    def start(self) -> None:
        try:
            langs = ocr_languages()
        except (OcrError, OSError, subprocess.SubprocessError) as exc:
            self.failed.emit(str(exc))
            return
        self._timeout.start(OCR_TIMEOUT_MS)
        self._process.start("tesseract", ["stdin", "stdout", "-l", langs, "--psm", "3"])

    def cancel(self) -> None:
        """Stop a running recognition (e.g. the user closed the capture); emits nothing."""
        self._cancelled = True
        self._timeout.stop()
        if self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.kill()
            self._process.waitForFinished(500)

    def _on_started(self) -> None:
        # Feed the image only once the process is up, so stdin is never written to a dead pipe.
        if self._cancelled:
            return
        self._process.write(prepare(self._image))
        self._process.closeWriteChannel()

    def _on_timeout(self) -> None:
        if self._cancelled:
            return
        self.cancel()
        self.failed.emit("Tesseract timed out.")

    def _on_finished(self, code: int, _status) -> None:
        self._timeout.stop()
        if self._cancelled:
            return
        if code != 0:
            err = bytes(self._process.readAllStandardError()).decode(errors="replace").strip()
            self.failed.emit(f"Tesseract failed: {err or code}")
            return
        self.finished.emit(clean(bytes(self._process.readAllStandardOutput()).decode(errors="replace")))

    def _on_error(self, error) -> None:
        self._timeout.stop()
        if self._cancelled:
            return
        if error == QProcess.ProcessError.FailedToStart:
            self.failed.emit("Could not start Tesseract.")
        elif error == QProcess.ProcessError.Crashed:
            self.failed.emit("Tesseract crashed.")
