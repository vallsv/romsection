from PyQt5 import Qt

from ..gba_file import PixelOrder


class PixelOrderList(Qt.QListWidget):
    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QListWidget.__init__(self, parent)
        self.setUniformItemSizes(True)
        self.setVerticalScrollBarPolicy(Qt.Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(Qt.QSizePolicy.Expanding, Qt.QSizePolicy.Maximum)
        self.setSizeAdjustPolicy(Qt.QListWidget.AdjustToContents)

        item = Qt.QListWidgetItem()
        item.setText(f"Normal")
        item.setData(Qt.Qt.UserRole, PixelOrder.NORMAL)
        self.addItem(item)

        item = Qt.QListWidgetItem()
        item.setText(f"Tiled 8×8")
        item.setData(Qt.Qt.UserRole, PixelOrder.TILED_8X8)
        self.addItem(item)

    def selectedPixelOrder(self) -> PixelOrder | None:
        items = self.selectedItems()
        if len(items) != 1:
            return None
        pixelOrder = items[0].data(Qt.Qt.UserRole)
        return pixelOrder

    def _findItemFromPixelOrder(self, pixelOrder: PixelOrder | None) -> Qt.QListWidgetItem | None:
        if pixelOrder is None:
            return None
        for i in range(self.count()):
            item = self.item(i)
            if item.data(Qt.Qt.UserRole) == pixelOrder:
                return item
        return None

    def selectPixelOrder(self, pixelOrder: PixelOrder | None):
        item = self._findItemFromPixelOrder(pixelOrder)
        if item is not None:
            i = self.row(item)
            self.setCurrentRow(i)
        else:
            self.setCurrentRow(-1)
