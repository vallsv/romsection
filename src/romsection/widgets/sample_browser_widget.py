import os
import io
import enum
import typing
import numpy
from PyQt5 import Qt
from numpy.typing import DTypeLike

from .sample_codec_combo_box import SampleCodecs
from ..array_utils import translate_range_to_uint8


class SampleBrowserWidget(Qt.QWidget):

    playbackChanged = Qt.pyqtSignal(bool)

    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QWidget.__init__(self, parent=parent)
        self.setSizePolicy(Qt.QSizePolicy.Expanding, Qt.QSizePolicy.Expanding)
        self.__nbSamplePerPixel = 1
        self.__sampleCodec: SampleCodecs = SampleCodecs.INT8
        self.__memory: io.IOBase = io.BytesIO(b"")
        self.__len = 0
        self.__pos = 0
        self.__bytearray: Qt.QByteArray | None = None
        self.__sink: Qt.QAudioOutput | None = None

    def sampleCodec(self) -> SampleCodecs:
        return self.__sampleCodec

    def setSampleCodec(self, codec: SampleCodecs):
        if self.__sampleCodec is codec:
            return
        self.__sampleCodec = codec
        self.update()

    def playVisible(self):
        if self.__sink is not None:
            return
        self.playbackChanged.emit(True)

        array = self._getVisibleData()
        data = translate_range_to_uint8(array).tobytes()
        self.__bytearray = Qt.QByteArray(data)
        buffer = Qt.QBuffer(self.__bytearray, self)
        buffer.open(Qt.QIODevice.ReadOnly)

        format = Qt.QAudioFormat()
        # format.setSampleRate(16000)
        format.setSampleRate(13500)
        format.setChannelCount(1)
        format.setSampleSize(8)
        format.setCodec("audio/pcm")
        format.setByteOrder(Qt.QAudioFormat.LittleEndian)
        format.setSampleType(Qt.QAudioFormat.UnSignedInt)

        info = Qt.QAudioDeviceInfo.defaultOutputDevice()
        if not info.isFormatSupported(format):
            print("Raw audio format not supported by backend, cannot play audio.")
            print("Supported channel count:", info.supportedChannelCounts())
            print("Supported codecs:       ", info.supportedCodecs())
            print("Supported byte orders:  ", info.supportedByteOrders())
            print("Supported sample rates: ", info.supportedSampleRates())
            print("Supported sample sizes: ", info.supportedSampleSizes())
            print("Supported sample types: ", info.supportedSampleTypes())
            return

        self.__sink = Qt.QAudioOutput(info, format, self)
        self.__sink.stateChanged.connect(self._onStateChanged)
        self.__sink.start(buffer)

    def isPlaying(self) -> bool:
        return self.__sink is not None

    def stop(self):
        if self.__sink is None:
            return
        self.__sink.stop()

    def _onStateChanged(self, state: Qt.QAudio.State):
        if self.__sink is None:
            return
        if state == Qt.QAudio.IdleState:
            self.__sink.stop()
        elif state == Qt.QAudio.StoppedState:
            self.__sink.deleteLater()
            self.__bytearray = None
            self.__sink = None
            self.playbackChanged.emit(False)

    def setNbSamplePerPixels(self, nb_sample: int):
        if nb_sample == self.__nbSamplePerPixel:
            return
        self.__nbSamplePerPixel = nb_sample
        self.update()

    def nbSamplePerPixels(self) -> int:
        return self.__nbSamplePerPixel

    def memory(self) -> io.IOBase:
        return self.__memory

    def setMemory(self, memory: io.IOBase):
        if self.__memory == memory:
            return
        self.__memory = memory

        self.__memory.seek(0, os.SEEK_END)
        self.__len = self.__memory.tell()
        self.__memory.seek(0, os.SEEK_SET)
        self.__pos = 0

        self.update()

    def memoryLength(self) -> int:
        return self.__len

    def position(self) -> int:
        return self.__pos

    def setPosition(self, position: int):
        if position == self.__pos:
            return
        self.__pos = position
        self.update()

    def resizeEvent(self, event):
        self.update()

    def _getDtype(self) -> DTypeLike:
        codec = self.__sampleCodec
        if codec == SampleCodecs.UINT8:
            return numpy.uint8
        if codec == SampleCodecs.INT8:
            return numpy.int8
        if codec == SampleCodecs.UINT16_BIG:
            return numpy.dtype(">u2")
        if codec == SampleCodecs.INT16_BIG:
            return numpy.dtype(">i2")
        raise ValueError(f"Unsupported sample size {codec}")

    def _getRange(self) -> tuple[int, int]:
        codec = self.__sampleCodec
        if codec == SampleCodecs.UINT8:
            return 0, 0xFF
        if codec == SampleCodecs.INT8:
            return -0x80, 0x7F
        if codec == SampleCodecs.UINT16_BIG:
            return 0, 0xFFFF
        if codec == SampleCodecs.INT16_BIG:
            return -0x8000, 0x7FFF
        raise ValueError(f"Unsupported sample size {codec}")

    def _getVisibleData(self) -> numpy.ndarray:
        width = self.width()
        codec = self.__sampleCodec.value
        sampleSize = codec.sample_size
        bytePerPixels = sampleSize * self.__nbSamplePerPixel
        size = width * bytePerPixels
        end = min(self.__pos + size, self.__len)
        size = (end - self.__pos) - (end - self.__pos) % bytePerPixels
        f = self.__memory
        f.seek(self.__pos, os.SEEK_SET)
        data = f.read(size)
        dtype = self._getDtype()
        array = numpy.frombuffer(data, dtype=dtype)
        return array

    def _getData(self, width: int, height: int) -> tuple[numpy.ndarray, numpy.ndarray]:
        # FIXME: We could filter data which is not aligned
        vrange = self._getRange()
        array = self._getVisibleData()
        array = array.astype(numpy.float32)
        array = (array - vrange[0]) / (vrange[1] - vrange[0])
        array = (array * height).astype(numpy.uint16)

        array.shape = -1, self.__nbSamplePerPixel
        middle = numpy.full(self.__nbSamplePerPixel, height // 2, dtype=numpy.uint16)
        minArray = numpy.minimum(array.min(axis=1), height // 2, dtype=numpy.uint16)
        maxArray = numpy.maximum(array.max(axis=1), height // 2, dtype=numpy.uint16)

        return minArray, maxArray

    def paintEvent(self, event: Qt.QPaintEvent):
        painter = Qt.QPainter(self)
        self._paintAll(painter)

    def _paintAll(self, painter: Qt.QPainter):
        painter.save()

        width = self.width()
        height = self.height()

        minArray, maxArray = self._getData(width, height)
        for x, (vmin, vmax) in enumerate(zip(minArray, maxArray)):
            painter.drawLine(x, vmin, x, vmax)

        painter.restore()
