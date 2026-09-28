"""`labdaemon` / `python -m labdaemon`: start the desktop app."""

import sys


def main() -> int:
    from labdaemon.gui.app import main as gui_main

    return gui_main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
