from PyQt5 import Qt

from ..gba_file import MemoryMap


class MemoryMapList(Qt.QListWidget):
    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QListWidget.__init__(self, parent)
        self.setUniformItemSizes(True)

    def addMemoryMap(self, mem: MemoryMap):
        item = Qt.QListWidgetItem()
        item.setText(f"{mem.byte_offset:08X} {mem.byte_payload: 8d}B")
        item.setData(Qt.Qt.UserRole, mem)
        self.addItem(item)

    def selectedMemoryMap(self) -> MemoryMap | None:
        items = self.selectedItems()
        if len(items) != 1:
            return None
        mem = items[0].data(Qt.Qt.UserRole)
        return mem
