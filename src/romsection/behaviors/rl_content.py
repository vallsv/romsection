import os
import io
import struct
import queue
import typing
from PyQt5 import Qt

from ..gba_file import GBAFile
from .behavior import Behavior
from ..format_utils import format_address
from ..model import MemoryMap, ByteCodec, DataType
from ..parsers import rl
from .. import qt_utils
from . import search
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

        mem = context.currentMemoryMap()
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
                context.mainWidget(),
                "Error",
                "The selected byte is not a valid run-length header"
            )
            return

        dataMem = MemoryMap(
            byte_codec=ByteCodec.RL,
            byte_offset=address,
            data_type=DataType.UNKNOWN,
        )

        with qt_utils.exceptionAsMessageBox(context.mainWidget()):
            byte_payload = rom.byte_payload(dataMem)
            dataMem.byte_payload = byte_payload

            memoryMapList = context.memoryMapList()
            splitMemoryMap(memoryMapList, mem, dataMem)


class SearchRlContent(search.SearchContentBehavior):
    """
    Search for run-length content.
    """

    def _checkStream(self, runner: search.SearchRunnable, romOffset: int, stream: io.IOBase) -> bool:
        """
        Check the stream at the place it is.

        This is executed inside another thread.
        """
        start = stream.tell()
        size = rl.dryrun(
            stream,
            min_length=self.minDataLength(),
            max_length=self.maxDataLength(),
            must_stop=runner._mustStop
        )
        byteLength = stream.tell() - start
        mem = MemoryMap(
            byte_offset=romOffset,
            byte_length=byteLength,
            byte_payload=size,
            byte_codec=ByteCodec.RL,
            data_type=DataType.UNKNOWN,
        )
        runner._onFound(mem)
        return True


class SearchSimilarRlContent(BehaviorAtRomOffset):

    def headerSize(self):
        return 1

    def isValidHeader(self, data: bytes):
        return data[0] == 0x30

    def createAction(self, parent: Qt.QObject) -> Qt.QAction:
        action = Qt.QAction(parent)
        action.setText("Search run-length content of the same size")
        action.setIcon(Qt.QIcon("icons:rl.png"))
        action.triggered.connect(self.run)
        return action

    def run(self):
        context = self.context()
        rom = context.rom()

        mem = context.currentMemoryMap()
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
                context.mainWidget(),
                "Error",
                "The selected byte is not a valid run-length"
            )
            return

        size = int.from_bytes(header[1:], byteorder="little", signed=False)

        subBehavior = SearchRlContent()
        subBehavior.setContext(context)
        subBehavior.setInsertionMode(search.InsertionMode.SPLIT)
        subBehavior.setDataLengthRange(size, size)
        subBehavior.run()
