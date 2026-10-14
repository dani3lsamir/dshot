"""Screen capture: direct grab on X11, xdg-desktop-portal Screenshot on Wayland.

Wayland compositors do not let applications read the screen, so there the image comes from the
portal (the same API GNOME, KDE and others use for screenshot tools). On X11 each screen is
grabbed directly, which is instant and needs no permission.
"""

import os
import time
import urllib.parse
from dataclasses import dataclass

from PySide6.QtCore import QRect
from PySide6.QtGui import QGuiApplication, QImage, QScreen


class CaptureError(Exception):
    pass


@dataclass
class ScreenShot:
    screen: QScreen
    geometry: QRect  # logical geometry of the screen on the virtual desktop
    image: QImage  # the screen's pixels at device resolution


def is_wayland_session() -> bool:
    # Also true when Qt runs through XWayland: X11 grabs there only see X11 windows.
    return bool(os.environ.get("WAYLAND_DISPLAY")) or os.environ.get("XDG_SESSION_TYPE") == "wayland"


def grab_screens() -> list[ScreenShot]:
    screens = QGuiApplication.screens()
    if not screens:
        raise CaptureError("No screen found.")
    if is_wayland_session():
        return split_virtual_desktop(portal_screenshot(), screens)
    shots = []
    for screen in screens:
        image = screen.grabWindow(0).toImage()
        if image.isNull():
            raise CaptureError(f"Could not read screen {screen.name()}.")
        shots.append(ScreenShot(screen, screen.geometry(), image))
    return shots


def split_virtual_desktop(full: QImage, screens: list[QScreen]) -> list[ScreenShot]:
    """Cuts a whole-desktop image into one image per screen.

    Assumes a uniform scale across screens; mixed per-monitor scaling may be slightly off.
    """
    crops = crop_rects(full.width(), full.height(), [screen.geometry() for screen in screens])
    return [ScreenShot(screen, screen.geometry(), full.copy(crop)) for screen, crop in zip(screens, crops)]


def crop_rects(width: int, height: int, geometries: list[QRect]) -> list[QRect]:
    """Pixel rectangle of each screen inside a whole-desktop image of the given size."""
    virtual = QRect()
    for g in geometries:
        virtual = virtual.united(g)
    sx = width / virtual.width()
    sy = height / virtual.height()
    return [QRect(round((g.x() - virtual.x()) * sx), round((g.y() - virtual.y()) * sy),
                  round(g.width() * sx), round(g.height() * sy)) for g in geometries]


def portal_screenshot(timeout: float = 60) -> QImage:
    try:
        from jeepney import DBusAddress, MatchRule, message_bus, new_method_call
        from jeepney.io.blocking import Proxy, open_dbus_connection
    except ImportError as exc:
        raise CaptureError("Wayland capture needs the Python 'jeepney' package.") from exc

    try:
        conn = open_dbus_connection(bus="SESSION")
    except Exception as exc:  # noqa: BLE001 - any D-Bus failure means no portal
        raise CaptureError(f"Cannot reach the desktop session bus: {exc}") from exc

    with conn:
        # The portal answers on a Request object whose path is derived from our name and token.
        token = f"dshot{os.getpid()}_{int(time.time() * 1000)}"
        sender = conn.unique_name.lstrip(":").replace(".", "_")
        request_path = f"/org/freedesktop/portal/desktop/request/{sender}/{token}"
        rule = MatchRule(type="signal", interface="org.freedesktop.portal.Request",
                         member="Response", path=request_path)
        Proxy(message_bus, conn).AddMatch(rule)

        portal = DBusAddress("/org/freedesktop/portal/desktop", bus_name="org.freedesktop.portal.Desktop",
                             interface="org.freedesktop.portal.Screenshot")
        options = {"handle_token": ("s", token), "interactive": ("b", False)}
        call = new_method_call(portal, "Screenshot", "sa{sv}", ("", options))
        with conn.filter(rule) as responses:
            try:
                conn.send_and_get_reply(call, timeout=10)
                signal = conn.recv_until_filtered(responses, timeout=timeout)
            except TimeoutError as exc:
                raise CaptureError("The screenshot portal did not answer.") from exc
            except Exception as exc:  # noqa: BLE001
                raise CaptureError(f"Screenshot portal error: {exc}") from exc

    response, results = signal.body
    if response != 0:
        raise CaptureError("The screenshot was cancelled or not allowed by the desktop.")
    uri = results.get("uri", ("s", ""))[1]
    path = urllib.parse.unquote(urllib.parse.urlparse(uri).path)
    image = QImage(path)
    if image.isNull():
        raise CaptureError("The screenshot portal returned an unreadable image.")
    # The portal writes a file just for this request (some desktops into ~/Pictures); we only
    # needed its pixels, so remove it rather than leave clutter behind.
    try:
        os.remove(path)
    except OSError:
        pass
    return image
