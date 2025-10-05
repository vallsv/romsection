from PyQt5 import Qt

from ..model import SampleCodec


class SampleCodecList(Qt.QListWidget):

    valueChanged = Qt.pyqtSignal(object)

    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QListWidget.__init__(self, parent)
        self.setUniformItemSizes(True)
        self.setVerticalScrollBarPolicy(Qt.Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(Qt.QSizePolicy.Expanding, Qt.QSizePolicy.Maximum)
        self.setSizeAdjustPolicy(Qt.QListWidget.AdjustToContents)

        item = Qt.QListWidgetItem()
        item.setText(f"Raw int8")
        item.setData(Qt.Qt.UserRole, SampleCodec.RAW_INT8)
        self.addItem(item)

        item = Qt.QListWidgetItem()
        item.setText(f"Sappy")
        item.setToolTip(f"12 bytes header including size + int8 sample")
        item.setData(Qt.Qt.UserRole, SampleCodec.SAPPY)
        self.addItem(item)

        rect = self.visualItemRect(item)
        self.setMinimumSize(150, -1)
        self.setMaximumHeight(rect.height() * self.count() + 4)

        self.itemSelectionChanged.connect(self._onChanged)

    def _onChanged(self):
        value = self.selectedValue()
        self.valueChanged.emit(value)

    def selectedValue(self) -> SampleCodec | None:
        items = self.selectedItems()
        if len(items) != 1:
            return None
        colorMode = items[0].data(Qt.Qt.UserRole)
        return colorMode

    def _findItemFromValue(self, value: SampleCodec | None) -> Qt.QListWidgetItem | None:
        if value is None:
            return None
        for i in range(self.count()):
            item = self.item(i)
            if item.data(Qt.Qt.UserRole) == value:
                return item
        return None

    def selectValue(self, value: SampleCodec | None):
        item = self._findItemFromValue(value)
        if item is not None:
            i = self.row(item)
            self.setCurrentRow(i)
        else:
            self.setCurrentRow(-1)
