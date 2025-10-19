from PyQt5 import Qt
from ..model import DataType, DataTypeGroup


class InfoDialog(Qt.QDialog):
    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QDialog.__init__(self, parent=parent)
        self.setWindowTitle("Info")

        self._close = Qt.QPushButton(self)
        self._close.setText("Close")
        self._close.clicked.connect(self.accept)

        self._content = Qt.QGridLayout()

        self._romSize = Qt.QLabel(self)
        self._content.addWidget(Qt.QLabel("ROM size", self), 0, 0)
        self._content.addWidget(self._romSize, 0, 1)

        self._grapgicsSize = Qt.QLabel(self)
        self._graphicsPercent = Qt.QLabel(self)
        self._content.addWidget(Qt.QLabel("Graphics", self), 1, 0)
        self._content.addWidget(self._grapgicsSize, 1, 1)
        self._content.addWidget(self._graphicsPercent, 1, 2)

        self._audioSize = Qt.QLabel(self)
        self._audioPercent = Qt.QLabel(self)
        self._content.addWidget(Qt.QLabel("Audio", self), 2, 0)
        self._content.addWidget(self._audioSize, 2, 1)
        self._content.addWidget(self._audioPercent, 2, 2)

        self._otherSize = Qt.QLabel(self)
        self._otherPercent = Qt.QLabel(self)
        self._content.addWidget(Qt.QLabel("Others", self), 3, 0)
        self._content.addWidget(self._otherSize, 3, 1)
        self._content.addWidget(self._otherPercent, 3, 2)

        self._unknownSize = Qt.QLabel(self)
        self._unknownPercent = Qt.QLabel(self)
        self._content.addWidget(Qt.QLabel("Unknown", self), 4, 0)
        self._content.addWidget(self._unknownSize, 4, 1)
        self._content.addWidget(self._unknownPercent, 4, 2)

        buttonLayout = Qt.QHBoxLayout()
        buttonLayout.addStretch(0)
        buttonLayout.addWidget(self._close)
        buttonLayout.addStretch(0)

        layout = Qt.QVBoxLayout(self)
        layout.addLayout(self._content)
        layout.addLayout(buttonLayout)

    def setContext(self, context):
        rom = context.rom()
        if rom is None:
            return
        unknown = 0
        graphics = 0
        audio = 0
        other = 0
        memoryMapList = context.memoryMapList()
        for mem in memoryMapList:
            data_type = mem.data_type
            size = mem.byte_length or 0

            if data_type is None:
                unknown += size
            elif data_type.value.group == DataTypeGroup.IMAGE:
                graphics += size
            elif data_type.value.group == DataTypeGroup.PALETTE:
                graphics += size
            elif data_type.value.group == DataTypeGroup.TILE_SET:
                graphics += size
            elif data_type.value.group == DataTypeGroup.MUSIC:
                audio += size
            elif data_type.value.group == DataTypeGroup.SAMPLE:
                audio += size
            elif data_type == DataType.UNKNOWN:
                unknown += size
            elif data_type.value.group == DataTypeGroup.OTHER:
                other += size

        untagged = rom.size - (unknown + graphics + audio + other)

        def memory(s: int) -> str:
            if s < 2 * 1024:
                return f"{s} B"
            elif s < 1024 * 1024:
                return f"{s // (1024)} KiB"
            return f"{s // (1024 * 1024)} MiB"

        def percent(v: int) -> str:
            p = 100 * v / rom.size
            return f"{p:0.2f}%"

        self._romSize.setText(memory(rom.size))
        self._grapgicsSize.setText(memory(graphics))
        self._graphicsPercent.setText(percent(graphics))
        self._audioSize.setText(memory(audio))
        self._audioPercent.setText(percent(audio))
        self._otherSize.setText(memory(other))
        self._otherPercent.setText(percent(other))
        self._unknownSize.setText(memory(unknown))
        self._unknownPercent.setText(percent(unknown))
