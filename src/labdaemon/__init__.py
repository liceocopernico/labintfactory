"""LabDaemon: desktop app and Python library for school lab instruments."""

from loguru import logger

__version__ = "0.1.0.dev0"

# A library stays quiet until the application (or a notebook) enables its logs.
logger.disable("labdaemon")


def __getattr__(name: str):
    # Lazy, so `import labdaemon` stays light and never pulls in Qt.
    if name == "Lab":
        from labdaemon.core.lab import Lab

        return Lab
    raise AttributeError(name)
