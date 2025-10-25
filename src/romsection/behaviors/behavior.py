from PyQt5 import Qt

from ..gba_file import GBAFile
from ..model import MemoryMap
from ..context import Context


class Behavior(Qt.QRunnable):
    """
    Dedicated runnable for this application in order to reuse glue code.

    FIXME: QRunnable is supposed to be threaded, it's not the way we use it
    """
    def __init__(self):
        Qt.QRunnable.__init__(self)
        self._context: Context | None = None

    def setContext(self, context: Context | None):
        self._context = context

    def context(self) -> Context:
        assert self._context is not None, "Not properly initialized"
        return self._context
