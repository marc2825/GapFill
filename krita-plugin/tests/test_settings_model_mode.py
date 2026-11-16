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


def test_corrupt_numeric_settings_fall_back_to_defaults(monkeypatch) -> None:
    import gapfill_krita.settings as settings_module

    _MemorySettings.values = {
        "threshold": "not-a-number",
        "markerRadius": "nan",
        "sweepRadius": None,
    }
    monkeypatch.setattr(settings_module, "QSettings", _MemorySettings)

    loaded = GapFillSettings.load()
    assert loaded.threshold == 500
    assert loaded.marker_radius == 14.0
    assert loaded.sweep_radius == 18.0

    _MemorySettings.values = {"threshold": "0", "markerRadius": "-3", "sweepRadius": "inf"}
    loaded = GapFillSettings.load()
    assert (loaded.threshold, loaded.marker_radius, loaded.sweep_radius) == (500, 14.0, 18.0)


def test_valid_persisted_numeric_strings_are_preserved(monkeypatch) -> None:
    import gapfill_krita.settings as settings_module

    _MemorySettings.values = {"threshold": "1200", "markerRadius": "9.5", "sweepRadius": "22"}
    monkeypatch.setattr(settings_module, "QSettings", _MemorySettings)

    loaded = GapFillSettings.load()
    assert (loaded.threshold, loaded.marker_radius, loaded.sweep_radius) == (1200, 9.5, 22.0)


def test_unknown_future_or_corrupt_mode_fails_closed_to_line_only(monkeypatch) -> None:
    import gapfill_krita.settings as settings_module

    _MemorySettings.values = {"modelBoundaryMode": "localized-ui-text"}
    monkeypatch.setattr(settings_module, "QSettings", _MemorySettings)

    assert GapFillSettings.load().model_boundary_mode is ModelBoundaryMode.LINE_ONLY
