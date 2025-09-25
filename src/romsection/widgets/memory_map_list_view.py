from PyQt5 import Qt

from ..gba_file import MemoryMap


class MemoryMapListView(Qt.QListView):
    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QListWidget.__init__(self, parent)
        self.setUniformItemSizes(True)
        self.setIconSize(Qt.QSize(16, 16))

    def selectedMemoryMap(self) -> MemoryMap | None:
        model = self.selectionModel()
        items = model.selectedIndexes()
        if len(items) != 1:
            return None
        mem = items[0].data(Qt.Qt.UserRole)
        return mem

    def selectedMemoryMaps(self) -> list[MemoryMap]:
        model = self.selectionModel()
        items = model.selectedIndexes()
        return [i.data(Qt.Qt.UserRole) for i in items]

    def currentMemoryMap(self) -> MemoryMap | None:
        """Return the current memory map."""
        model = self.selectionModel()
        index = model.currentIndex()
        if not index.isValid():
            return None
        mem = index.data(Qt.Qt.UserRole)
        return mem
