from PyQt5 import Qt

from ..gba_file import ByteCodec


class ByteCodecList(Qt.QListWidget):

    valueChanged = Qt.pyqtSignal(object)

    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QListWidget.__init__(self, parent)
        self.setUniformItemSizes(True)
        self.setVerticalScrollBarPolicy(Qt.Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(Qt.QSizePolicy.Expanding, Qt.QSizePolicy.Maximum)
        self.setSizeAdjustPolicy(Qt.QListWidget.AdjustToContents)
        self.setResizeMode(Qt.QListView.Fixed)

        item = Qt.QListWidgetItem()
        item.setText(f"Raw")
        item.setData(Qt.Qt.UserRole, ByteCodec.RAW)
        item.setIcon(Qt.QIcon("icons:empty.png"))
        self.addItem(item)

        item = Qt.QListWidgetItem()
        item.setText(f"LZ77")
        item.setData(Qt.Qt.UserRole, ByteCodec.LZ77)
        item.setIcon(Qt.QIcon("icons:lz77.png"))
        self.addItem(item)

        item = Qt.QListWidgetItem()
        item.setText(f"Huffman")
        item.setData(Qt.Qt.UserRole, ByteCodec.HUFFMAN)
        item.setIcon(Qt.QIcon("icons:huffman.png"))
        self.addItem(item)

        item = Qt.QListWidgetItem()
        item.setText(f"Run-lenght")
        item.setData(Qt.Qt.UserRole, ByteCodec.RL)
        item.setIcon(Qt.QIcon("icons:rl.png"))
        self.addItem(item)

        item = Qt.QListWidgetItem()
        item.setText(f"Huffman over LZ77")
        item.setData(Qt.Qt.UserRole, ByteCodec.HUFFMAN_OVER_LZ77)
        item.setIcon(Qt.QIcon("icons:huffman_lz77.png"))
        self.addItem(item)

        rect = self.visualItemRect(item)
        self.setMaximumHeight(rect.height() * self.count() + 4)

        self.itemSelectionChanged.connect(self._onItemSelectionChanged)

    def _onItemSelectionChanged(self):
        self.valueChanged.emit(self.selectedValue())

    def selectedValue(self) -> ByteCodec | None:
        items = self.selectedItems()
        if len(items) != 1:
            return None
        value = items[0].data(Qt.Qt.UserRole)
        return value

    def _findItemFromValue(self, value: ByteCodec | None) -> Qt.QListWidgetItem | None:
        if value is None:
            return None
        for i in range(self.count()):
            item = self.item(i)
            if item.data(Qt.Qt.UserRole) == value:
                return item
        return None

    def selectValue(self, value: ByteCodec | None):
        item = self._findItemFromValue(value)
        if item is not None:
            i = self.row(item)
            self.setCurrentRow(i)
        else:
            self.setCurrentRow(-1)
