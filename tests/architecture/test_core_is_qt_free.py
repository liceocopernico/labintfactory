"""Design rule R1: the core, transports and device plugins never import Qt."""

import subprocess
import sys

SCRIPT = r"""
import importlib, importlib.abc, pkgutil, sys

class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in ("PySide6", "shiboken6", "pyqtgraph"):
            raise ImportError(f"Qt import forbidden outside the GUI: {name}")

sys.meta_path.insert(0, Block())
import labdaemon
for mod in pkgutil.walk_packages(labdaemon.__path__, "labdaemon."):
    if mod.name.startswith("labdaemon.gui") or mod.name == "labdaemon.__main__":
        continue
    importlib.import_module(mod.name)
labdaemon.Lab
print("ok")
"""


def test_core_imports_without_qt():
    result = subprocess.run([sys.executable, "-c", SCRIPT], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"
