"""Single-instance messaging over a Unix socket, usable without loading Qt."""

import os
import socket
import tempfile


def socket_path() -> str:
    base = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
    return os.path.join(base, f"dshot-{os.getuid()}.sock")


def send_to_running(command: str, timeout: float = 0.5) -> bool:
    """Sends a command to the running dshot; False if none is running."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(timeout)
            client.connect(socket_path())
            client.sendall(command.encode() + b"\n")
        return True
    except OSError:
        return False
