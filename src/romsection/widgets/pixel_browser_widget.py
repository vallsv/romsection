import os
import io
import numpy
from PyQt5 import Qt

from ..gba_file import ImageColorMode, ImagePixelOrder
from .. import array_utils


class PixelBrowserWidget(Qt.QWidget):

    selectionChanged = Qt.pyqtSignal(object)

    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QWidget.__init__(self, parent=parent)
        self.__colorMode = ImageColorMode.INDEXED_8BIT
        self.__pixelOrder = ImagePixelOrder.NORMAL
        self.__memory: io.IOBase = io.BytesIO(b"")
        self.__pos: int = 0
        self.__len: int = 0
        self.__pixelWidth: int = 48
        self.__zoom: int = 4
        self.__selectionFrom: int = -1
        self.__selectionTo: int = -1

    def selection(self) -> tuple[int, int] | None:
        """
        Return the selection.

        Return:
            A tuple with the position range.
            The first is included, the second is excluded.
        """
        if self.__selectionFrom == -1:
            return None
        if self.__selectionTo == -1:
            return None
        # FIXME: Make sure the returned selection is oriented
        return self.__pos + self.__selectionFrom, self.__pos + self.__selectionTo + 1

    def zoom(self) -> int:
        return self.__zoom

    def setZoom(self, zoom: int):
        if zoom == self.__zoom:
            return
        self.__zoom = zoom
        self.update()

    def position(self) -> int:
        return self.__pos

    def setPosition(self, position: int):
        if position == self.__pos:
            return
        self.__pos = position
        self.update()

    def pixelWidth(self) -> int:
        return self.__pixelWidth

    def setPixelWidth(self, pixelWidth: int):
        if pixelWidth == self.__pixelWidth:
            return
        self.__pixelWidth = pixelWidth
        self.update()

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

    def colorMode(self) -> ImageColorMode:
        return self.__colorMode

    def setColorMode(self, colorMode: ImageColorMode):
        if self.__colorMode == colorMode:
            return
        self.__colorMode = colorMode
        self.update()

    def pixelOrder(self) -> ImagePixelOrder:
        return self.__pixelOrder

    def setPixelOrder(self, pixelOrder: ImagePixelOrder):
        if self.__pixelOrder == pixelOrder:
            return
        self.__pixelOrder = pixelOrder
        self.update()

    def _readBytes(self, pos: int, length: int) -> bytes:
        """
        Read an amount of bytes.

        The amount of bytes can differ from the request if the
        steam is empty.
        """
        self.__memory.seek(pos, os.SEEK_SET)
        return self.__memory.read(length)

    def _getNbBytesPerPixels(self, nb_pixels: int) -> int:
        """Return the minimal nb bytes mandatory to display `nb_pixels`."""
        if self.__pixelOrder == ImagePixelOrder.NORMAL:
            pass
        elif self.__pixelOrder == ImagePixelOrder.TILED_8X8:
            # Have to be aligned to the next 8x8 pixels
            remained = nb_pixels % 8 * 8
            if remained != 0:
                nb_pixels += 8 * 8 - remained
        else:
            raise ValueError(f"Unsupported {self.__pixelOrder}")

        if self.__colorMode == ImageColorMode.INDEXED_8BIT:
            result = nb_pixels
        elif self.__colorMode == ImageColorMode.INDEXED_4BIT:
            remainded = nb_pixels % 2
            result = nb_pixels // 2
            if remainded != 0:
                # Have to be aligned to the next 2 pixels
                result += 1
        elif self.__colorMode == ImageColorMode.A1RGB15:
            result = nb_pixels * 2
        elif self.__colorMode == ImageColorMode.RGB15:
            result = nb_pixels * 2
        else:
            raise ValueError(f"Unsupported {self.__colorMode}")

        return result

    def _getConstrainedHeight(self, height: int) -> int:
        """
        Use the codec constraint to allow to display at least this `height`.
        """
        if self.__pixelOrder == ImagePixelOrder.TILED_8X8:
            remaining = height % 8
            if remaining != 0:
                height += 8 - remaining
        return height

    def _getConstrainedWidth(self, width: int) -> int:
        """
        Use the codec constraint to allow to display at least this `width`.
        """
        if self.__pixelOrder == ImagePixelOrder.TILED_8X8:
            remaining = width % 8
            if remaining != 0:
                width += 8 - remaining
        if self.__colorMode == ImageColorMode.INDEXED_4BIT:
            # Only display lines aligned to a byte
            if width % 2 != 0:
                width += 1
        return width

    def _getNbBytesForEasyDisplay(self, max_bytes: int, width: int) -> int:
        """
        Return the nb bytes which are easy to display.

        It's the minimal nb bytes, smaller or equal than this `nb_bytes`,
        which can be used to dispklay a full rectangle of the requested
        `width`.
        """
        if self.__pixelOrder == ImagePixelOrder.NORMAL:
            nb_pixels_for_width = width
        elif self.__pixelOrder == ImagePixelOrder.TILED_8X8:
            # The width should already be properly constrainted
            assert width % 8 == 0
            nb_tile_per_width = width // 8
            nb_pixels_for_width = nb_tile_per_width * 8 * 8
        else:
            raise ValueError(f"Unsupported {self.__pixelOrder}")

        if self.__colorMode == ImageColorMode.INDEXED_8BIT:
            nb_bytes_for_width = nb_pixels_for_width
        elif self.__colorMode == ImageColorMode.INDEXED_4BIT:
            # The width should already be properly constrainted
            assert width % 2 == 0
            nb_bytes_for_width = nb_pixels_for_width // 2
        elif self.__colorMode == ImageColorMode.A1RGB15:
            nb_bytes_for_width = nb_pixels_for_width * 2
        elif self.__colorMode == ImageColorMode.RGB15:
            nb_bytes_for_width = nb_pixels_for_width * 2
        else:
            raise ValueError(f"Unsupported {self.__colorMode}")

        nb_bytes = max_bytes - max_bytes % nb_bytes_for_width
        return nb_bytes

    def paintEvent(self, event: Qt.QPaintEvent):
        painter = Qt.QPainter(self)
        self._paintAll(painter)

    def _getBytesPerLine(self, width: int) -> int:
        if self.__colorMode == ImageColorMode.INDEXED_8BIT:
            return width
        elif self.__colorMode == ImageColorMode.INDEXED_4BIT:
            assert width % 2 == 0
            return width // 2
        elif self.__colorMode == ImageColorMode.A1RGB15:
            return width * 2
        elif self.__colorMode == ImageColorMode.RGB15:
            return width * 2
        raise ValueError(f"Unsupported {self.__colorMode}")

    def bytesPerLine(self) -> int:
        width = self._getConstrainedWidth(self.__pixelWidth)
        return self._getBytesPerLine(width)

    def _toImage(self, data: bytes, width: int) -> Qt.QImage:
        if len(data) == 0:
            return Qt.QImage()

        if self.__pixelOrder == ImagePixelOrder.NORMAL:
            pass

        bytes_per_line = self._getBytesPerLine(width)
        height = len(data) // bytes_per_line

        # FIXME: Some cases can have shortcuts

        if self.__colorMode == ImageColorMode.INDEXED_8BIT:
            array = numpy.frombuffer(data, dtype=numpy.uint8)
        elif self.__colorMode == ImageColorMode.INDEXED_4BIT:
            array = numpy.frombuffer(data, dtype=numpy.uint8)
            array = array_utils.convert_8bx1_to_4bx2(array)
            # FIXME: While there is no palette
            array *= 0xF
        elif self.__colorMode == ImageColorMode.A1RGB15:
            array = numpy.frombuffer(data, dtype=numpy.uint16)
            array = array_utils.convert_a1rgb15_to_argb32(array, use_alpha=True)
        elif self.__colorMode == ImageColorMode.RGB15:
            array = numpy.frombuffer(data, dtype=numpy.uint16)
            array = array_utils.convert_a1rgb15_to_argb32(array, use_alpha=False)
        else:
            raise ValueError(f"Unsupported {self.__colorMode}")

        if self.__pixelOrder == ImagePixelOrder.TILED_8X8:
            array.shape = height, width, -1
            array = array_utils.convert_to_tiled_8x8(array)

        if self.__colorMode in [ImageColorMode.INDEXED_8BIT, ImageColorMode.INDEXED_4BIT]:
            image = Qt.QImage(
                array.tobytes(),
                width,
                height,
                Qt.QImage.Format_Grayscale8,
            )
        else:
            image = Qt.QImage(
                array.tobytes(),
                width,
                height,
                Qt.QImage.Format_ARGB32,
            )
        return image

    def _paintAll(self, painter: Qt.QPainter):
        painter.save()

        transform = Qt.QTransform()
        transform = transform.scale(self.__zoom, self.__zoom)
        painter.setTransform(transform)

        visibleHeight = self.height() // self.__zoom
        if self.height() % self.__zoom != 0:
            visibleHeight += 1

        height = self._getConstrainedHeight(visibleHeight)
        width = self._getConstrainedWidth(self.__pixelWidth)

        nb_pixels = width * height
        nb_bytes = self._getNbBytesPerPixels(nb_pixels)

        binaryData = self._readBytes(self.__pos, nb_bytes)
        nbEasyBytes = self._getNbBytesForEasyDisplay(len(binaryData), width)
        easyBytes = binaryData[0:nbEasyBytes]
        image = self._toImage(easyBytes, width)
        painter.drawImage(Qt.QPoint(0, 0), image)

        remainingBytes = binaryData[nbEasyBytes:]
        # FIXME: Draw the remaining stuff

        painter.resetTransform()

        polygon = self._polygonSelection()
        if polygon is not None:
            painter.setPen(Qt.QPen(Qt.QColor(0, 0, 255)))
            painter.drawPolygon(polygon)

        painter.restore()

    def _pixelFromBytePosition(self, position: int) -> Qt.QPoint:
        # FIXME: Rework it for other than 1 pixel per byte
        pixelCenter = Qt.QPoint(self.__zoom // 2, self.__zoom // 2)
        if self.__pixelOrder == ImagePixelOrder.TILED_8X8:
            bytesPerLine = self.bytesPerLine()
            nbTilesPerLine = bytesPerLine // 8
            nbTiles, tp = divmod(position, 8 * 8)
            ty, tx = divmod(nbTiles, nbTilesPerLine)
            y, x = divmod(tp, 8)
            return Qt.QPoint(tx * 8 + x, ty * 8 + y) * self.__zoom + pixelCenter
        else:
            bytesPerLine = self.bytesPerLine()
            y, x = divmod(position, bytesPerLine)
            return Qt.QPoint(x, y) * self.__zoom + pixelCenter

    def _polygonSelection(self) -> Qt.QPolygon | None:
        if self.__selectionFrom == -1:
            return None
        poly = Qt.QPolygon(2)
        poly[0] = self._pixelFromBytePosition(self.__selectionFrom)
        poly[1] = self._pixelFromBytePosition(self.__selectionTo)
        return poly

    def _positionFromPixel(self, pos: Qt.QPoint) -> int:
        x = pos.x() // self.__zoom
        y = pos.y() // self.__zoom
        bytesPerLine = self.bytesPerLine()
        x = min(x, bytesPerLine)

        # FIXME: Rework it for other than 1 pixel per byte
        if self.__pixelOrder == ImagePixelOrder.TILED_8X8:
            tx, x = divmod(x, 8)
            ty, y = divmod(y, 8)
            position = ty * bytesPerLine * 8 + tx * 8 * 8 + y * 8 + x
        else:
            position = x + bytesPerLine * y
        return position

    def mousePressEvent(self, event: Qt.QMouseEvent):
        if event.button() == Qt.Qt.LeftButton:
            self.grabMouse()
            pos = self._positionFromPixel(event.pos())
            self.__selectionFrom = pos
            self.__selectionTo = pos
            self.update()
            self.selectionChanged.emit(self.selection())

    def mouseMoveEvent(self, event: Qt.QMouseEvent):
        if self.mouseGrabber() is self:
            pos = self._positionFromPixel(event.pos())
            self.__selectionTo = pos
            self.update()
            self.selectionChanged.emit(self.selection())

    def mouseReleaseEvent(self, event: Qt.QMouseEvent):
        if event.button() == Qt.Qt.LeftButton:
            pos = self._positionFromPixel(event.pos())
            self.__selectionTo = pos
            self.releaseMouse()
            self.update()
            self.selectionChanged.emit(self.selection())
