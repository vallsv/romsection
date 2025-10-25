from PyQt5 import Qt
from .widgets.memory_map_list_model import MemoryMapListModel
from .gba_file import GBAFile
from .model import MemoryMap


class Context(Qt.QObject):

    romChanged = Qt.pyqtSignal(object)

    def __init__(self, parent: Qt.QObject | None) -> None:
        Qt.QObject.__init__(self, parent)
        self._mainWidget: Qt.QWidget | None = None
        self._memoryMapList = MemoryMapListModel(self)
        self._rom: GBAFile | None = None
        self._currentMemoryMap: MemoryMap | None = None
        self._undoStack = Qt.QUndoStack(self)

    def mainWidget(self) -> Qt.QWidget:
        assert self._mainWidget is not None
        return self._mainWidget

    def undoStack(self) -> Qt.QUndoStack:
        return self._undoStack

    def memoryMapList(self) -> MemoryMapListModel:
        return self._memoryMapList

    def romOrNone(self) -> GBAFile | None:
        return self._rom

    def rom(self) -> GBAFile:
        assert self._rom is not None
        return self._rom

    def setRom(self, rom: GBAFile | None):
        self._rom = rom
        if rom is None:
            self._memoryMapList.setObjectList([])
        else:
            self._memoryMapList.setObjectList(rom.offsets)
        self._undoStack.clear()
        self.romChanged.emit(rom)

    def _setCurrentMemoryMap(self, mem: MemoryMap | None):
        self._currentMemoryMap = mem

    def currentMemoryMap(self) -> MemoryMap | None:
        return self._currentMemoryMap

    def updateMemoryMap(self, previous: MemoryMap, next: MemoryMap):
        from .commands.update_memorymap import UpdateMemoryMapCommand
        command = UpdateMemoryMapCommand()
        command.setContext(self)
        command.setCommand(previous, next)
        self._undoStack.push(command)

    def pushCommand(self, command: Qt.QUndoCommand):
        command.setContext(self)
        self._undoStack.push(command)
