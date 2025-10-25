import io
import queue
from PyQt5 import Qt

from ..model import MemoryMap, ByteCodec, DataType
from . import search
from .behavior import Behavior
from ..parsers import lz77
from ._utils import splitMemoryMap
from .. import qt_utils
from .common import BehaviorAtRomOffset


class SplitLZ77Content(BehaviorAtRomOffset):

    def headerSize(self):
        return 1

    def isValidHeader(self, data: bytes):
        return data[0] == 0x10

    def createAction(self, parent: Qt.QObject) -> Qt.QAction:
        action = Qt.QAction(parent)
        action.setText("Extract LZ77 content")
        action.setIcon(Qt.QIcon("icons:lz77.png"))
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

        if header[0] != 0x10:
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Error",
                "The selected byte is not a valid LZ77 header"
            )
            return

        byte_codec = ByteCodec.LZ77
        with qt_utils.exceptionAsMessageBox(context.mainWidget()):
            byte_length, byte_payload = rom.check_codec(address, byte_codec)
            dataMem = MemoryMap(
                byte_codec=byte_codec,
                byte_offset=address,
                byte_length=byte_length,
                byte_payload=byte_payload,
                data_type=DataType.UNKNOWN,
            )

            memoryMapList = context.memoryMapList()
            splitMemoryMap(memoryMapList, mem, dataMem)


class SearchLZ77Content(search.SearchContentBehavior):
    """
    Search for LZ77 content.
    """

    def _checkStream(self, runner: search.SearchRunnable, romOffset: int, stream: io.IOBase) -> bool:
        """
        Check the stream at the place it is.

        This is executed inside another thread.
        """
        start = stream.tell()
        size = lz77.dryrun(
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
            byte_codec=ByteCodec.LZ77,
            data_type=DataType.UNKNOWN,
        )
        runner._onFound(mem)
        return True


class SearchSimilarLZ77Content(BehaviorAtRomOffset):

    def headerSize(self):
        return 1

    def isValidHeader(self, data: bytes):
        return data[0] == 0x10

    def createAction(self, parent: Qt.QObject) -> Qt.QAction:
        action = Qt.QAction(parent)
        action.setText("Search LZ77 content of the same size")
        action.setIcon(Qt.QIcon("icons:lz77.png"))
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

        if header[0] != 0x10:
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Error",
                "The selected byte is not a valid LZ77"
            )
            return

        size = int.from_bytes(header[1:], byteorder="little", signed=False)

        subBehavior = SearchLZ77Content()
        subBehavior.setContext(context)
        subBehavior.setInsertionMode(search.InsertionMode.SPLIT)
        subBehavior.setDataLengthRange(size, size)
        subBehavior.run()
