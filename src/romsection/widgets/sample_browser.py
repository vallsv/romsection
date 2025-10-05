import os
import io
import numpy
from PyQt5 import Qt

from .sample_browser_widget import SampleBrowserWidget
from .sample_codec_combo_box import SampleCodecComboBox
from .combo_box import ComboBox
from .hexa_view import HexaView


class SampleBrowser(Qt.QWidget):
    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QWidget.__init__(self, parent=parent)
        self.setSizePolicy(Qt.QSizePolicy.Expanding, Qt.QSizePolicy.Expanding)
        self.__address: int = 0

        self.setFocusPolicy(Qt.Qt.StrongFocus)

        layout = Qt.QVBoxLayout(self)
        self.setLayout(layout)

        self.__toolbar = Qt.QToolBar(self)
        self.__statusbar = Qt.QStatusBar(self)

        frame = Qt.QFrame(self)
        frame.setFrameShadow(Qt.QFrame.Sunken)
        frame.setFrameShape(Qt.QFrame.StyledPanel)

        waveView = SampleBrowserWidget(frame)
        self.__wave = waveView
        self.__scroll = Qt.QScrollBar(frame)
        self.__scroll.setTracking(True)
        self.__scroll.setOrientation(Qt.Qt.Horizontal)

        self.__hexa = HexaView(self)
        self.__hexa.setVisible(False)

        self.__showHexa = Qt.QAction(self)
        self.__showHexa.setIcon(Qt.QIcon("icons:hexa.png"))
        self.__showHexa.setCheckable(True)
        self.__showHexa.setText("Hex viewer")
        self.__showHexa.setToolTip("Show hexa viewer")
        self.__showHexa.toggled.connect(self.__hexa.setVisible)
        self.__showHexa.setChecked(not self.__hexa.isHidden())
        self.__toolbar.addAction(self.__showHexa)

        self.__toolbar.addSeparator()

        frameLayout = Qt.QVBoxLayout(frame)
        frame.setLayout(frameLayout)
        frameLayout.setSpacing(0)
        frameLayout.setContentsMargins(0, 0, 0, 0)
        frameLayout.addWidget(self.__wave)
        frameLayout.addWidget(self.__scroll)

        frameLayout.setStretchFactor(self.__wave, 1)

        self.__samplePerPixels = Qt.QSpinBox(self.__toolbar)
        self.__samplePerPixels.setRange(1, 128)
        self.__samplePerPixels.setValue(self.__wave.nbSamplePerPixels())
        self.__toolbar.addWidget(self.__samplePerPixels)

        self.__sampleCodec = SampleCodecComboBox(self.__toolbar)
        self.__toolbar.addWidget(self.__sampleCodec)

        self.__playButton = Qt.QPushButton(self.__toolbar)
        self.__playButton.clicked.connect(self._playback)
        self.__playButton.setToolTip("Playback visible data only")
        self.__playButton.setIcon(Qt.QIcon("icons:play.png"))
        self.__toolbar.addWidget(self.__playButton)

        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(self.__toolbar)
        layout.addWidget(frame)
        frameLayout.addWidget(self.__hexa)
        layout.addWidget(self.__statusbar)
        layout.setStretchFactor(frame, 1)

        self.__samplePerPixels.valueChanged.connect(waveView.setNbSamplePerPixels)
        self.__scroll.valueChanged.connect(self.setPosition)
        self.__sampleCodec.valueChanged.connect(waveView.setSampleCodec)
        self.__wave.playbackChanged.connect(self._onPlaybackChanged)

    def _playback(self):
        if self.__wave.isPlaying():
            self.__wave.stop()
        else:
            self.__wave.playVisible()

    def _onPlaybackChanged(self, playing: bool):
        if playing:
            self.__playButton.setIcon(Qt.QIcon("icons:stop.png"))
        else:
            self.__playButton.setIcon(Qt.QIcon("icons:play.png"))

    def __onSampleTypeChanged(self, index: int):
        size, signed = self.__sampleType.itemData(index)
        self.__wave.setSampleSize(size)
        self.__wave.setSampleSigned(signed)

    def keyPressEvent(self, event: Qt.QKeyEvent):
        if event.key() == Qt.Qt.Key_Left:
            self.moveToPreviousByte()
        elif event.key() == Qt.Qt.Key_Right:
            self.moveToNextByte()
        elif event.key() == Qt.Qt.Key_PageUp:
            self.moveToPreviousPage()
        elif event.key() == Qt.Qt.Key_PageDown:
            self.moveToNextPage()

    def setPosition(self, pos: int):
        self.__wave.setPosition(pos)
        self.__hexa.setPosition(pos)

    def moveToPreviousByte(self):
        pos = self.__wave.position() - 1
        pos = max(pos, 0)
        self.setPosition(pos)

    def moveToNextByte(self):
        pos = self.__wave.position() + 1
        pos = min(pos, self.__wave.memoryLength())
        self.setPosition(pos)

    def moveToPreviousPage(self):
        # FIXME: Have to be improved
        pos = self.__wave.position() - self.__wave.width()
        pos = max(pos, 0)
        self.setPosition(pos)

    def moveToNextPage(self):
        # FIXME: Have to be improved
        pos = self.__wave.position() + self.__wave.width()
        pos = min(pos, self.__wave.memoryLength())
        self.setPosition(pos)

    def memory(self) -> io.IOBase:
        return self.__wave.memory()

    def setMemory(self, memory: io.IOBase, address: int = 0):
        self.__address = address
        self.__wave.setMemory(memory)
        self.__hexa.setMemory(memory, address=address)
        self.__scroll.setValue(0)
        self.__scroll.setRange(0, self.__wave.memoryLength())

    def address(self) -> int:
        return self.__address
