import os
import io
import numpy
import enum
import typing
from PyQt5 import Qt

from .combo_box import ComboBox


class SampleCodec(typing.NamedTuple):
    sample_size: int
    signed: bool
    endianness: typing.Literal["<", ">"]


class SampleCodecs(enum.Enum):
    INT8 = SampleCodec(1, True, "<")
    UINT8 = SampleCodec(1, False, "<")
    INT16_BIG = SampleCodec(2, True, ">")
    UINT16_BIG = SampleCodec(2, False, ">")


class SampleCodecComboBox(ComboBox):
    valueChanged = Qt.pyqtSignal(object)

    def __init__(self, parent: Qt.QWidget | None):
        ComboBox.__init__(self, parent=parent)
        self.addItem("Int 8bits", SampleCodecs.INT8)
        self.addItem("Uint 8bits", SampleCodecs.UINT8)
        self.addItem("Int Big 16bits", SampleCodecs.INT16_BIG)
        self.addItem("Uint Big 16bits", SampleCodecs.UINT16_BIG)
        self.currentIndexChanged.connect(self.__onIndexChanged)

    def __onIndexChanged(self, index: int):
        value = self.valueFromIndex(index)
        self.valueChanged.emit(value)

    def valueFromIndex(self, index: int) -> SampleCodecs | None:
        if index == -1:
            return None
        value = self.itemData(index)
        return value

    def indexFromValue(self, value: SampleCodecs | None) -> int:
        if value is None:
            return -1
        for index in range(self.itemCount()):
            v = self.valueFromIndex(index)
            if value is v:
                return index
        # Here we could update the component
        return -1

    def value(self) -> SampleCodecs | None:
        index = self.currentIndex()
        value = self.valueFromIndex(index)
        return value

    def selectValue(self, codec: SampleCodecs | None):
        index = self.indexFromValue(codec)
        self.setCurrentIndex(index)
