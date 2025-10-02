import os
import io
import numpy
from PyQt5 import Qt
from numpy.typing import DTypeLike


class SoundWaveView(Qt.QWidget):
    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QWidget.__init__(self, parent=parent)
        self.setSizePolicy(Qt.QSizePolicy.Expanding, Qt.QSizePolicy.Expanding)
        self.__nbSamplePerPixel = 1
        self.__sampleSize = 2
        self.__sampleSigned = False
        self.__memory: io.IOBase = io.BytesIO(b"")
        self.__len = 0
        self.__pos = 0

    def setNbSamplePerPixels(self, nb_sample: int):
        if nb_sample == self.__nbSamplePerPixel:
            return
        self.__nbSamplePerPixel = nb_sample
        self.update()

    def nbSamplePerPixels(self) -> int:
        return self.__nbSamplePerPixel

    def setSampleSize(self, sampleSize: int):
        if sampleSize == self.__sampleSize:
            return
        self.__sampleSize = sampleSize
        self.update()

    def sampleSize(self) -> int:
        return self.__sampleSize

    def setSampleSigned(self, sampleSigned: bool):
        if sampleSigned == self.__sampleSigned:
            return
        self.__sampleSigned = sampleSigned
        self.update()

    def sampleSigned(self) -> bool:
        return self.__sampleSigned

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
        if self.__sampleSigned:
            if self.__sampleSize == 1:
                return numpy.int8
            if self.__sampleSize == 2:
                return numpy.int16
            if self.__sampleSize == 4:
                return numpy.int32
            raise ValueError(f"Unsupported sample size {self.__sampleSize}")
        else:
            if self.__sampleSize == 1:
                return numpy.uint8
            if self.__sampleSize == 2:
                return numpy.uint16
            if self.__sampleSize == 4:
                return numpy.uint32
            raise ValueError(f"Unsupported sample size {self.__sampleSize}")

    def _getData(self, width: int) -> tuple[numpy.ndarray, numpy.ndarray]:
        # FIXME: We probably have to align to odd bytes
        bytePerPixels = self.__sampleSize * self.__nbSamplePerPixel
        size = width * bytePerPixels
        end = min(self.__pos + size, self.__len)
        size = (end - self.__pos) - (end - self.__pos) % bytePerPixels
        f = self.__memory
        f.seek(self.__pos, os.SEEK_SET)
        data = f.read(size)
        dtype = self._getDtype()
        array = numpy.frombuffer(data, dtype=dtype)
        if not self.__sampleSigned:
            if self.__sampleSize == 1:
                hmax = 0xFF // 2
            elif self.__sampleSize == 2:
                hmax = 0xFFFF // 2
            elif self.__sampleSize == 4:
                hmax = 0xFFFFFFFF // 2
            else:
                raise ValueError(f"Unsupported sammple size {self.__sampleSize}")
            array = array.astype(numpy.int64)
            array = array - hmax
        array.shape = -1, self.__nbSamplePerPixel
        minArray = array.min(axis=1)
        maxArray = array.max(axis=1)
        return minArray, maxArray

    def _normalised(self, data: numpy.ndarray, length: int) -> numpy.ndarray:
        vmax = 0
        if self.__sampleSize == 1:
            vmax = 0xFF // 2
        elif self.__sampleSize == 2:
            vmax = 0xFFFF // 2
        elif self.__sampleSize == 4:
            vmax = 0xFFFFFFFF // 2
        else:
            raise ValueError(f"Unsupported sammple size {self.__sampleSize}")
        return (data / vmax * length).astype(numpy.int16)

    def paintEvent(self, event: Qt.QPaintEvent):
        painter = Qt.QPainter(self)
        self._paintAll(painter)

    def _paintAll(self, painter: Qt.QPainter):
        painter.save()

        width = self.width()
        height = self.height()

        margin = 5
        half_height = height // 2
        minArray, maxArray = self._getData(width)
        minArray = self._normalised(minArray, half_height - margin) + half_height
        maxArray = self._normalised(minArray, half_height - margin) + half_height
        for x, (vmin, vmax) in enumerate(zip(minArray, maxArray)):
            painter.drawLine(x, vmin, x, vmax)

        painter.restore()
