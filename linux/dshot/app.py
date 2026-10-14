"""Tray app, single instance and command line.

`dshot` starts the tray app, or starts a capture if it is already running (bind it to Print Screen
in your desktop's keyboard settings). `dshot --capture` starts the app if needed and captures.
"""

import argparse
import gc
import os
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QTimer
from PySide6.QtGui import QAction
from PySide6.QtNetwork import QLocalServer
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from dshot import __version__, icons
from dshot.capture import CaptureError, grab_screens
from dshot.ipc import socket_path
from dshot.overlay import CaptureSession

AUTOSTART_FILE = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "autostart" / "dshot.desktop"
# Short pause so the tray menu or the key press is gone before the screen is grabbed.
CAPTURE_DELAY_MS = 180


def launcher_command() -> str:
    """Command that starts dshot, for the autostart entry (set by the installed launcher script)."""
    launcher = os.environ.get("DSHOT_LAUNCHER")
    if launcher:
        return f'"{launcher}"'
    package_dir = Path(__file__).resolve().parent.parent
    return f'env PYTHONPATH="{package_dir}" "{sys.executable}" -m dshot'


def startup_enabled() -> bool:
    return AUTOSTART_FILE.is_file()


def set_startup(enabled: bool) -> None:
    if enabled:
        AUTOSTART_FILE.parent.mkdir(parents=True, exist_ok=True)
        AUTOSTART_FILE.write_text(
            "[Desktop Entry]\nType=Application\nName=dshot\nComment=Screenshot, annotation and OCR\n"
            f"Exec={launcher_command()}\nIcon=dshot\nTerminal=false\nX-GNOME-Autostart-enabled=true\n"
        )
    elif AUTOSTART_FILE.exists():
        AUTOSTART_FILE.unlink()


class DshotApp(QObject):
    def __init__(self, server: QLocalServer):
        super().__init__()
        self._server = server
        self._server.newConnection.connect(self._on_connection)
        self._session: CaptureSession | None = None

        self.tray = QSystemTrayIcon(icons.app_icon(light=True))
        self.tray.setToolTip("dshot - click to capture")
        menu = QMenu()
        capture = QAction("Capture", menu)
        capture.triggered.connect(self.request_capture)
        menu.addAction(capture)
        startup = QAction("Start at login", menu, checkable=True)
        startup.setChecked(startup_enabled())
        startup.toggled.connect(self._toggle_startup)
        menu.addAction(startup)
        menu.addSeparator()
        quit_action = QAction("Exit", menu)
        quit_action.triggered.connect(QApplication.quit)
        menu.addAction(quit_action)
        self._menu = menu
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()
        else:
            print("dshot: no system tray found; run `dshot` again (or bind it to a key) to capture.",
                  file=sys.stderr)

    def _on_tray_activated(self, reason) -> None:
        # Left click captures, as in Lightshot; right click opens the menu.
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.request_capture()

    def _toggle_startup(self, enabled: bool) -> None:
        try:
            set_startup(enabled)
        except OSError as exc:
            QMessageBox.warning(None, "Start at login", str(exc))

    def _on_connection(self) -> None:
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            if socket.bytesAvailable() == 0:
                socket.waitForReadyRead(1000)
            command = bytes(socket.readAll()).decode(errors="replace").strip()
            socket.disconnectFromServer()
            if command == "quit":
                QApplication.quit()
            else:
                self.request_capture()

    def request_capture(self) -> None:
        QTimer.singleShot(CAPTURE_DELAY_MS, self.capture)

    def capture(self) -> None:
        if self._session is not None:
            return
        try:
            shots = grab_screens()
        except CaptureError as exc:
            self.notify("Capture failed", str(exc))
            return
        self._session = CaptureSession(shots)
        self._session.notification.connect(self.notify)
        self._session.finished.connect(self._on_session_finished)
        self._session.show()

    def _on_session_finished(self) -> None:
        self._session = None
        # A capture holds full-screen images; free them now so the idle tray app stays small.
        gc.collect()

    def notify(self, title: str, message: str) -> None:
        if self.tray.isVisible() and QSystemTrayIcon.supportsMessages():
            self.tray.showMessage(title, message, icons.app_icon(), 4000)
        else:
            print(f"dshot: {title}: {message}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dshot", description="Screenshot, annotation and OCR tool.")
    parser.add_argument("--capture", action="store_true", help="start a capture (starting dshot if needed)")
    parser.add_argument("--quit", action="store_true", help="exit the running dshot")
    parser.add_argument("--version", action="version", version=f"dshot {__version__}")
    args = parser.parse_args(argv)

    app = QApplication(sys.argv[:1])
    app.setApplicationName("dshot")
    app.setDesktopFileName("dshot")
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(icons.app_icon())

    # A running dshot was already asked to capture by __main__ (as in the Windows build, opening
    # dshot again captures); getting here means this is the first instance.
    if args.quit:
        return 0
    path = socket_path()
    QLocalServer.removeServer(path)  # Clears a stale socket left by a crash.
    server = QLocalServer()
    if not server.listen(path):
        print(f"dshot: cannot listen on {path}: {server.errorString()}", file=sys.stderr)
        return 1
    dshot = DshotApp(server)
    if args.capture:
        dshot.request_capture()
    return app.exec()
