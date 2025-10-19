import os
import io
import numpy
from PyQt5 import Qt

from .hexa_view import HexaView
from .sappy_instrument_bank import SappyInstrumentBank


class MusicBrowser(Qt.QWidget):
    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QWidget.__init__(self, parent=parent)
        self.setSizePolicy(Qt.QSizePolicy.Expanding, Qt.QSizePolicy.Expanding)
        self.__address: int = 0
        self.__len: int = 0
        self.__pos: int = 0
        self.__memory: io.IOBase = io.BytesIO(b"")

        self.setFocusPolicy(Qt.Qt.StrongFocus)

        layout = Qt.QVBoxLayout(self)
        self.setLayout(layout)

        self.__toolbar = Qt.QToolBar(self)
        self.__addressLabel = Qt.QLabel(self)
        self.__instrument = SappyInstrumentBank(self)
        self.__statusbar = Qt.QStatusBar(self)

        self.__hexa = HexaView(self)
        self.__hexa.setVisible(False)

        self.__showHexa = Qt.QAction(self)
        self.__showHexa.setIcon(Qt.QIcon("icons:hexa.png"))
        self.__showHexa.setCheckable(True)
        self.__showHexa.setText("Hex viewer")
        self.__showHexa.setToolTip("Show hexa viewer")
        self.__showHexa.toggled.connect(self.__hexa.setVisible)
        self.__showHexa.setChecked(not self.__hexa.isHidden())
        self.__toolbar.addAction(self.__showHexa)

        self.__toolbar.addSeparator()

        prevInst = Qt.QPushButton(self)
        prevInst.clicked.connect(self.moveToPreviousPage)
        prevInst.setText("<")
        self.__toolbar.addWidget(prevInst)

        nextInst = Qt.QPushButton(self)
        nextInst.clicked.connect(self.moveToNextPage)
        nextInst.setText(">")
        self.__toolbar.addWidget(nextInst)

        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(self.__toolbar)
        layout.addWidget(self.__addressLabel)
        layout.addWidget(self.__instrument)
        layout.addWidget(self.__hexa)
        layout.addWidget(self.__statusbar)
        layout.setStretchFactor(self.__instrument, 1)
        layout.setStretchFactor(self.__hexa, 1)

        self.__hexa.selectionModel().selectionChanged.connect(self.__selectionChanged)

    def __selectionChanged(self):
        offset = self.__hexa.selectedAddress()
        if offset is None:
            return
        self.__pos = min(max(offset - self.__address, 0), self.__len)
        self.__update()

    def keyPressEvent(self, event: Qt.QKeyEvent):
        if event.key() == Qt.Qt.Key_Left:
            self.moveToPreviousByte()
        elif event.key() == Qt.Qt.Key_Right:
            self.moveToNextByte()
        elif event.key() == Qt.Qt.Key_PageUp:
            self.moveToPreviousPage()
        elif event.key() == Qt.Qt.Key_PageDown:
            self.moveToNextPage()

    def position(self, pos: int):
        self.__pos = pos
        self.__hexa.setPosition(pos)

    def setPosition(self, pos: int):
        self.__pos = pos
        self.__hexa.setPosition(pos)
        self.__hexa.selectAddress(self.__address + pos)
        self.__update()

    def moveToPreviousByte(self):
        pos = self.__pos - 1
        pos = max(pos, 0)
        self.setPosition(pos)

    def moveToNextByte(self):
        pos = self.__pos + 1
        pos = min(pos, self.__len)
        self.setPosition(pos)

    def moveToPreviousPage(self):
        pos = self.__pos - 12
        pos = max(pos, 0)
        self.setPosition(pos)

    def moveToNextPage(self):
        pos = self.__pos + 12
        pos = min(pos, self.__len)
        self.setPosition(pos)

    def memory(self) -> io.IOBase:
        return self.__memory

    def address(self) -> int:
        return self.__address

    def setMemory(self, memory: io.IOBase, address: int = 0):
        if self.__memory == memory:
            return
        self.__memory = memory
        self.__address = address

        self.__memory.seek(0, os.SEEK_END)
        self.__len = self.__memory.tell()
        self.__memory.seek(0, os.SEEK_SET)
        self.__pos = 0

        self.__hexa.setMemory(memory, address=address)
        self.__update()

    def __update(self):
        self.__addressLabel.setText(f"{self.__address + self.__pos:08X}h")
        f = self.__memory
        f.seek(self.__pos, os.SEEK_SET)
        data = f.read(12)
        self.__instrument.setData(data)
