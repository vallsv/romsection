from PyQt5 import Qt


class PaletteSizeList(Qt.QListWidget):
    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QListWidget.__init__(self, parent)
        self.setUniformItemSizes(True)
        self.setVerticalScrollBarPolicy(Qt.Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(Qt.QSizePolicy.Expanding, Qt.QSizePolicy.Maximum)
        self.setSizeAdjustPolicy(Qt.QListWidget.AdjustToContents)
        self.setResizeMode(Qt.QListView.Fixed)

        item = Qt.QListWidgetItem()
        item.setText(f"16 colors")
        item.setData(Qt.Qt.UserRole, 16)
        self.addItem(item)

        item = Qt.QListWidgetItem()
        item.setText(f"256 colors")
        item.setData(Qt.Qt.UserRole, 256)
        self.addItem(item)

        rect = self.visualItemRect(item)
        self.setMaximumHeight(rect.height() * self.count() + 4)

    def selectedPaletteSize(self) -> int | None:
        items = self.selectedItems()
        if len(items) != 1:
            return None
        size = items[0].data(Qt.Qt.UserRole)
        return size

    def _findItemFromPaletteSize(self, size: int | None) -> Qt.QListWidgetItem | None:
        if size is None:
            return None
        for i in range(self.count()):
            item = self.item(i)
            if item.data(Qt.Qt.UserRole) == size:
                return item
        return None

    def selectPaletteSize(self, size: int | None):
        item = self._findItemFromPaletteSize(size)
        if item is not None:
            i = self.row(item)
            self.setCurrentRow(i)
        else:
            self.setCurrentRow(-1)
