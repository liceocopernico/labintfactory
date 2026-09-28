"""Starting the desktop app."""

import argparse
import sys
from pathlib import Path

from loguru import logger
from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
from PySide6.QtWidgets import QApplication

from labdaemon import __version__
from labdaemon.core import i18n
from labdaemon.core.manager import DeviceManager
from labdaemon.core.registry import Registry
from labdaemon.core.settings import Settings, plugin_dirs
from labdaemon.gui.bridge import QtBridge
from labdaemon.gui.main_window import MainWindow

QT_I18N_DIR = Path(__file__).resolve().parent / "i18n"


def configure_logging(settings: Settings, verbose: bool) -> None:
    logger.remove()
    logger.add(sys.stderr, level="DEBUG" if verbose else "INFO")
    try:
        settings.paths.log_dir.mkdir(parents=True, exist_ok=True)
        logger.add(settings.paths.log_dir / "labdaemon.log", level="DEBUG", rotation="5 MB", retention=5,
                   enqueue=True)
    except OSError as e:
        logger.warning("no log file: {}", e)
    logger.enable("labdaemon")


def install_translations(app: QApplication, language: str) -> list[QTranslator]:
    QLocale.setDefault(QLocale(language))
    translators = []
    for name, folder in (("labdaemon", QT_I18N_DIR),
                         ("qtbase", Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)))):
        t = QTranslator(app)
        if t.load(f"{name}_{language}", str(folder)):
            app.installTranslator(t)
            translators.append(t)
    return translators


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="labdaemon", description="LabDaemon: school lab instruments.")
    p.add_argument("--simulate", action="append", default=[], metavar="PLUGIN",
                   help="connect the simulated twin of a device plugin at start (e.g. tsl2591_photometer)")
    p.add_argument("--plugin-dir", action="append", default=[], type=Path, metavar="DIR",
                   help="also look for folder plugins here")
    p.add_argument("--lang", choices=sorted(i18n.LANGUAGES), help="interface language for this run")
    p.add_argument("--verbose", action="store_true", help="debug messages on the console")
    p.add_argument("--version", action="version", version=f"LabDaemon {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings()
    configure_logging(settings, args.verbose)
    language = args.lang or settings.get("app.language")
    i18n.set_language(language)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("LabDaemon")
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")
    install_translations(app, i18n.language())

    registry = Registry(plugin_dirs(settings, args.plugin_dir),
                        developer_mode=bool(settings.get("plugins.developer_mode"))).load()
    manager = DeviceManager(registry, settings)
    bridge = QtBridge(manager)
    window = MainWindow(manager, registry, settings, bridge)
    window.show()
    for plugin_id in args.simulate:
        window.devices.add_simulated(plugin_id)
    logger.info("LabDaemon {} started (Python {}, language {})", __version__, sys.version.split()[0],
                i18n.language())
    try:
        return app.exec()
    finally:
        manager.shutdown()
