from PyQt5 import Qt
from .base import ContextCommand
from ..model import MemoryMap, ByteCodec, DataType


class ExtractMemoryMapCommand(ContextCommand):
    """
    Extract a memory map from another one.

    The memory before and after are set as UNKNOWN data.
    """
    def __init__(self, parent: Qt.QUndoCommand | None = None):
        ContextCommand.__init__(self, parent)
        self._cutMem: MemoryMap | None = None
        self._beforeMem: MemoryMap | None = None
        self._newMem: MemoryMap | None = None
        self._afterMem: MemoryMap | None = None

    def setCommand(self, cutMem: MemoryMap, newMem: MemoryMap):
        beforeMem = MemoryMap(
            byte_offset=cutMem.byte_offset,
            byte_length=newMem.byte_offset - cutMem.byte_offset,
            byte_codec=ByteCodec.RAW,
            data_type=DataType.UNKNOWN,
        )

        afterMem = MemoryMap(
            byte_offset=newMem.byte_end,
            byte_length=cutMem.byte_length - beforeMem.byte_length - newMem.byte_length,
            byte_codec=ByteCodec.RAW,
            data_type=DataType.UNKNOWN,
        )

        if beforeMem.byte_length < 0:
            raise RuntimeError("Inconsistencies in memory map creation")

        if afterMem.byte_length < 0:
            raise RuntimeError("Inconsistencies in memory map creation")

        if cutMem.byte_end != afterMem.byte_end:
            raise RuntimeError("Inconsistencies in memory map creation")

        self._cutMem = cutMem
        self._newMem = newMem
        if beforeMem.byte_length != 0:
            self._beforeMem = beforeMem
        else:
            self._beforeMem = None
        if afterMem.byte_length != 0:
            self._afterMem = afterMem
        else:
            self._afterMem = None

    def redo(self):
        if self._cutMem is None:
            return

        context = self.context()
        memoryMapList = context.memoryMapList()
        index = memoryMapList.objectIndex(self._cutMem).row()
        memoryMapList.removeObject(self._cutMem)

        if self._beforeMem is not None:
            memoryMapList.insertObject(index, self._beforeMem)
            index += 1
        memoryMapList.insertObject(index, self._newMem)
        index += 1
        if self._afterMem is not None:
            memoryMapList.insertObject(index, self._afterMem)

    def undo(self):
        if self._cutMem is None:
            return

        context = self.context()
        memoryMapList = context.memoryMapList()
        index = -1

        if self._beforeMem is not None:
            index = memoryMapList.objectIndex(self._beforeMem).row()
            memoryMapList.removeObject(self._beforeMem)
        if index == -1:
            index = memoryMapList.objectIndex(self._newMem).row()
        memoryMapList.removeObject(self._newMem)
        if self._afterMem is not None:
            memoryMapList.removeObject(self._afterMem)

        memoryMapList.insertObject(index, self._cutMem)
