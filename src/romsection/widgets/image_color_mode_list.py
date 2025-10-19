from PyQt5 import Qt

from ..gba_file import ImageColorMode


class ImageColorModeList(Qt.QListWidget):

    valueChanged = Qt.pyqtSignal(object)

    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QListWidget.__init__(self, parent)
        self.setUniformItemSizes(True)
        self.setVerticalScrollBarPolicy(Qt.Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(Qt.QSizePolicy.Expanding, Qt.QSizePolicy.Maximum)
        self.setSizeAdjustPolicy(Qt.QListWidget.AdjustToContents)

        item = Qt.QListWidgetItem()
        item.setText(f"Indexed 256 colors")
        item.setData(Qt.Qt.UserRole, ImageColorMode.INDEXED_8BIT)
        self.addItem(item)

        item = Qt.QListWidgetItem()
        item.setText(f"Indexed 16 colors")
        item.setData(Qt.Qt.UserRole, ImageColorMode.INDEXED_4BIT)
        self.addItem(item)

        rect = self.visualItemRect(item)
        self.setMinimumSize(150, -1)
        self.setMaximumHeight(rect.height() * self.count() + 4)

        self.itemSelectionChanged.connect(self._onItemSelectionChanged)

    def _onItemSelectionChanged(self):
        self.valueChanged.emit(self.selectedValue())

    def selectedValue(self) -> ImageColorMode | None:
        items = self.selectedItems()
        if len(items) != 1:
            return None
        value = items[0].data(Qt.Qt.UserRole)
        return value

    def _findItemFromValue(self, value: ImageColorMode | None) -> Qt.QListWidgetItem | None:
        if value is None:
            return None
        for i in range(self.count()):
            item = self.item(i)
            if item.data(Qt.Qt.UserRole) == value:
                return item
        return None

    def selectValue(self, value: ImageColorMode | None):
        item = self._findItemFromValue(value)
        if item is not None:
            i = self.row(item)
            self.setCurrentRow(i)
        else:
            self.setCurrentRow(-1)
