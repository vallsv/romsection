import typing
import queue
import io
import os
import enum
from collections.abc import Callable

from PyQt5 import Qt

from ..gba_file import GBAFile
from ..model import MemoryMap, ByteCodec, DataType
from .behavior import Behavior
from ..commands.extract_memorymap import ExtractMemoryMapCommand


class Signals(Qt.QObject):
    started = Qt.pyqtSignal()
    succeeded = Qt.pyqtSignal()
    cancelled = Qt.pyqtSignal()
    finished = Qt.pyqtSignal()
    progress = Qt.pyqtSignal()


class SearchRunnable(Qt.QRunnable):
    def __init__(
        self,
        rom: GBAFile,
        memoryRange: tuple[int, int],
        queue: queue.Queue[MemoryMap],
        checkStream: Callable[["SearchRunnable", int, io.IOBase], bool] | None = None
    ):
        Qt.QRunnable.__init__(self)
        self._signals = Signals()
        self._rom = rom
        self._queue = queue
        self._memoryRange = memoryRange
        self._mustStop: typing.Callable[[], bool] | None = None
        self._skipValidBlocks = False
        """
        If True, if a data is found, do not search any more other content
        inside this block. Else, each offset is checked individually.
        """
        self.__checkStream = checkStream

    @property
    def signals(self) -> Signals:
        return self._signals

    def setCancelCallback(self, mustStop: typing.Callable[[], bool] | None = None):
        self._mustStop = mustStop

    def _onFound(self, mem: MemoryMap):
        self._queue.put(mem)

    def _onProgress(self, offset: int):
        self._signals.progress.emit()

    def byteLength(self) -> int:
        return self._memoryRange[1] - self._memoryRange[0]

    def title(self) -> str:
        return "Searching for..."

    def _checkStream(self, romOffset: int, stream: io.IOBase) -> bool:
        """
        Check for the content at the steam location.

        Return true if something start at this place.
        """
        return False

    def run(self):
        self.signals.started.emit()
        try:
            offsetFrom = self._memoryRange[0]
            offsetTo = self._memoryRange[1]

            rawMem = MemoryMap(
                byte_offset=offsetFrom,
                byte_length=offsetTo - offsetFrom,
            )
            data = self._rom.extract_raw(rawMem)
            stream = io.BytesIO(data)

            romOffset = offsetFrom
            offset = 0
            while romOffset + offset < offsetTo:
                if self._mustStop():
                    raise StopIteration

                try:
                    if self.__checkStream is not None:
                        found = self.__checkStream(self, romOffset + offset, stream)
                    else:
                        found = self._checkStream(romOffset + offset, stream)
                except ValueError:
                    found = False
                except RuntimeError:
                    found = False

                if not self._skipValidBlocks:
                    offset += 1
                    stream.seek(offset, os.SEEK_SET)
                else:
                    if not found:
                        offset += 1
                        stream.seek(offset, os.SEEK_SET)
                    else:
                        offset = stream.tell()

                if self._onProgress is not None:
                    self._onProgress(offset)

        except StopIteration:
            self._signals.cancelled.emit()
        else:
            self._signals.succeeded.emit()
        finally:
            self._signals.finished.emit()


class WaitForSearchDialog(Qt.QDialog):
    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QDialog.__init__(self, parent=parent)
        self.setWindowTitle("Searching for...")

        self._nbJobs = 0
        self._startedJobs = 0
        self._succeededJobs = 0
        self._finishedJobs = 0
        self._cancelled = False
        self._bytesToCheck = 0
        self._bytesChecked = 0

        widget = Qt.QWidget()
        widget.setLayout(Qt.QGridLayout())

        self._progressBar = Qt.QProgressBar(self)

        self._cancel = Qt.QPushButton(self)
        self._cancel.setText("Cancel")
        self._cancel.clicked.connect(self._requestCancel)

        buttonLayout = Qt.QHBoxLayout()
        buttonLayout.addStretch(0)
        buttonLayout.addWidget(self._cancel)
        buttonLayout.addStretch(0)

        layout = Qt.QVBoxLayout(self)
        layout.addWidget(self._progressBar)
        layout.addLayout(buttonLayout)

    def _cancelRequested(self) -> bool:
        return self._cancelled

    def registerRunnable(self, runnable: SearchRunnable):
        self.setWindowTitle(runnable.title())
        self._bytesToCheck += runnable.byteLength()
        runnable.signals.started.connect(self._onStarted)
        runnable.signals.finished.connect(self._onFinished)
        runnable.setCancelCallback(self._cancelRequested)
        runnable.signals.progress.connect(self._onProgress)
        self._nbJobs += 1
        self._progressBar.setRange(0, self._bytesToCheck)

    def _requestCancel(self):
        self._cancelled = True

    def _onProgress(self):
        self._bytesChecked += 1
        self._updateProgress()

    def _onStarted(self):
        self._startedJobs += 1

    def _onSucceeded(self):
        self._succeededJobs += 1

    def _onFinished(self):
        self._finishedJobs += 1
        if self._finishedJobs == self._nbJobs:
            if not self._cancelled:
                self.accept()
            else:
                self.reject()

    def _updateProgress(self):
        self._progressBar.setValue(self._bytesChecked)


class InsertionMode(enum.Enum):
    INSERT = enum.auto()
    """Remove the initial memory map and create new onces"""

    SPLIT = enum.auto()
    """Split recursivelly the initial map"""

class SearchContentBehavior(Behavior):
    """
    Search for some content.
    """
    def __init__(self) -> None:
        Behavior.__init__(self)
        self.__minDataLength = 16
        self.__maxDataLength = 1024 * 24
        self.__insertionMode: InsertionMode = InsertionMode.INSERT

    def setDataLengthRange(self, minLength: int, maxLength: int):
        self.__minDataLength = minLength
        self.__maxDataLength = maxLength

    def minDataLength(self) -> int:
        return self.__minDataLength

    def maxDataLength(self) -> int:
        return self.__maxDataLength

    def setInsertionMode(self, mode: InsertionMode):
        self.__insertionMode = mode

    def _checkStream(self, runner: SearchRunnable, romOffset: int, stream: io.IOBase) -> bool:
        """
        Check the stream at the place it is.

        This is executed inside another thread.
        """
        raise NotImplementedError

    def run(self) -> None:
        context = self.context()
        rom = context.rom()

        mem = context.currentMemoryMap()
        if mem is None:
            return

        memoryMapQueue: queue.Queue[MemoryMap] = queue.Queue()

        Qt.QGuiApplication.setOverrideCursor(Qt.QCursor(Qt.Qt.WaitCursor))
        pool = Qt.QThreadPool.globalInstance()

        nbFound = 0
        memoryMapList = context.memoryMapList()
        notAdded: list[tuple[MemoryMap, str]] = []

        def flushQueue():
            nonlocal nbFound
            try:
                while newMem := memoryMapQueue.get(block=False):
                    if self.__insertionMode == InsertionMode.INSERT:
                        if nbFound == 0:
                            # At the first found we remove the parent memory
                            memoryMapList.removeObject(mem)
                        nbFound += 1
                        index = memoryMapList.indexAfterOffset(newMem.byte_offset)
                        memoryMapList.insertObject(index, newMem)
                    elif self.__insertionMode == InsertionMode.SPLIT:
                        nbFound += 1
                        mem = rom.memory_map_containing_offset(newMem.byte_offset)
                        if mem is None:
                            notAdded.add((newMem, "There is no parent memory"))
                            continue
                        if mem.byte_codec not in (None, ByteCodec.RAW):
                            notAdded.add((newMem, "Parent memory is not a raw data"))
                            continue
                        if mem.data_type != DataType.UNKNOWN:
                            notAdded.add((newMem, "Parent memory have a data type"))
                            continue
                        try:
                            # FIXME: Have to be merged with the previous one
                            command = ExtractMemoryMapCommand()
                            command.setCommand(mem, newMem)
                            context.pushCommand(command)
                        except RuntimeError as e:
                            notAdded.add((newMem, e.args[0]))
                    else:
                        raise RuntimeError(f"Unsupported {self.__insertionMode}")
            except queue.Empty:
                pass

        runnable = SearchRunnable(
            rom=rom,
            memoryRange=(mem.byte_offset, mem.byte_end),
            queue=memoryMapQueue,
            checkStream=self._checkStream,
        )
        if self.__insertionMode == InsertionMode.SPLIT:
            # No need to check intermediate values, it will not be inserted
            # in the end because another memorymap is already there
            runnable._skipValidBlocks = True

        dialog = WaitForSearchDialog(context.mainWidget())
        dialog.registerRunnable(runnable)
        pool.start(runnable)

        timer = Qt.QTimer(context.mainWidget())
        timer.timeout.connect(flushQueue)
        timer.start(200)

        dialog.exec()

        timer.stop()
        flushQueue()
        Qt.QGuiApplication.restoreOverrideCursor()

        msg = f"{nbFound} potential location was found."
        if len(notAdded) != 0:
            msg += f"{msg} {len(notAdded)} was not inserted for various reasons."

        Qt.QMessageBox.information(
            context.mainWidget(),
            "Seatch result",
            msg,
        )
