import typing
import queue
from PyQt5 import Qt

from ..gba_file import GBAFile
from ..model import MemoryMap


class Signals(Qt.QObject):
    started = Qt.pyqtSignal()
    succeeded = Qt.pyqtSignal()
    cancelled = Qt.pyqtSignal()
    finished = Qt.pyqtSignal()


class SearchLZ77Runnable(Qt.QRunnable):
    def __init__(
        self,
        rom: GBAFile,
        memoryRange: tuple[int, int],
        queue: queue.Queue[MemoryMap],
    ):
        Qt.QRunnable.__init__(self)
        self.signals = Signals()
        self._rom = rom
        self._queue = queue
        self._memoryRange = memoryRange
        self._mustStop: typing.Callable[[], bool] | None = None

    def setCancelCallback(self, mustStop: typing.Callable[[], bool] | None = None):
        self._mustStop = mustStop

    def _onFound(self, mem: MemoryMap):
        self._queue.put(mem)

    def run(self):
        self.signals.started.emit()
        try:
            self._rom.search_for_lz77(
                offset_from=self._memoryRange[0],
                offset_to=self._memoryRange[1],
                must_stop=self._mustStop,
                on_found=self._onFound,
            )
        except StopIteration:
            self.signals.cancelled.emit()
        else:
            self.signals.succeeded.emit()
        finally:
            self.signals.finished.emit()


class WaitForSearchDialog(Qt.QDialog):
    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QDialog.__init__(self, parent=parent)
        self.setWindowTitle("Searching for LZ77...")

        self._nbJobs = 0
        self._startedJobs = 0
        self._succeededJobs = 0
        self._finishedJobs = 0
        self._cancelled = False

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

    def registerRunnable(self, runnable: SearchLZ77Runnable):
        runnable.signals.started.connect(self._onStarted)
        runnable.signals.finished.connect(self._onFinished)
        runnable.setCancelCallback(self._cancelRequested)
        self._nbJobs += 1
        self._progressBar.setRange(0, self._nbJobs * 2)

    def _requestCancel(self):
        self._cancelled = True

    def _onStarted(self):
        self._startedJobs += 1
        self._updateProgress()

    def _onSucceeded(self):
        self._succeededJobs += 1
        self._updateProgress()

    def _onFinished(self):
        self._finishedJobs += 1
        if self._finishedJobs == self._nbJobs:
            if not self._cancelled:
                self.accept()
            else:
                self.reject()

    def _updateProgress(self):
        self._progressBar.setValue(self._startedJobs + self._succeededJobs)
