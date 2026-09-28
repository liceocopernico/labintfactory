# LabDaemon design

The design proposal for LabDaemon, the standalone desktop app that replaces the Jupyter/ipywidgets interface of `labintfactory`. It covers the architecture, the LabInt wire protocol, the plugins, the GUI with its mockups, and the roadmap.

Current version: **draft 0.8**. Published page: https://claude.ai/artifact/WHEASfHFZgTas2KxyAo5RE (private; share it from the page's Share menu).

## Files

| File | What it is |
|---|---|
| `template.html` | The source of the page: all text, styles and mockups. Edit this file. |
| `build.py` | Generates the mockups' example charts and table rows, and writes the page. |
| `labdaemon-design.html` | The built page. Open it in a browser; don't edit it by hand. |
| `print.css` | Print styles used for the PDF: A4 pages, page numbers, mockups scaled to the page width. |

## Rebuilding

```bash
python build.py
```

This fills the `%%NAME%%` placeholders in `template.html` and writes `labdaemon-design.html`. It needs only the standard library. The example data uses a fixed random seed, so a rebuild without changes produces an identical file.

For a PDF as well:

```bash
python build.py --pdf
```

This needs Google Chrome or Chromium, plus internet access for the web fonts and the mermaid library that draws the diagrams. By default it writes `labdaemon-design.pdf` here; pass a path to write elsewhere (`--pdf out.pdf`).

Notes:

- The diagrams (`<pre class="mermaid">` blocks) are drawn by the claude.ai page viewer, and by `--pdf`. Opened directly in a browser, `labdaemon-design.html` shows them as plain text.
- Some mockup captions quote values computed by `build.py`, such as the calibration fit and the field at 80 mm. `build.py` prints them; if you change the example data, update the text to match.

## Changing the design

- Record every change in the "What changed in draft …" note at the top of `template.html`, and bump the version in the eyebrow and in the footer.
- Once the design is approved, call it 1.0. After that, record significant decisions as short decision records in `docs/decisions/` (context, decision, consequences) and link them from the design.
- Changes to the core contracts (`Device`, capabilities, `Experiment`, the plugin manifest, the wire protocol) must follow the versioning rules in the design (`API_VERSION`, `proto=`).
- To update the published page, publish `labdaemon-design.html` again to the same URL.
