"""Translations for the core and for plugins (gettext). The GUI's own strings use Qt's tr().

Class-level texts (parameter labels, plugin names) are marked with N_() so they are extracted but
stay in English until displayed; display code passes them through _().
"""

import gettext
import threading
from pathlib import Path

DOMAIN = "labdaemon"
LOCALE_DIR = Path(__file__).resolve().parent.parent / "locale"
LANGUAGES = {"en": "English", "it": "Italiano"}
DEFAULT_LANGUAGE = "en"

_lock = threading.Lock()
_language = DEFAULT_LANGUAGE
_catalogs: list[tuple[str, Path]] = [(DOMAIN, LOCALE_DIR)]
_translation: gettext.NullTranslations = gettext.NullTranslations()


def N_(text: str) -> str:
    """Mark text for extraction without translating it now."""
    return text


def _(text: str) -> str:
    return _translation.gettext(text)


def ngettext(singular: str, plural: str, n: int) -> str:
    return _translation.ngettext(singular, plural, n)


def language() -> str:
    return _language


def set_language(lang: str) -> None:
    """Switch every loaded catalog (core and plugins) to `lang`; unknown texts stay in English."""
    global _language
    with _lock:
        _language = lang if lang in LANGUAGES else DEFAULT_LANGUAGE
        _rebuild()


def add_catalog(domain: str, localedir: Path) -> None:
    """Register a plugin's catalog (its own gettext domain and locale folder)."""
    with _lock:
        if (domain, localedir) not in _catalogs:
            _catalogs.append((domain, localedir))
            _rebuild()


def _rebuild() -> None:
    global _translation
    first: gettext.NullTranslations | None = None
    for domain, localedir in _catalogs:
        t = gettext.translation(domain, localedir, languages=[_language], fallback=True)
        if first is None:
            first = t
        elif first is not t:
            first.add_fallback(t)
    _translation = first or gettext.NullTranslations()
