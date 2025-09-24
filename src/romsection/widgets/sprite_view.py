import numpy
from PyQt5 import Qt


class SpriteView(Qt.QWidget):
    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QWidget.__init__(self, parent)
        layout = Qt.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._scene = Qt.QGraphicsScene(self)

        self._view = Qt.QGraphicsView(self)
        # self._view.setInteractive(True)
        self._view.setScene(self._scene)
        self._view.setVerticalScrollBarPolicy(Qt.Qt.ScrollBarAlwaysOff)
        self._view.setHorizontalScrollBarPolicy(Qt.Qt.ScrollBarAlwaysOff)

        self._pixmap = Qt.QGraphicsPixmapItem()
        self._scene.addItem(self._pixmap)

        layout.addWidget(self._view)

    def resizeEvent(self, event):
        self._fitData()

    def _fitData(self):
        self._view.fitInView(self._pixmap, Qt.Qt.KeepAspectRatio)

    def setData(self, data: numpy.ndarray | None):
        """
        Display sprite from numpy array of some.
        """
        if data is None:
            image = Qt.QImage()
        elif len(data.shape) == 2 and data.dtype == numpy.uint8:
            image = Qt.QImage(
                data.tobytes(),
                data.shape[1],
                data.shape[0],
                Qt.QImage.Format_Grayscale8,
            )
        elif len(data.shape) == 3 and data.shape[2] == 3 and data.dtype == numpy.uint8:
            image = Qt.QImage(
                data.tobytes(),
                data.shape[1],
                data.shape[0],
                Qt.QImage.Format_RGB888,
            )
        elif len(data.shape) == 3 and data.shape[2] == 3 and data.dtype.kind == "f":
            image = Qt.QImage(
                (data * 255).astype(numpy.uint8).tobytes(),
                data.shape[1],
                data.shape[0],
                Qt.QImage.Format_RGB888,
            )
        else:
            raise ValueError(f"Shape {data.shape} {data.dtype} {data.dtype.type} is not supported")
        pixmap = Qt.QPixmap.fromImage(image)
        self._pixmap.setPixmap(pixmap)
        imageSize = image.size()
        self._pixmap.setOffset(-imageSize.width() / 2, -imageSize.height() / 2)
        self._fitData()
