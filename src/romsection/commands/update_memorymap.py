from PyQt5 import Qt
from .base import ContextCommand
from ..model import MemoryMap


class UpdateMemoryMapCommand(ContextCommand):
    def __init__(self, parent: Qt.QUndoCommand | None = None):
        ContextCommand.__init__(self, parent)
        self._currentMem: MemoryMap | None = None
        self._newMem: MemoryMap | None = None

    def setCommand(self, currentMem: MemoryMap, newMem: MemoryMap):
        self._currentMem = currentMem
        self._newMem = newMem

    def redo(self):
        memoryMapList = self.context().memoryMapList()
        memoryMapList.replaceObject(self._currentMem, self._newMem)

    def undo(self):
        memoryMapList = self.context().memoryMapList()
        memoryMapList.replaceObject(self._newMem, self._currentMem)
