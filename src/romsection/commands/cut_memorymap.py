from PyQt5 import Qt
from .base import ContextCommand
from ..model import MemoryMap, ByteCodec, DataType


class CutMemoryMapCommand(ContextCommand):
    def __init__(self, parent: Qt.QUndoCommand | None = None):
        ContextCommand.__init__(self, parent)
        self._cutMem: MemoryMap | None = None
        self._beforeOffsetMem: MemoryMap | None = None
        self._afterOffsetMem: MemoryMap | None = None

    def setCommand(self, cutMem: MemoryMap, romOffset: int):
        if romOffset <= cutMem.byte_offset:
            # no op
            self._cutMem = None
            return
        if romOffset >= cutMem.byte_end:
            # no op
            self._cutMem = None
            return

        self._cutMem = cutMem
        self._beforeOffsetMem = MemoryMap(
            byte_offset=cutMem.byte_offset,
            byte_length=romOffset - cutMem.byte_offset,
            data_type=DataType.UNKNOWN,
        )
        self._afterOffsetMem = MemoryMap(
            byte_offset=romOffset,
            byte_length=cutMem.byte_offset + cutMem.byte_length - romOffset,
            data_type=DataType.UNKNOWN,
        )

    def redo(self):
        if self._cutMem is None:
            return

        context = self.context()
        memoryMapList = context.memoryMapList()
        index = memoryMapList.objectIndex(self._cutMem).row()
        memoryMapList.removeObject(self._cutMem)
        memoryMapList.insertObject(index, self._beforeOffsetMem)
        memoryMapList.insertObject(index + 1, self._afterOffsetMem)

    def undo(self):
        if self._cutMem is None:
            return

        context = self.context()
        memoryMapList = context.memoryMapList()
        index = memoryMapList.objectIndex(self._beforeOffsetMem).row()
        memoryMapList.removeObject(self._beforeOffsetMem)
        memoryMapList.removeObject(self._afterOffsetMem)
        memoryMapList.insertObject(index, self._cutMem)
