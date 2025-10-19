from PyQt5 import Qt

from .combo_box import ComboBox
from ..gba_file import MemoryMap


class PaletteComboBox(ComboBox):

    valueChanged = Qt.pyqtSignal(object)

    def __init__(self, parent: Qt.QWidget | None):
        ComboBox.__init__(self, parent)
        self.currentIndexChanged.connect(self._onCurrentIndexChanged)

    def _onCurrentIndexChanged(self):
        self.valueChanged.emit(self.selectedValue())

    def selectedValue(self) -> MemoryMap | None:
        row = self.currentIndex()
        if row == -1:
            return None
        model = self.model()
        index = model.index(row, 0)
        return model.object(index)

    def selectValue(self, mem: MemoryMap | None):
        if mem is None:
            self.setCurrentIndex(-1)
        else:
            model = self.model()
            index = model.objectIndex(mem)
            if not index.isValid():
                self.setCurrentIndex(-1)
            else:
                row = index.row()
                self.setCurrentIndex(row)
