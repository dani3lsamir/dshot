"""Offline OCR with Tesseract (English and Spanish), run asynchronously so the UI stays responsive."""

import re
import shutil
import subprocess

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QObject, QProcess, Qt, Signal
from PySide6.QtGui import QImage

PREFERRED_LANGUAGES = ("eng", "spa")


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
    langs = [lang for lang in PREFERRED_LANGUAGES if lang in installed_languages()]
    if not langs:
        raise OcrError("No English or Spanish OCR data found. Install tesseract-data-eng/-spa "
                       "(Arch, CachyOS) or tesseract-ocr-eng/-spa (Mint, Ubuntu).")
    return "+".join(langs)


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
        self._process = QProcess(self)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)

    def start(self) -> None:
        try:
            langs = ocr_languages()
        except (OcrError, OSError, subprocess.SubprocessError) as exc:
            self.failed.emit(str(exc))
            return
        self._process.start("tesseract", ["stdin", "stdout", "-l", langs, "--psm", "3"])
        self._process.write(prepare(self._image))
        self._process.closeWriteChannel()

    def _on_finished(self, code: int, _status) -> None:
        if code != 0:
            err = bytes(self._process.readAllStandardError()).decode(errors="replace").strip()
            self.failed.emit(f"Tesseract failed: {err or code}")
            return
        self.finished.emit(clean(bytes(self._process.readAllStandardOutput()).decode(errors="replace")))

    def _on_error(self, error) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            self.failed.emit("Could not start Tesseract.")
