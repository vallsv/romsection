from PyQt5 import Qt
from ..context import Context

class ContextCommand(Qt.QUndoCommand):
    def __init__(self, parent: Qt.QUndoCommand | None = None):
        Qt.QUndoCommand.__init__(self, parent)
        self._context: Context | None = None

    def setContext(self, context: "Context"):
        self._context = context

    def context(self) -> "Context":
        assert self._context is not None
        return self._context
