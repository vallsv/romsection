import binascii
from PyQt5 import Qt

from ..gba_file import DataType


class GbaRomHeaderView(Qt.QWidget):
    def __init__(self, parent: Qt.QWidget):
        Qt.QWidget.__init__(self, parent=parent)
        layout = Qt.QGridLayout(self)
        self._table = Qt.QTableWidget(self)
        self._table.setColumnCount(2)
        self._table.setRowCount(12)
        self._table.setHorizontalHeaderLabels(["Title", "Value"])
        self._table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table)

    def _setRow(self, row: int, header: str, item: Qt.QTableWidgetItem):
        headerItem = Qt.QTableWidgetItem()
        headerItem.setText(header)
        self._table.setItem(row, 0, headerItem)
        self._table.setItem(row, 1, item)

    def setMemory(self, memory: bytes):
        self._table.clear()
        if len(memory) != 192:
            raise ValueError("Memory size does not match GBA ROM header")

        # 0x00-0x03: 32 bit ARM opcode, usually B instruction
        item = Qt.QTableWidgetItem()
        opcode = int.from_bytes(memory[0:4], byteorder='little', signed=False)
        branch = (memory[0] & 0b00001010) != 0
        address = int.from_bytes(memory[1:4], byteorder='little', signed=False)
        inst = f'b 0x{address:06X}' if branch else f"0x{opcode:08X}"
        item.setText(inst)
        self._setRow(0, "ARM7TDMI Opcode", item)

        # 0x04-0x9F: Nintendo Logo data
        item = Qt.QTableWidgetItem()
        data = memory[0x04:0x9F]
        item.setText(f"{data.hex()}")
        self._setRow(1, "Nintendo Logo", item)

        # 0xA0-0xAB: Game Title
        item = Qt.QTableWidgetItem()
        data = memory[0xA0:0xAC].rstrip(b"\x00")
        item.setText(f"{data.decode()}")
        self._setRow(2, "Game Title", item)

        # 0xAC-0xAF: Game Code
        item = Qt.QTableWidgetItem()
        data = memory[0xAC:0xB0]
        item.setText(f"{data.decode()}")
        self._setRow(3, "Game Code", item)

        # 0xB0-0xB1: Maker Code
        item = Qt.QTableWidgetItem()
        data = memory[0xB0:0xB2]
        item.setText(f"{data.decode()}")
        self._setRow(4, "Maker Code", item)

        # 0xB2-0xB2: 0x96 Fixed
        item = Qt.QTableWidgetItem()
        value = int.from_bytes(memory[0xB2:0xB3], byteorder='little', signed=False)
        item.setText(f"0x{value:02X}")
        self._setRow(5, "Fixed value", item)

        # 0xB3-0xB3: Main Unit Code
        item = Qt.QTableWidgetItem()
        value = int.from_bytes(memory[0xB3:0xB4], byteorder='little', signed=False)
        item.setText(f"0x{value:02X}")
        self._setRow(6, "Main Unit Code", item)

        # 0xB4-0xB4: Device Type
        item = Qt.QTableWidgetItem()
        value = int.from_bytes(memory[0xB4:0xB5], byteorder='little', signed=False)
        item.setText(f"0x{value:02X}")
        self._setRow(7, "Device Type", item)

        # 0xB5-0xBB: Reserved Area
        item = Qt.QTableWidgetItem()
        data = memory[0xB5:0xBC]
        item.setText(f"{data.hex()}")
        self._setRow(8, "Reserved Area", item)

        # 0xBC-0xBC: Mask ROM Version
        item = Qt.QTableWidgetItem()
        value = int.from_bytes(memory[0xBC:0xBD], byteorder='little', signed=False)
        item.setText(f"0x{value:02X}")
        self._setRow(9, "Mask ROM Version", item)

        # 0xBD-0xBD: Compliment Check
        item = Qt.QTableWidgetItem()
        value = int.from_bytes(memory[0xBD:0xBE], byteorder='little', signed=False)
        item.setText(f"0x{value:02X}")
        self._setRow(10, "Compliment Check", item)

        # 0xBE-0xBF: Reserved Area
        item = Qt.QTableWidgetItem()
        data = memory[0xBE:0xC0]
        item.setText(f"{data.hex()}")
        self._setRow(11, "Reserved Area", item)
