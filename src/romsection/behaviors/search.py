import typing
import queue
import io
import os
from PyQt5 import Qt

from ..gba_file import GBAFile
from ..model import MemoryMap


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
