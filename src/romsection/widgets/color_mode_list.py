from PyQt5 import Qt

from ..gba_file import ColorMode


class ColorModeList(Qt.QListWidget):
    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QListWidget.__init__(self, parent)
        self.setUniformItemSizes(True)
        self.setVerticalScrollBarPolicy(Qt.Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(Qt.QSizePolicy.Expanding, Qt.QSizePolicy.Maximum)
        self.setSizeAdjustPolicy(Qt.QListWidget.AdjustToContents)

        item = Qt.QListWidgetItem()
        item.setText(f"Indexed 256 colors")
        item.setData(Qt.Qt.UserRole, ColorMode.INDEXED_8BIT)
        self.addItem(item)

        item = Qt.QListWidgetItem()
        item.setText(f"Indexed 16 colors")
        item.setData(Qt.Qt.UserRole, ColorMode.INDEXED_4BIT)
        self.addItem(item)

    def selectedColorMode(self) -> ColorMode | None:
        items = self.selectedItems()
        if len(items) != 1:
            return None
        colorMode = items[0].data(Qt.Qt.UserRole)
        return colorMode

    def _findItemFromColorMode(self, colorMode: ColorMode | None) -> Qt.QListWidgetItem | None:
        if colorMode is None:
            return None
        for i in range(self.count()):
            item = self.item(i)
            if item.data(Qt.Qt.UserRole) == colorMode:
                return item
        return None

    def selectColorMode(self, colorMode: ColorMode | None):
        item = self._findItemFromColorMode(colorMode)
        if item is not None:
            i = self.row(item)
            self.setCurrentRow(i)
        else:
            self.setCurrentRow(-1)
