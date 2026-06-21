from krita import Extension

from .qt_compat import QObject


class GapFillExtension(Extension):
    def __init__(self, parent):
        super().__init__(parent)

    def setup(self):
        pass

    def createActions(self, window):
        action = window.createAction(
            "gapfill_krita_toggle_docker", "Show GapFill Docker", "tools/scripts"
        )
        action.triggered.connect(lambda: self._show_docker(window))

    @staticmethod
    def _show_docker(window):
        docker = window.qwindow().findChild(QObject, "gapfill_krita_docker")
        if docker is not None:
            docker.show()
            docker.raise_()
