from PyQt5 import Qt

from ..gba_file import GBAFile
from ..model import MemoryMap


class Behavior(Qt.QRunnable):
    """
    Dedicated runnable for this application in order to reuse glue code.

    FIXME: Rework context as a dedicated class, from Extractor
    FIXME: QRunnable is supposed to be thread, it's not the way we use it
    """
    def __init__(self):
        Qt.QRunnable.__init__(self)
        self._context: Qt.QWidget | None = None

    def setContext(self, context: Qt.QWidget):
        self._context = context

    def context(self) -> Qt.QWidget:
        assert self._context is not None, "Not properly initialized"
        return self._context
