"""`labdaemon` / `python -m labdaemon`: the desktop app, or a command-line tool (`labdaemon ports`, …)."""

import sys


def main() -> int:
    argv = sys.argv[1:]
    from labdaemon.cli import COMMANDS

    if argv and argv[0] in COMMANDS:
        from labdaemon.cli import main as cli_main

        return cli_main(argv)
    from labdaemon.gui.app import main as gui_main

    return gui_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
