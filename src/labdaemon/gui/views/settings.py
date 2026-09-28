"""Settings view (M0: language and polling; the rest arrives with its milestone)."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QFormLayout, QLabel, QVBoxLayout, QWidget

from labdaemon.core.errors import PolicyLocked
from labdaemon.core.i18n import LANGUAGES
from labdaemon.core.settings import Settings


class SettingsView(QWidget):
    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        v = QVBoxLayout(self)
        title = QLabel(self.tr("Settings"))
        title.setStyleSheet("font-weight:600; font-size:15pt;")
        v.addWidget(title)
        form = QFormLayout()
        v.addLayout(form)

        self.language = QComboBox()
        for code, name in LANGUAGES.items():
            self.language.addItem(name, code)
        self.language.setCurrentIndex(max(0, self.language.findData(settings.get("app.language"))))
        self.language.activated.connect(lambda i: self._save("app.language", self.language.itemData(i)))
        form.addRow(self.tr("Language"), self._with_note(self.language, "app.language",
                                                          self.tr("Applies after restarting LabDaemon.")))

        self.poll = QDoubleSpinBox()
        self.poll.setRange(0.1, 10.0)
        self.poll.setSingleStep(0.1)
        self.poll.setDecimals(1)
        self.poll.setSuffix(" s")
        self.poll.setKeyboardTracking(False)
        self.poll.setValue(float(settings.get("devices.poll_interval_s")))
        self.poll.valueChanged.connect(lambda x: self._save("devices.poll_interval_s", round(x, 1)))
        form.addRow(self.tr("Live reading every"), self._with_note(
            self.poll, "devices.poll_interval_s", self.tr("Applies to boards connected from now on.")))

        paths = settings.paths
        info = QLabel("\n".join([
            self.tr("Settings file: {0}").format(paths.user_settings),
            self.tr("Machine policy: {0}").format(paths.policy),
            self.tr("Logs: {0}").format(paths.log_dir),
        ]))
        info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        info.setStyleSheet("color: palette(placeholder-text);")
        v.addSpacing(12)
        v.addWidget(info)
        v.addStretch()

    def _with_note(self, editor: QWidget, key: str, note: str) -> QWidget:
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(editor)
        if self.settings.is_locked(key):
            editor.setEnabled(False)
            note = self.tr("Set by your administrator.")
        label = QLabel(note)
        label.setStyleSheet("color: palette(placeholder-text);")
        lay.addWidget(label)
        return box

    def _save(self, key: str, value: object) -> None:
        try:
            self.settings.set(key, value)
            self.settings.save()
        except (PolicyLocked, OSError) as e:
            self.window().statusBar().showMessage(str(e), 8000)
