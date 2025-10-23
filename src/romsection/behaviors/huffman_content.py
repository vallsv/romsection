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
from ._utils import splitMemoryMap


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

        if header[0] not in (0x24, 0x28):
            Qt.QMessageBox.information(
                context,
                "Error",
                "The selected byte is not a valid huffman"
            )
            return

        dataMem = MemoryMap(
            byte_codec=ByteCodec.HUFFMAN,
            byte_offset=address,
            data_type=DataType.UNKNOWN,
        )

        with qt_utils.exceptionAsMessageBox(context):
            byte_payload = rom.byte_payload(dataMem)
            dataMem.byte_payload = byte_payload

            memoryMapList = context.memoryMapList()
            with qt_utils.exceptionAsMessageBox(context):
                splitMemoryMap(memoryMapList, mem, dataMem)


class SearchHuffmanRunnable(search.SearchRunnable):
    def title(self) -> str:
        return "Searching for Huffman content..."

    def _checkStream(self, romOffset: int, stream: io.IOBase) -> bool:
        """
        Check the stream at the place it is.
        """
        start = stream.tell()
        size = huffman.dryrun(
            stream,
            min_length=16,
            max_length=1024*24,
            must_stop=self._mustStop
        )
        byteLength = stream.tell() - start
        mem = MemoryMap(
            byte_offset=romOffset,
            byte_length=byteLength,
            byte_payload=size,
            byte_codec=ByteCodec.HUFFMAN,
            data_type=DataType.UNKNOWN,
        )
        self._onFound(mem)
        return True


class SearchHuffmanContent(Behavior):
    """
    Search for huffman content.
    """
    def run(self) -> None:
        context = self.context()
        rom = context.rom()

        mem = context._memView.selectedMemoryMap()
        if mem is None:
            return

        assert rom is not None

        memoryMapQueue: queue.Queue[MemoryMap] = queue.Queue()

        Qt.QGuiApplication.setOverrideCursor(Qt.QCursor(Qt.Qt.WaitCursor))
        pool = Qt.QThreadPool.globalInstance()

        nbFound = 0
        memoryMapList = context.memoryMapList()

        def flushQueue():
            nonlocal nbFound
            try:
                newMem = memoryMapQueue.get(block=False)
                if nbFound == 0:
                    # At the first found we remove the parent memory
                    memoryMapList.removeObject(mem)
                nbFound += 1
                index = memoryMapList.indexAfterOffset(newMem.byte_offset)
                memoryMapList.insertObject(index, newMem)
            except queue.Empty:
                pass

        runnable = SearchHuffmanRunnable(
            rom=rom,
            memoryRange=(mem.byte_offset, mem.byte_end),
            queue=memoryMapQueue,
        )

        dialog = search.WaitForSearchDialog(context)
        dialog.registerRunnable(runnable)
        pool.start(runnable)

        timer = Qt.QTimer(context)
        timer.timeout.connect(flushQueue)
        timer.start(1000)

        dialog.exec()

        timer.stop()
        flushQueue()
        Qt.QGuiApplication.restoreOverrideCursor()

        Qt.QMessageBox.information(
            context,
            "Seatch result",
            f"{nbFound} potential huffman location was found"
        )
