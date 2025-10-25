from PyQt5 import Qt
from .base import ContextCommand
from ..model import MemoryMap


class InsertMemoryMapCommand(ContextCommand):
    def __init__(self, parent: Qt.QUndoCommand | None = None):
        ContextCommand.__init__(self, parent)
        self._mem: MemoryMap | None = None
        self._index = -1

    def setCommand(self, index: int, mem: MemoryMap):
        self._index = index
        self._mem = mem

    def redo(self):
        if self._index == -1:
            return
        memoryMapList = self.context().memoryMapList()
        index = self._index
        memoryMapList.insertObject(index, self._mem)

    def undo(self):
        if self._mem is None:
            return
        context = self.context()
        memoryMapList = context.memoryMapList()
        self._index = memoryMapList.objectIndex(self._mem).row()
        memoryMapList.removeObject(self._mem)
