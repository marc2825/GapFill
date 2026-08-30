from krita import Extension, Krita

DOCKER_OBJECT_NAME = "gapfill_krita_docker"


class GapFillExtension(Extension):
    def __init__(self, parent):
        super().__init__(parent)

    def setup(self):
        pass

    def createActions(self, window):
        action = window.createAction(
            "gapfill_krita_toggle_docker", "Show GapFill Docker", "tools/scripts"
        )
        action.triggered.connect(self._show_docker)

    @staticmethod
    def _show_docker(_checked=False):
        window = Krita.instance().activeWindow()
        if window is None:
            return
        try:
            dockers = window.dockers()
            docker = next(
                (item for item in dockers if item.objectName() == DOCKER_OBJECT_NAME),
                None,
            )
            if docker is not None:
                docker.show()
                docker.raise_()
        except RuntimeError:
            # The active window or one of its dockers may be deleted while Qt
            # dispatches the action. Treat that lifecycle race as no target.
            return
