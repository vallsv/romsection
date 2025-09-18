from PyQt5 import Qt


class ShapeList(Qt.QListWidget):
    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QListWidget.__init__(self, parent)
        self.setUniformItemSizes(True)

    def addShape(self, shape: tuple[int, int]):
        item = Qt.QListWidgetItem()
        item.setText(f"{shape[1]} × {shape[0]}")
        item.setData(Qt.Qt.UserRole, shape)
        self.addItem(item)

    def selectedShape(self) -> tuple[int, int] | None:
        items = self.selectedItems()
        if len(items) != 1:
            return None
        shape = items[0].data(Qt.Qt.UserRole)
        return shape

    def _findItemFromShape(self, shape: tuple[int, int] | None) -> Qt.QListWidgetItem | None:
        if shape is None:
            return None
        for i in range(self.count()):
            item = self.item(i)
            if item.data(Qt.Qt.UserRole) == shape:
                return item
        return None

    def selectShape(self, shape: tuple[int, int] | None):
        item = self._findItemFromShape(shape)
        if item is not None:
            i = self.row(item)
            self.setCurrentRow(i)
        else:
            self.setCurrentRow(-1)
