import io
import queue
from PyQt5 import Qt

from ..model import MemoryMap, ByteCodec, DataType
from . import search
from .behavior import Behavior
from ..parsers import lz77
from .. import qt_utils


class BehaviorAtRomOffset(Behavior):

    def __init__(self):
        Behavior.__init__(self)
        self.__offset: int | None = None

    def setOffset(self, offset: int):
        self.__offset = offset

    def offset(self) -> int | None:
        return self.__offset

    def createAction(self, parent: Qt.QObject) -> Qt.QAction:
        action = Qt.QAction(parent)
        action.setText(type(self).__name__)
        action.triggered.connect(self.run)
        return action

    def headerSize(self) -> int:
        """
        Return the minimal size expected to check potential
        valid content.

        This change the way `isValidHeader` is called.
        """
        return 0

    def isValidHeader(self, header: bytes):
        """
        Check is the head of that content is valid.

        It's of the size of `headerSize`.

        Argument:
            data: The data to check, which have the size of the
                  `headerSize`.

        Return `True` if this `data` is potentially
        a valid content to process.
        """
        return True
