"""Qt-free core: contracts, services and the plugin runtime.

Nothing in this package (or in transports/, devices/) may import PySide6 or pyqtgraph;
tests/architecture enforces it.
"""

API_VERSION = 1
"""Plugin API version. Plugins declare the version they were written for (§5 of the design)."""
