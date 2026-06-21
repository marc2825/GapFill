from krita import DockWidgetFactory, DockWidgetFactoryBase, Krita

from .docker import GapFillDocker
from .extension import GapFillExtension


def register() -> None:
    app = Krita.instance()
    app.addExtension(GapFillExtension(app))
    app.addDockWidgetFactory(
        DockWidgetFactory(
            "gapfill_krita_docker",
            DockWidgetFactoryBase.DockRight,
            GapFillDocker,
        )
    )
