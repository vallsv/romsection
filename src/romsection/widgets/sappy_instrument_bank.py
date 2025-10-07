import struct
from PyQt5 import Qt

from .. import sappy_utils


class SappyInstrumentBank(Qt.QWidget):

    def __init__(self, parent: Qt.QWidget | None):
        Qt.QWidget.__init__(self, parent=parent)
        self.__data: bytes | None = None
        self.__address = 0
        self.__text = Qt.QTextEdit(self)
        layout = Qt.QVBoxLayout(self)
        layout.addWidget(self.__text)

    def setData(self, data: bytes | None):
        self.__data = data
        self._update()

    def _getData(self) -> bytes | None:
        if self.__data is None:
            return None
        if len(self.__data) != 12:
            return None
        return self.__data

    def _update(self):
        data = self._getData()
        text = self._formatInstrument(data)
        self.__text.setText(text)

    def _formatInstrument(self, data: bytes | None) -> str:
        if data is None:
            return ""
        if data == sappy_utils.UNUSED_INSTRUMENT:
            return "Unused instrument"

        instType = data[0]
        if instType in (0x00, 0x08,  0x10, 0x20):
            return self._formatSample(data)
        if instType == (0x01, 0x02, 0x03, 0x04, 0x09, 0x0A, 0x0B, 0x0C):
            return self._formatPsg(data)
        if instType == 0x40:
            return self._formatKeySplit(data)
        if instType == 0x80:
            return self._formatEveryKeySplit(data)
        return self._formatUnsupported(data)

    def _formatSample(self, data: bytes) -> str:
        result = struct.unpack("<BBBBLBBBB", data)
        kindDesc = "Sample (GBA Direct Sound channel)"
        kind, key, unused, panning, sample, attack, decay, sustain, release = result
        romSample = sample - 0x8000000
        return f"""{kindDesc}:

kind    0x{kind:02X}: {kind}
key     0x{key:02X}: {key}
unused  0x{unused:02X}: {unused}
panning 0x{panning:02X}: {panning}
sample  0x{sample:08X}: {sample}     IN ROM: 0x{romSample:08X}: {romSample}
attack  0x{attack:02X}: {attack}
decay   0x{decay:02X}: {decay}
sustain 0x{sustain:02X}: {sustain}
release 0x{release:02X}: {release}
"""

    def _formatPsg(self, data: bytes) -> str:
        kindDesc = "PSG instrument / sub-instrument"
        return f"{kindDesc}:\n{str(data)}"

    def _formatKeySplit(self, data: bytes) -> str:
        kindDesc = "Key-Split instruments"
        return f"{kindDesc}:\n{str(data)}"

    def _formatEveryKeySplit(self, data: bytes) -> str:
        kindDesc = "Every Key Split (percussion) instrument"
        return f"{kindDesc}:\n{str(data)}"

    def _formatUnsupported(self, data: bytes) -> str:
        return f"Unsupported instrument:\n{str(data)}"
