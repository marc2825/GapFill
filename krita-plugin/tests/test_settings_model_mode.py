from __future__ import annotations

from gapfill_krita.engine.types import ModelBoundaryMode
from gapfill_krita.settings import GapFillSettings


class _MemorySettings:
    values: dict[str, object] = {}

    def __init__(self, _organization: str, _application: str):
        pass

    def value(self, key: str, default=None):
        return self.values.get(key, default)

    def setValue(self, key: str, value) -> None:  # noqa: N802 - Qt API
        self.values[key] = value


def test_missing_persisted_mode_defaults_to_published_line_only(monkeypatch) -> None:
    import gapfill_krita.settings as settings_module

    _MemorySettings.values = {}
    monkeypatch.setattr(settings_module, "QSettings", _MemorySettings)

    assert GapFillSettings.load().model_boundary_mode is ModelBoundaryMode.LINE_ONLY


def test_line_or_guides_uses_a_stable_value_and_survives_reload(monkeypatch) -> None:
    import gapfill_krita.settings as settings_module

    _MemorySettings.values = {}
    monkeypatch.setattr(settings_module, "QSettings", _MemorySettings)
    settings = GapFillSettings(model_boundary_mode=ModelBoundaryMode.LINE_OR_GUIDES)
    settings.save()

    assert _MemorySettings.values["modelBoundaryMode"] == "line_or_guides"
    assert GapFillSettings.load().model_boundary_mode is ModelBoundaryMode.LINE_OR_GUIDES


def test_unknown_future_or_corrupt_mode_fails_closed_to_line_only(monkeypatch) -> None:
    import gapfill_krita.settings as settings_module

    _MemorySettings.values = {"modelBoundaryMode": "localized-ui-text"}
    monkeypatch.setattr(settings_module, "QSettings", _MemorySettings)

    assert GapFillSettings.load().model_boundary_mode is ModelBoundaryMode.LINE_ONLY
