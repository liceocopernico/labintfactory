# LabDaemon

A desktop application (Windows and Linux) for school lab instruments: microcontroller boards and lab sensors as plugins, experiments on top of them, and the data they produce. It replaces the Jupyter/ipywidgets `labintfactory`, whose code is kept in [`legacy/`](legacy/) for reference.

- Design: [`docs/design`](docs/design/) (architecture, mockups, roadmap)
- Board protocol: [`firmware/PROTOCOL.md`](firmware/PROTOCOL.md) (the LabInt wire protocol, version 1)

**Status: milestone M0** (skeleton and protocol). You can connect a simulated TSL2591 photometer over the simulated wire protocol and watch its live reading. Experiments, real serial boards and sessions arrive in M1.

## Running it

It needs [uv](https://docs.astral.sh/uv/). uv installs Python 3.14 and the dependencies itself.

```bash
uv sync
uv run labdaemon --simulate tsl2591_photometer
```

Useful options: `--lang it` (interface language for this run), `--plugin-dir DIR` (extra folder plugins), `--verbose`. Settings live in the user config folder, and logs in the user log folder (both listed under Settings).

From Python or Jupyter, without the GUI:

```python
from labdaemon import Lab

with Lab() as lab:
    photo = lab.simulate("tsl2591_photometer")["photometer"]
    photo.set_parameter("led_color", "red")
    print(photo.read_light(samples=3))
```

## Developing

```bash
uv run pytest                          # tests (GUI tests run offscreen)
uv run ruff check src tests tools      # lint
uv run python tools/i18n.py extract    # after changing user-visible strings
uv run python tools/i18n.py compile    # after translating (.po with a PO editor, .ts with pyside6-linguist)
uv run python tools/i18n.py check      # every string translated (CI runs this)
```

| Path | Contents |
|---|---|
| `src/labdaemon/core/` | Qt-free core: capabilities, parameters, devices, board worker, device manager, plugin registry, settings and policy, i18n, the `Lab` facade |
| `src/labdaemon/transports/` | LabInt wire protocol client; simulated transport and board simulator |
| `src/labdaemon/devices/` | Built-in device plugins (M0: `tsl2591` photometer, with its simulated twin) |
| `src/labdaemon/gui/` | PySide6 application; the only package that imports Qt |
| `src/labdaemon/locale/`, `src/labdaemon/gui/i18n/` | Translations (English source, Italian) |
| `tests/` | pytest suite, including the rule that the core never imports Qt |
| `firmware/` | Protocol spec; the LabInt C++ library and reference sketches arrive in M1 |

Built-in plugins are declared as entry points in `pyproject.toml`. Folder plugins (a folder with a `plugin.toml`) are found on the command line (`--plugin-dir`), in `LABDAEMON_PLUGIN_PATH`, in the user plugin folder, and in the machine-wide plugin folder.

## Licence

GPL-3.0-or-later. See [LICENSE](LICENSE).
