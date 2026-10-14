import sys

from dshot.ipc import send_to_running

# Fast path: a second launch (Print Screen, tray-less desktops) only pokes the running instance,
# without loading Qt, so the capture starts quickly.
_args = set(sys.argv[1:])
if not _args & {"-h", "--help", "--version"}:
    if send_to_running("quit" if "--quit" in _args else "capture"):
        sys.exit(0)
    if "--quit" in _args:
        sys.exit(0)

from dshot.app import main  # noqa: E402

sys.exit(main())
