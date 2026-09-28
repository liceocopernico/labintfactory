"""Build the LabDaemon design page from template.html.

The template holds the whole page except the example charts and tables of the
mockups, which are generated here from plausible lab data and substituted for
the %%NAME%% placeholders.

    python build.py            # writes labdaemon-design.html
    python build.py --pdf      # also writes labdaemon-design.pdf (needs Google Chrome or Chromium)
"""

import argparse
import math
import random
import re
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "template.html"
PAGE = HERE / "labdaemon-design.html"
PRINT_CSS = HERE / "print.css"
MERMAID_JS = "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"

random.seed(11)  # same "noise" on every build, so rebuilds don't produce spurious diffs


def f1(v):
    return f"{v:.1f}"


def plot(w, h, xr, yr, series, xticks, yticks, xlabel, ylabel,
         xfmt=str, yfmt=str, ml=50, mr=12, mt=10, mb=38):
    """Inline SVG chart. series: (kind, css_class, points), kind in line|dash|dots|pts."""
    x0, x1 = xr
    y0, y1 = yr
    pw, ph = w - ml - mr, h - mt - mb
    X = lambda x: ml + (x - x0) / (x1 - x0) * pw
    Y = lambda y: mt + (1 - (y - y0) / (y1 - y0)) * ph
    o = [f'<svg viewBox="0 0 {w} {h}" class="plot" role="img" aria-label="{ylabel} against {xlabel}">']
    for t in yticks:
        o.append(f'<line class="grid" x1="{ml}" x2="{ml + pw}" y1="{f1(Y(t))}" y2="{f1(Y(t))}"/>')
        o.append(f'<text class="tl" x="{ml - 6}" y="{f1(Y(t) + 3.5)}" text-anchor="end">{yfmt(t)}</text>')
    for t in xticks:
        o.append(f'<line class="grid" y1="{mt}" y2="{mt + ph}" x1="{f1(X(t))}" x2="{f1(X(t))}"/>')
        o.append(f'<text class="tl" x="{f1(X(t))}" y="{mt + ph + 14}" text-anchor="middle">{xfmt(t)}</text>')
    o.append(f'<rect class="frame" x="{ml}" y="{mt}" width="{pw}" height="{ph}"/>')
    for kind, cls, pts in series:
        if kind in ("line", "dash"):
            d = " ".join(f"{f1(X(x))},{f1(Y(y))}" for x, y in pts)
            o.append(f'<polyline class="{cls}" points="{d}"/>')
        else:
            r = 3.6 if kind == "dots" else 2.2
            o += [f'<circle class="{cls}" cx="{f1(X(x))}" cy="{f1(Y(y))}" r="{r}"/>' for x, y in pts]
    o.append(f'<text class="al" x="{ml + pw / 2}" y="{h - 4}" text-anchor="middle">{xlabel}</text>')
    o.append(f'<text class="al" transform="translate(12 {mt + ph / 2}) rotate(-90)" text-anchor="middle">{ylabel}</text>')
    o.append("</svg>")
    return "\n".join(o)


def fragments():
    """Charts and table rows for the mockups, keyed by placeholder name."""
    out = {}

    # Calibration curve (mockup 4): blank + 3 standards, blank I0 = 412.4 lx.
    I0 = 412.4
    std = [(0.0, 0.0), (0.02, 0.138), (0.04, 0.268), (0.06, 0.409)]
    n = len(std)
    xm = sum(x for x, _ in std) / n
    ym = sum(y for _, y in std) / n
    sxx = sum((x - xm) ** 2 for x, _ in std)
    sxy = sum((x - xm) * (y - ym) for x, y in std)
    m = sxy / sxx
    q = ym - m * xm
    ssr = sum((y - (m * x + q)) ** 2 for x, y in std)
    sst = sum((y - ym) ** 2 for _, y in std)
    print(f"calibration: slope {m:.3f} ± {math.sqrt(ssr / (n - 2) / sxx):.3f}, "
          f"intercept {q:.4f}, R² {1 - ssr / sst:.5f}  (mockup 4 text quotes these)")
    out["CALROWS"] = "\n".join(
        f'<tr><td class="n">{i if i else "blank"}</td><td class="n">{c:.3f}</td>'
        f'<td class="n">{I0 * 10 ** -a:.1f}</td><td class="n">{10 ** -a:.3f}</td>'
        f'<td class="n">{a:.3f}</td><td class="ok">measured</td></tr>'
        for i, (c, a) in enumerate(std))
    out["CAL"] = plot(460, 290, (0, 0.10), (0, 0.70),
                      [("dash", "fit", [(0, q), (0.10, m * 0.10 + q)]), ("dots", "d-a", std)],
                      [0, 0.02, 0.04, 0.06, 0.08, 0.10], [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7],
                      "c (mol/L)", "A", xfmt=lambda v: f"{v:.2f}", yfmt=lambda v: f"{v:.1f}")

    # First-order kinetics (mockup 5): A(t) = A∞ + A0·e^(−kt), one point every 2 s.
    k, A0, Ainf = 0.00652, 0.80, 0.030
    kin = [(t, Ainf + A0 * math.exp(-k * t) + random.gauss(0, 0.004)) for t in range(0, 301, 2)]
    out["KIN"] = plot(640, 300, (0, 320), (0, 0.9),
                      [("line", "s-a thin", kin),
                       ("dash", "fit", [(t, Ainf + A0 * math.exp(-k * t)) for t in range(0, 321, 4)]),
                       ("pts", "d-a", kin)],
                      list(range(0, 321, 40)), [0, 0.15, 0.3, 0.45, 0.6, 0.75, 0.9],
                      "t (s)", "A", yfmt=lambda v: f"{v:.2f}")
    out["KINROWS"] = "\n".join(
        f'<tr><td class="n">{t:.1f}</td><td class="n">{I0 * 10 ** -a:.1f}</td><td class="n">{a:.4f}</td></tr>'
        for t, a in kin[-6:])

    # Live illuminance sparkline (mockup 2).
    sp = [412.1 + 0.5 * math.sin(i / 5) + random.gauss(0, 0.25) for i in range(60)]
    lo, hi = 410.8, 413.4
    pts = " ".join(f"{f1(4 + i * 252 / 59)},{f1(52 - (v - lo) / (hi - lo) * 48)}" for i, v in enumerate(sp))
    out["SPARK"] = (f'<svg viewBox="0 0 260 56" class="plot spark" role="img" '
                    f'aria-label="Illuminance over the last 30 seconds"><polyline class="s-a" points="{pts}"/>'
                    f'<circle class="d-a" cx="256" cy="{f1(52 - (sp[-1] - lo) / (hi - lo) * 48)}" r="3"/></svg>')

    # Field profile of a finite solenoid centred at 70 mm, scan stopped at 80 mm (mockup 6).
    a, b, R = 40.0, 100.0, 15.0
    g = lambda z: (z - a) / math.hypot(z - a, R) - (z - b) / math.hypot(z - b, R)
    K = 3.2 / g(70.0)
    zs = [20 + 0.5 * i for i in range(121)]
    bz = [(z, K * g(z) + random.gauss(0, 0.02)) for z in zs]
    bx = [(z, 0.04 + random.gauss(0, 0.02)) for z in zs]
    by = [(z, -0.06 + random.gauss(0, 0.02)) for z in zs]
    print(f"field: Bz at 80 mm = {bz[-1][1]:.2f} mT  (mockup 6 text quotes this)")
    out["FIELD"] = plot(660, 320, (20, 120), (-0.5, 3.5),
                        [("line", "s-x", bx), ("line", "s-y", by), ("line", "s-z", bz), ("dots", "d-z", [bz[-1]])],
                        list(range(20, 121, 10)), [-0.5, 0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5],
                        "Position (mm)", "B (mT)", yfmt=lambda v: f"{v:.1f}")

    # Spectral response with LED peaks (mockup 9). Shapes are illustrative, not datasheet data.
    ws = list(range(350, 1101, 5))
    c0r = [0.95 * math.exp(-((w - 690) / 190) ** 2) + 0.38 * math.exp(-((w - 880) / 110) ** 2) for w in ws]
    c1r = [0.9 * math.exp(-((w - 860) / 115) ** 2) + 0.05 * math.exp(-((w - 600) / 80) ** 2) for w in ws]
    m0 = max(c0r)
    leds = [("led-b", 470), ("led-g", 520), ("led-o", 605), ("led-r on", 625)]
    out["SPECTRAL"] = plot(620, 250, (350, 1100), (0, 1.05),
                           [("line", cls, [(x, 0), (x, 1.02)]) for cls, x in leds]
                           + [("line", "s-z", [(w, v / m0) for w, v in zip(ws, c0r)]),
                              ("line", "s-x", [(w, v / m0) for w, v in zip(ws, c1r)])],
                           list(range(400, 1101, 100)), [0, 0.25, 0.5, 0.75, 1.0],
                           "Wavelength (nm)", "Relative response", yfmt=lambda v: f"{v:.2f}")
    return out


def build_page():
    html = TEMPLATE.read_text(encoding="utf-8")
    for key, val in fragments().items():
        html = html.replace(f"%%{key}%%", val)
    left = re.findall(r"%%\w+%%", html)
    if left:
        raise SystemExit(f"unfilled placeholders: {left}")
    PAGE.write_text(html, encoding="utf-8")
    print(f"written {PAGE.name} ({len(html)} bytes)")
    return html


def build_pdf(html, out):
    """Print the page to A4 with headless Chrome, using print.css and rendering the mermaid diagrams."""
    chrome = next((shutil.which(c) for c in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")
                   if shutil.which(c)), None)
    if not chrome:
        raise SystemExit("Google Chrome or Chromium is needed for --pdf")
    css = PRINT_CSS.read_text(encoding="utf-8")
    printable = HERE / "_print.html"
    printable.write_text(
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        + html
        + f"\n<style>\n{css}\n</style>\n<script src=\"{MERMAID_JS}\"></script>\n"
        + '<script>mermaid.initialize({startOnLoad:true, theme:"neutral", fontFamily:"IBM Plex Sans, sans-serif"});</script>\n',
        encoding="utf-8")
    try:
        subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        "--run-all-compositor-stages-before-draw", "--virtual-time-budget=25000",
                        f"--print-to-pdf={out}", printable.as_uri()],
                       check=True, capture_output=True)
    finally:
        printable.unlink(missing_ok=True)
    print(f"written {out.name}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdf", nargs="?", const=HERE / "labdaemon-design.pdf", type=Path,
                    help="also print a PDF (default: labdaemon-design.pdf)")
    args = ap.parse_args()
    page = build_page()
    if args.pdf:
        build_pdf(page, args.pdf.resolve())
