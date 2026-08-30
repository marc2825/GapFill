from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path
from types import ModuleType


class _Signal:
    def __init__(self):
        self._slots = []

    def connect(self, slot):
        self._slots.append(slot)

    def emit(self, checked=False):
        for slot in self._slots:
            if inspect.signature(slot).parameters:
                slot(checked)
            else:
                slot()


class _Action:
    def __init__(self):
        self.triggered = _Signal()


class _Docker:
    def __init__(self, name="gapfill_krita_docker"):
        self._name = name
        self.shown = False
        self.raised = False

    def objectName(self):
        return self._name

    def show(self):
        self.shown = True

    def raise_(self):
        self.raised = True


class _Window:
    def __init__(self, dockers=()):
        self._dockers = list(dockers)
        self.deleted = False
        self.actions = []

    def createAction(self, _identifier, _text, _location):
        if self.deleted:
            raise RuntimeError("wrapped C/C++ object of type Window has been deleted")
        action = _Action()
        self.actions.append(action)
        return action

    def dockers(self):
        if self.deleted:
            raise RuntimeError("wrapped C/C++ object of type Window has been deleted")
        return list(self._dockers)

    def qwindow(self):
        if self.deleted:
            raise RuntimeError("wrapped C/C++ object of type Window has been deleted")
        raise AssertionError("The lifecycle-safe path must not use qwindow().")


class _Application:
    def __init__(self):
        self.active_window = None

    def activeWindow(self):
        return self.active_window


def _load_extension(monkeypatch, application):
    import gapfill_krita

    krita = ModuleType("krita")

    class Extension:
        def __init__(self, parent):
            self.parent = parent

    class Krita:
        @staticmethod
        def instance():
            return application

    krita.Extension = Extension
    krita.Krita = Krita
    monkeypatch.setitem(sys.modules, "krita", krita)
    module_name = "gapfill_krita._extension_lifecycle_test"
    monkeypatch.delitem(sys.modules, module_name, raising=False)
    source = Path(gapfill_krita.__file__).with_name("extension.py")
    spec = importlib.util.spec_from_file_location(module_name, source)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.GapFillExtension(application)


def test_action_resolves_active_window_after_creator_wrapper_is_deleted(monkeypatch) -> None:
    application = _Application()
    extension = _load_extension(monkeypatch, application)
    stale_docker = _Docker()
    creator = _Window([stale_docker])
    extension.createActions(creator)
    creator.deleted = True

    active_docker = _Docker()
    application.active_window = _Window([active_docker])
    creator.actions[0].triggered.emit()

    assert active_docker.shown and active_docker.raised
    assert not stale_docker.shown


def test_action_without_active_window_fails_closed(monkeypatch) -> None:
    application = _Application()
    extension = _load_extension(monkeypatch, application)
    creator_docker = _Docker()
    creator = _Window([creator_docker])
    extension.createActions(creator)

    application.active_window = None
    creator.actions[0].triggered.emit()

    assert not creator_docker.shown


def test_action_uses_only_the_active_windows_gapfill_docker(monkeypatch) -> None:
    application = _Application()
    extension = _load_extension(monkeypatch, application)
    other_docker = _Docker()
    other_window = _Window([other_docker])
    extension.createActions(other_window)

    active_docker = _Docker()
    unrelated = _Docker("some_other_docker")
    active_window = _Window([unrelated, active_docker])
    application.active_window = active_window
    other_window.actions[0].triggered.emit()

    assert active_docker.shown and active_docker.raised
    assert not unrelated.shown
    assert not other_docker.shown
