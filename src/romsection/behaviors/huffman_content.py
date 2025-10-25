import typing
import io
import os
import struct
import queue
from PyQt5 import Qt

from ..gba_file import GBAFile
from ..model import MemoryMap, ByteCodec, DataType
from . import search
from .behavior import Behavior
from ..parsers import huffman
from .common import BehaviorAtRomOffset
from .. import qt_utils
from ..commands.extract_memorymap import ExtractMemoryMapCommand


class SplitHuffmanContent(BehaviorAtRomOffset):

    def headerSize(self):
        return 1

    def isValidHeader(self, data: bytes):
        return data[0] in (0x24, 0x28)

    def createAction(self, parent: Qt.QObject) -> Qt.QAction:
        action = Qt.QAction(parent)
        action.setText("Extract huffman content")
        action.setIcon(Qt.QIcon("icons:huffman.png"))
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
        header = rom.extract_raw(headerMem)

        if header[0] not in (0x24, 0x28):
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Error",
                "The selected byte is not a valid huffman"
            )
            return

        byte_codec = ByteCodec.HUFFMAN
        with qt_utils.exceptionAsMessageBox(context.mainWidget()):
            byte_length, byte_payload = rom.check_codec(address, byte_codec)
            dataMem = MemoryMap(
                byte_codec=byte_codec,
                byte_offset=address,
                byte_length=byte_length,
                byte_payload=byte_payload,
                data_type=DataType.UNKNOWN,
            )
            command = ExtractMemoryMapCommand()
            command.setCommand(mem, dataMem)
            context.pushCommand(command)


class SearchHuffmanContent(search.SearchContentBehavior):
    """
    Search for huffman content.
    """

    def _checkStream(self, runner: search.SearchRunnable, romOffset: int, stream: io.IOBase) -> bool:
        """
        Check the stream at the place it is.

        This is executed inside another thread.
        """
        start = stream.tell()
        size = huffman.dryrun(
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
            byte_codec=ByteCodec.HUFFMAN,
            data_type=DataType.UNKNOWN,
        )
        runner._onFound(mem)
        return True


class SearchSimilarHuffmanContent(BehaviorAtRomOffset):

    def headerSize(self):
        return 1

    def isValidHeader(self, data: bytes):
        return data[0] in (0x24, 0x28)

    def createAction(self, parent: Qt.QObject) -> Qt.QAction:
        action = Qt.QAction(parent)
        action.setText("Search huffman content of the same size")
        action.setIcon(Qt.QIcon("icons:huffman.png"))
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
        header = rom.extract_raw(headerMem)

        if header[0] not in (0x24, 0x28):
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Error",
                "The selected byte is not a valid huffman"
            )
            return

        size = int.from_bytes(header[1:], byteorder="little", signed=False)

        subBehavior = SearchHuffmanContent()
        subBehavior.setContext(context)
        subBehavior.setInsertionMode(search.InsertionMode.SPLIT)
        subBehavior.setDataLengthRange(size, size)
        subBehavior.run()
