from PyQt5 import Qt

from .combo_box import ComboBox
from ..gba_file import MemoryMap


class PaletteComboBox(ComboBox):
    def selectedMemoryMap(self) -> MemoryMap | None:
        row = self.currentIndex()
        if row == -1:
            return None
        model = self.model()
        index = model.index(row, 0)
        return model.object(index)

    def selectMemoryMap(self, mem: MemoryMap | None):
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
