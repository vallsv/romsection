from PyQt5 import Qt

from ..gba_file import ImageColorMode


class ImageColorModeCombo(Qt.QComboBox):
    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QComboBox.__init__(self, parent)
        self.addItem("Indexed 256 colors", ImageColorMode.INDEXED_8BIT)
        self.addItem("Indexed 16 colors", ImageColorMode.INDEXED_4BIT)
        self.addItem("ARGB 1+5+5+5 bits", ImageColorMode.A1RGB15)
        self.addItem("RGB 5+5+5 bits", ImageColorMode.RGB15)
        self.setCurrentIndex(0)

    def selectedValue(self) -> ImageColorMode | None:
        index = self.currentIndex()
        if index == -1:
            return None
        return self.itemData(index)

    def selectValue(self, colorMode: ImageColorMode | None):
        if colorMode is None:
            self.setCurrentIndex(-1)
            return
        for index in range(self.count()):
            if  self.itemData(index) == colorMode:
                self.setCurrentIndex(index)
                return
        self.setCurrentIndex(-1)
