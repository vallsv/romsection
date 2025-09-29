from PyQt5 import Qt

from ..gba_file import DataType


class DataTypeList(Qt.QListWidget):
    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QListWidget.__init__(self, parent)
        self.setUniformItemSizes(True)
        self.setVerticalScrollBarPolicy(Qt.Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(Qt.QSizePolicy.Expanding, Qt.QSizePolicy.Maximum)
        self.setSizeAdjustPolicy(Qt.QListWidget.AdjustToContents)
        self.setResizeMode(Qt.QListView.Fixed)

        item = Qt.QListWidgetItem()
        item.setText(f"GBA ROM header")
        item.setData(Qt.Qt.UserRole, DataType.GBA_ROM_HEADER)
        item.setIcon(Qt.QIcon("icons:gba.png"))
        self.addItem(item)

        item = Qt.QListWidgetItem()
        item.setText(f"Image")
        item.setData(Qt.Qt.UserRole, DataType.IMAGE)
        item.setIcon(Qt.QIcon("icons:image.png"))
        self.addItem(item)

        item = Qt.QListWidgetItem()
        item.setText(f"Palette")
        item.setData(Qt.Qt.UserRole, DataType.PALETTE)
        item.setIcon(Qt.QIcon("icons:palette.png"))
        self.addItem(item)

        item = Qt.QListWidgetItem()
        item.setText(f"Tile set")
        item.setData(Qt.Qt.UserRole, DataType.TILE_SET)
        item.setIcon(Qt.QIcon("icons:tileset.png"))
        self.addItem(item)

        item = Qt.QListWidgetItem()
        item.setText(f"Padding")
        item.setData(Qt.Qt.UserRole, DataType.PADDING)
        item.setIcon(Qt.QIcon("icons:padding.png"))
        self.addItem(item)

        item = Qt.QListWidgetItem()
        item.setText(f"Unknown")
        item.setData(Qt.Qt.UserRole, DataType.UNKNOWN)
        item.setIcon(Qt.QIcon("icons:unknown.png"))
        self.addItem(item)

        rect = self.visualItemRect(item)
        self.setMinimumHeight(rect.height() * self.count() + 4)
        self.setMaximumHeight(rect.height() * self.count() + 4)

    def selectedDataType(self) -> DataType | None:
        items = self.selectedItems()
        if len(items) != 1:
            return None
        dataType = items[0].data(Qt.Qt.UserRole)
        return dataType

    def _findItemFromDataType(self, dataType: DataType | None) -> Qt.QListWidgetItem | None:
        if dataType is None:
            return None
        for i in range(self.count()):
            item = self.item(i)
            if item.data(Qt.Qt.UserRole) == dataType:
                return item
        return None

    def selectDataType(self, dataType: DataType | None):
        item = self._findItemFromDataType(dataType)
        if item is not None:
            i = self.row(item)
            self.setCurrentRow(i)
        else:
            self.setCurrentRow(-1)
