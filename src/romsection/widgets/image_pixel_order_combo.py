from PyQt5 import Qt

from ..gba_file import ImagePixelOrder


class ImagePixelOrderCombo(Qt.QComboBox):
    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QComboBox.__init__(self, parent)
        self.addItem("Normal", ImagePixelOrder.NORMAL)
        self.addItem("Tiled 8×8", ImagePixelOrder.TILED_8X8)
        self.setCurrentIndex(0)

    def selectedValue(self) -> ImagePixelOrder | None:
        index = self.currentIndex()
        if index == -1:
            return None
        return self.itemData(index)

    def selectValue(self, pixelOrder: ImagePixelOrder | None):
        if pixelOrder is None:
            self.setCurrentIndex(-1)
            return
        for index in range(self.count()):
            if  self.itemData(index) == pixelOrder:
                self.setCurrentIndex(index)
                return
        self.setCurrentIndex(-1)
