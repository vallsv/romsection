import io
import numpy
from PyQt5 import Qt

from ..model import MemoryMap, DataType, SampleCodec
from ..gba_file import GBAFile
from ..parsers import sappy_utils
from .sample_browser_widget import SampleBrowserWidget
from .sample_codec_combo_box import SampleCodecs


class SampleView(Qt.QWidget):
    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QWidget.__init__(self, parent)
        layout = Qt.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.__memoryMap: MemoryMap | None = None
        self.__rom: GBAFile | None = None

        self.__toolbar = Qt.QToolBar(self)
        self.__wave = SampleBrowserWidget(self)
        self.__statusbar = Qt.QStatusBar(self)

        self.__playButton = Qt.QPushButton(self.__toolbar)
        self.__playButton.clicked.connect(self._playback)
        self.__playButton.setToolTip("Playback visible data only")
        self.__playButton.setIcon(Qt.QIcon("icons:play.png"))
        self.__toolbar.addWidget(self.__playButton)

        self.__toolbar.addSeparator()

        self.__samplePerPixels = Qt.QSpinBox(self.__toolbar)
        self.__samplePerPixels.setRange(1, 128)
        self.__samplePerPixels.setValue(self.__wave.nbSamplePerPixels())
        self.__toolbar.addWidget(self.__samplePerPixels)

        layout.addWidget(self.__toolbar)
        layout.addWidget(self.__wave)
        layout.addWidget(self.__statusbar)
        layout.setStretchFactor(self.__wave, 1)

        self.__wave.playbackChanged.connect(self._onPlaybackChanged)
        self.__samplePerPixels.valueChanged.connect(self.__wave.setNbSamplePerPixels)

    def _playback(self):
        if self.__wave.isPlaying():
            self.__wave.stop()
        else:
            self.__wave.play()

    def _onPlaybackChanged(self, playing: bool):
        if playing:
            self.__playButton.setIcon(Qt.QIcon("icons:stop.png"))
        else:
            self.__playButton.setIcon(Qt.QIcon("icons:play.png"))

    def memoryMap(self) -> MemoryMap | None:
        return self.__memoryMap

    def setMemoryMap(self, memoryMap: MemoryMap | None):
        self.__memoryMap = memoryMap
        self._updateData()

    def rom(self) -> GBAFile | None:
        return self.__rom

    def setRom(self, rom: GBAFile | None):
        self.__rom = rom
        self._updateData()

    def _updateData(self):
        rom = self.__rom
        mem = self.__memoryMap
        if rom is None or mem is None:
            self.__wave.setMemory(io.BytesIO(b""))
            return

        data = rom.extract_data(mem)
        data_type = mem.data_type

        if data_type == DataType.SAMPLE_INT8:
            memory = io.BytesIO(data)
            self.__wave.setPosition(0)
            self.__wave.setSampleCodec(SampleCodecs.INT8)
            self.__wave.setMemory(memory)
            self.__statusbar.showMessage("INT8")

        elif data_type == DataType.SAMPLE_SAPPY:
            if len(data) < 16:
                raise ValueError(f"Data is smaller ({len(data)}) than the expected header")
            header = data[0:16]
            sample = sappy_utils.SampleHeader.parse(header)
            memory = io.BytesIO(data[16:])
            self.__wave.setPosition(0)

            sampleCodec = mem.sample_codec
            if sampleCodec in (None, SampleCodec.SAMPLE_INT8):
                self.__wave.setSampleCodec(SampleCodecs.INT8)
            elif sampleCodec == SampleCodec.SAMPLE_UINT8:
                self.__wave.setSampleCodec(SampleCodecs.UINT8)
            else:
                assert False, f"Unsupported {sampleCodec}"

            self.__wave.setMemory(memory)

            other_flags = sample.flags & 0xBF
            desc = f"SAPPY INT8 loop={sample.loop} other flags={other_flags} pitch={sample.pitch} restart loop={sample.start} size={sample.size}"
            self.__statusbar.showMessage(desc)

        else:
            raise ValueError(f"Unsupported data type {data_type}")
