import os
import io
import numpy
from PyQt5 import Qt

from .sound_wave_view import SoundWaveView
from .sample_codec_combo_box import SampleCodecComboBox
from .combo_box import ComboBox
from .hexa_view import HexaView


class SoundBrowser(Qt.QWidget):
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

        waveView = SoundWaveView(frame)
        self.__widget = waveView
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
        frameLayout.addWidget(self.__widget)
        frameLayout.addWidget(self.__scroll)

        frameLayout.setStretchFactor(self.__widget, 1)

        self.__samplePerPixels = Qt.QSpinBox(self.__toolbar)
        self.__samplePerPixels.setRange(1, 128)
        self.__samplePerPixels.setValue(self.__widget.nbSamplePerPixels())
        self.__toolbar.addWidget(self.__samplePerPixels)

        self.__sampleCodec = SampleCodecComboBox(self.__toolbar)
        self.__toolbar.addWidget(self.__sampleCodec)

        playButton = Qt.QPushButton(self.__toolbar)
        playButton.clicked.connect(waveView.playSelection)
        self.__toolbar.addWidget(playButton)

        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(self.__toolbar)
        layout.addWidget(frame)
        frameLayout.addWidget(self.__hexa)
        layout.addWidget(self.__statusbar)
        layout.setStretchFactor(frame, 1)

        self.__samplePerPixels.valueChanged.connect(waveView.setNbSamplePerPixels)
        self.__scroll.valueChanged.connect(self.setPosition)
        self.__sampleCodec.valueChanged.connect(waveView.setSampleCodec)

    def __onSampleTypeChanged(self, index: int):
        size, signed = self.__sampleType.itemData(index)
        self.__widget.setSampleSize(size)
        self.__widget.setSampleSigned(signed)

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
        self.__widget.setPosition(pos)
        self.__hexa.setPosition(pos)

    def moveToPreviousByte(self):
        pos = self.__widget.position() - 1
        pos = max(pos, 0)
        self.setPosition(pos)

    def moveToNextByte(self):
        pos = self.__widget.position() + 1
        pos = min(pos, self.__widget.memoryLength())
        self.setPosition(pos)

    def moveToPreviousPage(self):
        # FIXME: Have to be improved
        pos = self.__widget.position() - self.__widget.width()
        pos = max(pos, 0)
        self.setPosition(pos)

    def moveToNextPage(self):
        # FIXME: Have to be improved
        pos = self.__widget.position() + self.__widget.width()
        pos = min(pos, self.__widget.memoryLength())
        self.setPosition(pos)

    def memory(self) -> io.IOBase:
        return self.__widget.memory()

    def setMemory(self, memory: io.IOBase, address: int = 0):
        self.__address = address
        self.__widget.setMemory(memory)
        self.__hexa.setMemory(memory, address=address)
        self.__scroll.setValue(0)
        self.__scroll.setRange(0, self.__widget.memoryLength())

    def address(self) -> int:
        return self.__address
