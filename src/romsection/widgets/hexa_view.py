from __future__ import annotations
import io
import lru
from PyQt5 import Qt


class HexaTableModel(Qt.QAbstractTableModel):
    """Table of hexadecimal rendering of byteq data.

    Bytes are displayed one by one as a hexadecimal viewer.

    The 16th first columns display bytes as hexadecimal, the last column
    displays the same data as ASCII.
    """

    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QAbstractTableModel.__init__(self, parent)
        self.__data: bytes | None = None
        self.__address: int = 0
        self.__start: int = 0
        self.__length: int = 0
        self.__padding: int = 0
        self.__font = Qt.QFontDatabase.systemFont(Qt.QFontDatabase.FixedFont)
        self.__palette = Qt.QPalette()
        self.__ascii: lru.LRU[int, str] = lru.LRU(256)
        self.__hilight = Qt.QColor("#fcaf3e")

    def rowCount(self, parent_idx=None):
        """Returns number of rows to be displayed in table"""
        if self.__data is None or self.__length == 0:
            return 0
        return ((self.__length - 1) >> 4) + 1

    def columnCount(self, parent_idx=None):
        """Returns number of columns to be displayed in table"""
        return 0x10 + 1

    def _getAscii(self, row: int) -> str:
        if self.__data is None:
            return ""

        ascii = self.__ascii.get(row, None)
        if ascii is not None:
            return ascii

        start = row << 4
        text = ""
        for i in range(0x10):
            pos = start + i
            if pos >= self.__length:
                break
            if pos < self.__padding:
                text += " "
                continue
            value = self.__data[pos - self.__padding]
            if value > 0x20 and value < 0x7F:
                text += chr(value)
            else:
                text += "."

        self.__ascii[row] = text
        return text

    def data(self, index, role=Qt.Qt.DisplayRole):
        """QAbstractTableModel method to access data values
        in the format ready to be displayed"""
        if not index.isValid():
            return None

        if self.__data is None:
            return None

        row = index.row()
        column = index.column()

        if role == Qt.Qt.UserRole:
            if column == 0x10:
                return None
            pos = (row << 4) + column
            if pos < self.__padding:
                return None
            if pos < self.__length:
                return self.__start + pos
            else:
                return None

        elif role == Qt.Qt.ForegroundRole:
            if column == 0x10:
                return Qt.QColorConstants.Black

        elif role == Qt.Qt.DisplayRole:
            if column == 0x10:
                ascii = self._getAscii(row)
                return ascii
            else:
                pos = (row << 4) + column
                if pos < self.__padding:
                    return ""
                if pos < self.__length:
                    value = self.__data[pos - self.__padding]
                    return f"{value:02X}"
                else:
                    return ""
        elif role == Qt.Qt.FontRole:
            return self.__font

        elif role == Qt.Qt.BackgroundRole:
            if column == 0x10:
                return self.__palette.color(Qt.QPalette.Disabled, Qt.QPalette.Window)
            pos = (row << 4) + column
            if pos < self.__padding or pos >= self.__length:
                return self.__palette.color(Qt.QPalette.Disabled, Qt.QPalette.ButtonText)

            if pos % 4 == 0:
                value = self.__data[pos - self.__padding]
                if value in (0x10, 0x24, 0x28, 0x30):
                    return self.__hilight

            return None

        elif role == Qt.Qt.TextAlignmentRole:
            if column == 0x10:
                return Qt.Qt.AlignLeft | Qt.Qt.AlignVCenter
            else:
                return Qt.Qt.AlignCenter

        return None

    def headerData(self, section, orientation, role=Qt.Qt.DisplayRole):
        """Returns the 0-based row or column index, for display in the
        horizontal and vertical headers"""
        if section == -1:
            # PyQt4 send -1 when there is columns but no rows
            return None

        if role == Qt.Qt.DisplayRole:
            if orientation == Qt.Qt.Vertical:
                address = self.__start + (section << 4)
                return f"{address:08X}"
            if orientation == Qt.Qt.Horizontal:
                if section == 0x10:
                    return "ASCII"
                else:
                    return f"{section:02X}"
        elif role == Qt.Qt.FontRole:
            return self.__font
        elif role == Qt.Qt.TextAlignmentRole:
            if orientation == Qt.Qt.Vertical:
                return Qt.Qt.AlignRight | Qt.Qt.AlignVCenter
            if orientation == Qt.Qt.Horizontal:
                if section == 0x10:
                    return Qt.Qt.AlignLeft | Qt.Qt.AlignVCenter
                else:
                    return Qt.Qt.AlignCenter
        return None

    def flags(self, index: Qt.QModelIndex):
        """QAbstractTableModel method to inform the view whether data
        is editable or not.
        """
        column = index.column()
        if column == 0x10:
            return Qt.Qt.NoItemFlags
        row = index.row()
        pos = (row << 4) + column
        if pos < self.__padding or pos >= self.__length:
            return Qt.Qt.NoItemFlags
        return Qt.QAbstractTableModel.flags(self, index)

    def setBytes(self, data: bytes | None, address: int = 0):
        """Set the data array."""
        self.beginResetModel()
        self.__data = data
        self.__address = address
        self.__start = (address >> 4) << 4
        self.__padding = self.__address - self.__start
        if data is not None:
            self.__length = self.__padding + len(data)
        else:
            self.__length = 0
        self.__ascii.clear()
        self.endResetModel()

    def indexFromAddress(self, address: int) -> Qt.QModelIndex:
        if address < self.__address or address >= self.__address + self.__length:
            return Qt.QModelIndex()
        row, col = divmod(address - self.__start, 16)
        return self.index(row, col)

    def bytes(self) -> bytes | None:
        """Returns the internal data."""
        return self.__data


class HexaView(Qt.QTableView):
    """TableView using HexaTableModel as default model.

    It customs the column size to provide a better layout.
    """

    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QTableView.__init__(self, parent)
        model = HexaTableModel(self)
        self.setModel(model)

    def setPosition(self, pos: int):
        line = pos // 16
        model = self.model()
        index = model.index(line, 0)
        self.scrollTo(index)

    def setMemory(self, memory: io.IOBase | None, address: int=0):
        """
        Set the binary data.
        """
        if memory is not None:
            # FIXME: Really handle `io`, actually we only support `BytesIO`.
            data = memory.getvalue()
        else:
            data = b""
        self.model().setBytes(data, address=address)
        self.__fixHeader()

    def setData(self, data: bytes | None, address: int=0):
        """Set the binary data.

        FIXME: Deprecated
        """
        self.model().setBytes(data, address=address)
        self.__fixHeader()

    def __fixHeader(self):
        """Update the view according to the state of the auto-resize"""
        header = self.horizontalHeader()
        header.setDefaultSectionSize(30)
        header.setStretchLastSection(True)
        for i in range(0x10):
            header.setSectionResizeMode(i, Qt.QHeaderView.Fixed)
        header.setSectionResizeMode(0x10, Qt.QHeaderView.Stretch)

    def selectedOffset(self) -> int | None:
        """FIXME: Deprecated"""
        return self.selectedAddress()

    def selectedAddress(self) -> int | None:
        """Return the selected address"""
        model = self.selectionModel()
        items = model.selectedIndexes()
        if len(items) != 1:
            return None
        return items[0].data(Qt.Qt.UserRole)

    def selectAddress(self, address: int | None):
        """Set the selected address"""
        selectionModel = self.selectionModel()
        if address is None:
            selectionModel.clearSelection()
            return
        model = self.model()
        index = model.indexFromAddress(address)
        selectionModel.select(index, Qt.QItemSelectionModel.ClearAndSelect)

    def setAddressSelection(self, selection: tuple[int, int] | None):
        # FIXME: Implement a full selection
        if selection is None:
            self.selectAddress(None)
        else:
            size = selection[1] - selection[0]
            if size == 1:
                address = selection[0]
                self.selectAddress(address)
                model = self.model()
                index = model.indexFromAddress(address)
                self.scrollTo(index)
            else:
                self.selectAddress(None)
