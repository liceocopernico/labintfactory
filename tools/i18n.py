"""Translation pipeline for LabDaemon (English source, Italian translation).

    uv run python tools/i18n.py extract   # refresh the catalogs from the source code
    uv run python tools/i18n.py compile   # build .mo (gettext) and .qm (Qt) files
    uv run python tools/i18n.py check     # fail if any string lacks a translation (used by CI)

Core and plugin strings use gettext (_ and N_) → src/labdaemon/locale/<lang>/LC_MESSAGES/labdaemon.po
GUI strings use Qt's tr()                     → src/labdaemon/gui/i18n/labdaemon_<lang>.ts
Translate the .po files with any PO editor (Poedit, Lokalize) and the .ts files with pyside6-linguist.
"""

import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "src" / "labdaemon"
LOCALE = PKG / "locale"
QT_DIR = PKG / "gui" / "i18n"
POT = LOCALE / "labdaemon.pot"
LANGUAGES = ["it"]


def tool(name: str) -> str:
    exe = Path(sys.executable).parent / name
    found = str(exe) if exe.exists() else shutil.which(name)
    if not found:
        sys.exit(f"{name} not found; run `uv sync` first")
    return found


def run(*cmd: str) -> None:
    subprocess.run(cmd, check=True, cwd=ROOT)


def extract() -> None:
    run(tool("pybabel"), "extract", "-F", "babel.cfg", "-k", "N_", "--no-location", "--sort-output",
        "--project", "LabDaemon", "--copyright-holder", "Matteo Mosangini", "-o", str(POT), "src/labdaemon")
    for lang in LANGUAGES:
        po = LOCALE / lang / "LC_MESSAGES" / "labdaemon.po"
        action = "update" if po.exists() else "init"
        run(tool("pybabel"), action, "-D", "labdaemon", "-i", str(POT), "-d", str(LOCALE), "-l", lang,
            *(["--no-fuzzy-matching"] if action == "update" else []))
    gui_sources = sorted(str(p.relative_to(ROOT)) for p in (PKG / "gui").rglob("*.py"))
    for lang in LANGUAGES:
        run(tool("pyside6-lupdate"), *gui_sources, "-no-obsolete", "-ts",
            str((QT_DIR / f"labdaemon_{lang}.ts").relative_to(ROOT)))


def compile_() -> None:
    run(tool("pybabel"), "compile", "-D", "labdaemon", "-d", str(LOCALE), "--statistics")
    for ts in sorted(QT_DIR.glob("*.ts")):
        run(tool("pyside6-lrelease"), str(ts), "-qm", str(ts.with_suffix(".qm")))


def check() -> None:
    from babel.messages.pofile import read_po

    problems = []
    for lang in LANGUAGES:
        po = LOCALE / lang / "LC_MESSAGES" / "labdaemon.po"
        with po.open("rb") as f:
            catalog = read_po(f)
        for msg in catalog:
            if msg.id and (not msg.string or msg.fuzzy):
                problems.append(f"{po.name} [{lang}]: {msg.id!r}")
        ts = QT_DIR / f"labdaemon_{lang}.ts"
        for message in ET.parse(ts).getroot().iter("message"):
            tr = message.find("translation")
            if tr is None or tr.get("type") == "unfinished" or not (tr.text or "").strip():
                problems.append(f"{ts.name}: {message.findtext('source')!r}")
    if problems:
        print("Untranslated strings:\n  " + "\n  ".join(problems))
        sys.exit(1)
    print("All strings are translated.")


if __name__ == "__main__":
    commands = {"extract": extract, "compile": compile_, "check": check}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        sys.exit(__doc__)
    commands[sys.argv[1]]()
