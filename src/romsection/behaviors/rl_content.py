import os
import io
import struct
from PyQt5 import Qt

from ..gba_file import GBAFile
from .behavior import Behavior
from ..format_utils import format_address
from ..model import MemoryMap, ByteCodec, DataType
from ..parsers import rl
from .. import qt_utils
from ._utils import splitMemoryMap
from .common import BehaviorAtRomOffset


class SplitRlContent(BehaviorAtRomOffset):

    def headerSize(self):
        return 1

    def isValidHeader(self, data: bytes):
        return data[0] == 0x30

    def createAction(self, parent: Qt.QObject) -> Qt.QAction:
        action = Qt.QAction(parent)
        action.setText("Extract run-length content")
        action.setIcon(Qt.QIcon("icons:rl.png"))
        action.triggered.connect(self.run)
        return action

    def run(self):
        context = self.context()
        rom = context.rom()

        mem = context._memView.selectedMemoryMap()
        if mem is None:
            return

        if mem.byte_codec not in (None, ByteCodec.RAW):
            return

        address = self.offset()
        if address is None:
            return

        headerMem = MemoryMap(
            byte_offset=address,
            byte_length=4,
            data_type=DataType.UNKNOWN,
        )
        header = rom.extract_data(headerMem)

        if header[0] != 0x30:
            Qt.QMessageBox.information(
                context,
                "Error",
                "The selected byte is not a valid run-length header"
            )
            return

        dataMem = MemoryMap(
            byte_codec=ByteCodec.RL,
            byte_offset=address,
            data_type=DataType.UNKNOWN,
        )

        with qt_utils.exceptionAsMessageBox(context):
            byte_payload = rom.byte_payload(dataMem)
            dataMem.byte_payload = byte_payload

            memoryMapList = context.memoryMapList()
            with qt_utils.exceptionAsMessageBox(context):
                splitMemoryMap(memoryMapList, mem, dataMem)
