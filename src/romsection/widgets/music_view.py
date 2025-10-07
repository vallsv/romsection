import os
import io
import numpy
from PyQt5 import Qt

from ..model import MemoryMap
from ..gba_file import GBAFile
from .hexa_view import HexaView
from .sappy_instrument_bank import SappyInstrumentBank
from .sappy_instrument_table import SappyInstrumentTable


class MusicView(Qt.QWidget):
    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QWidget.__init__(self, parent=parent)
        self.setSizePolicy(Qt.QSizePolicy.Expanding, Qt.QSizePolicy.Expanding)

        self.__memoryMap: MemoryMap | None = None
        self.__rom: GBAFile | None = None

        self.setFocusPolicy(Qt.Qt.StrongFocus)

        layout = Qt.QVBoxLayout(self)
        self.setLayout(layout)

        self.__toolbar = Qt.QToolBar(self)
        self.__instrument = SappyInstrumentBank(self)
        self.__statusbar = Qt.QStatusBar(self)

        self.__table = SappyInstrumentTable(self)

        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(self.__toolbar)
        layout.addWidget(self.__instrument)
        layout.addWidget(self.__table)
        layout.addWidget(self.__statusbar)
        layout.setStretchFactor(self.__table, 1)

        self.__table.selectionModel().selectionChanged.connect(self.__selectionChanged)

    def __selectionChanged(self):
        data = self.__table.selectedItemData()
        self.__instrument.setData(data)

    def memoryMap(self) -> MemoryMap | None:
        return self.__memoryMap

    def setMemoryMap(self, memoryMap: MemoryMap | None):
        self.__memoryMap = memoryMap
        self._updateData()

    def rom(self) -> GBAFile | None:
        return self.__rom

    def setRom(self, rom: GBAFile | None):
        self.__rom = rom
        self._updateData()

    def _updateData(self):
        rom = self.__rom
        mem = self.__memoryMap
        if rom is None or mem is None:
            self.__table.setMemory(io.BytesIO(b""))
            return

        array = rom.extract_data(mem)
        data = array.tobytes()

        self.__table.setMemory(io.BytesIO(data), address=mem.byte_offset)
        self.__instrument.setData(None)
