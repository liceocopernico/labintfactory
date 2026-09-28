# LabDaemon

A desktop application (Windows and Linux) for school lab instruments: microcontroller boards and lab sensors as plugins, experiments on top of them, and the data they produce. It replaces the Jupyter/ipywidgets `labintfactory`, whose code is kept in [`legacy/`](legacy/) for reference.

- Design: [`docs/design`](docs/design/) (architecture, mockups, roadmap)
- Board protocol: [`firmware/PROTOCOL.md`](firmware/PROTOCOL.md) (the LabInt wire protocol, version 1)

**Status: M1 nearly complete.** The real photometer (UNO R4 Minima with the LabInt firmware in [`firmware/`](firmware/)) connects over USB. The **absorbance and concentration** experiment runs in guided and expert mode: blank, standards, a calibration line with uncertainties, and unknown samples. Calibrations can be saved and reused, and sessions are saved as `.labint` files. A simulated photometer works without hardware. Still to do for M1: a complete lab with real solutions on Windows and on Linux.

## Running it

It needs [uv](https://docs.astral.sh/uv/). uv installs Python 3.14 and the dependencies itself.

```bash
uv sync
uv run labdaemon --simulate tsl2591_photometer      # no hardware needed
uv run labdaemon --connect /dev/ttyACM0             # a real board (COM3 … on Windows), or use Add device…
```

Useful options: `--lang it` (interface language for this run), `--plugin-dir DIR` (extra folder plugins), `--verbose`. Settings live in the user config folder, and logs in the user log folder (both listed under Settings).

From Python or Jupyter, without the GUI:

```python
from labdaemon import Lab

with Lab() as lab:
    photo = lab.simulate("tsl2591_photometer")["photometer"]   # or lab.connect("/dev/ttyACM0")["photometer"]
    photo.set_output("red", 1850)
    print(photo.read_light(samples=3))

    exp = lab.experiment("absorbance", sensor=photo, source=photo)
    exp.run_operation("measure_blank")
    exp.run_operation("measure_standard", 0.02)   # … more standards
    print(exp.fit_text())
    exp.session.save("lab.labint")
```

## Developing

```bash
uv run pytest                          # tests (GUI tests run offscreen)
LABDAEMON_TEST_PORT=/dev/ttyACM0 uv run pytest tests/test_hardware.py   # with a real photometer
uv run ruff check src tests tools      # lint
uv run python tools/i18n.py extract    # after changing user-visible strings
uv run python tools/i18n.py compile    # after translating (.po with a PO editor, .ts with pyside6-linguist)
uv run python tools/i18n.py check      # every string translated (CI runs this)
```

| Path | Contents |
|---|---|
| `src/labdaemon/core/` | Qt-free core: capabilities, parameters, devices, board worker, device manager, plugin registry, experiments and wizard steps, datasets, sessions, calibrations, fits, hardware sheets, settings and policy, i18n, the `Lab` facade |
| `src/labdaemon/transports/` | LabInt wire protocol client; USB serial transport; simulated transport and board simulator |
| `src/labdaemon/devices/` | Built-in device plugins: the `tsl2591` photometer, with its hardware sheet and simulated twin |
| `src/labdaemon/experiments/` | Built-in experiment plugins: `absorbance` |
| `src/labdaemon/gui/` | PySide6 application; the only package that imports Qt |
| `src/labdaemon/locale/`, `src/labdaemon/gui/i18n/` | Translations (English source, Italian) |
| `tests/` | pytest suite, including the rule that the core never imports Qt |
| `firmware/` | Protocol spec, the LabInt C++ library and the photometer firmware ([firmware/README.md](firmware/README.md)) |

Built-in plugins are declared as entry points in `pyproject.toml`. Folder plugins (a folder with a `plugin.toml`) are found on the command line (`--plugin-dir`), in `LABDAEMON_PLUGIN_PATH`, in the user plugin folder, and in the machine-wide plugin folder.

## Licence

GPL-3.0-or-later. See [LICENSE](LICENSE).
