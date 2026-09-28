import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from labdaemon.core import i18n  # noqa: E402
from labdaemon.core.manager import DeviceManager  # noqa: E402
from labdaemon.core.registry import Registry  # noqa: E402
from labdaemon.core.settings import Paths, Settings  # noqa: E402


@pytest.fixture
def settings(tmp_path):
    return Settings(Paths.under(tmp_path))


@pytest.fixture
def registry():
    return Registry().load()


@pytest.fixture
def manager(registry, settings):
    m = DeviceManager(registry, settings)
    yield m
    m.shutdown()


@pytest.fixture(autouse=True)
def english():
    i18n.set_language("en")
    yield
    i18n.set_language("en")
