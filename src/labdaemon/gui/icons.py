"""Line icons for the navigation rail, drawn from SVG paths in the palette's text colour."""

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

PATHS = {
    "experiments": '<path d="M9 3h6M10 3v6l-5.5 9.5A1.7 1.7 0 0 0 6 21h12a1.7 1.7 0 0 0 1.5-2.5L14 9V3M7.5 15h9"/>',
    "devices": '<path d="M7 7h10v10H7zM10 3v4M14 3v4M10 17v4M14 17v4M3 10h4M3 14h4M17 10h4M17 14h4"/>',
    "data": '<path d="M4 5h16v14H4zM4 10h16M4 15h16M10 5v14"/>',
    "firmware": '<path d="M8 8l-4 4 4 4M16 8l4 4-4 4M13.5 5l-3 14"/>',
    "plugins": '<path d="M5 8h4a2 2 0 1 1 4 0h4v4a2 2 0 1 1 0 4v3H5v-3a2 2 0 1 0 0-4z"/>',
    "settings": '<path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>',
}


def _pixmaps(name: str, color: QColor, size: int) -> list[QPixmap]:
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color.name()}" '
           f'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">{PATHS[name]}</svg>')
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    out = []
    for scale in (1, 2):
        pm = QPixmap(size * scale, size * scale)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        renderer.render(painter, QRectF(0, 0, size * scale, size * scale))
        painter.end()
        pm.setDevicePixelRatio(scale)
        out.append(pm)
    return out


def icon(name: str, color: QColor, checked_color: QColor | None = None, size: int = 22) -> QIcon:
    """A line icon; with checked_color, a different colour when its button is checked."""
    result = QIcon()
    for pm in _pixmaps(name, color, size):
        result.addPixmap(pm, QIcon.Mode.Normal, QIcon.State.Off)
    for pm in _pixmaps(name, checked_color or color, size):
        result.addPixmap(pm, QIcon.Mode.Normal, QIcon.State.On)
    return result
