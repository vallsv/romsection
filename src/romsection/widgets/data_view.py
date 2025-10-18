import os
import io
import numpy
import typing
from PyQt5 import Qt

from ..model import MemoryMap, DataType
from .. import sappy_utils
from .. import gba_utils
from ..gba_file import GBAFile
from .hexa_view import HexaView
from .sappy_instrument_bank import SappyInstrumentBank
from .hexa_array_view import HexaArrayView
from .hexa_struct_view import HexaStructView
from ..behaviors import sappy_content


class Description(typing.NamedTuple):
    is_array: bool
    item_struct: typing.Any
    struct: typing.Any
    item_size: int | None


DESCRIPTION = {
    DataType.MUSIC_INSTRUMENT_SAPPY: Description(
        is_array=True,
        item_struct=sappy_utils.InstrumentItem,
        struct=None,
        item_size=12,
    ),
    DataType.MUSIC_SONG_TABLE_SAPPY: Description(
        is_array=True,
        item_struct=sappy_utils.SongTableItem,
        struct=None,
        item_size=8,
    ),
    DataType.MUSIC_SONG_HEADER_SAPPY: Description(
        is_array=False,
        item_struct=None,
        struct=sappy_utils.SongHeader,
        item_size=None,
    ),
    DataType.MUSIC_TRACK_SAPPY: Description(
        is_array=False,
        item_struct=None,
        struct=sappy_utils.Track,
        item_size=None,
    ),
    DataType.MUSIC_KEY_SPLIT_TABLE_SAPPY: Description(
        is_array=True,
        item_struct=sappy_utils.SongTableItem,
        struct=None,
        item_size=1,
    ),
    DataType.GBA_ROM_HEADER: Description(
        is_array=False,
        item_struct=None,
        struct=gba_utils.GbaHeader,
        item_size=None,
    ),
}


class DataView(Qt.QWidget):
    """
    Display most of the known data with the best we can have.

    Actually in mostly focus on hexa view.
    """

    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QWidget.__init__(self, parent=parent)
        self.setSizePolicy(Qt.QSizePolicy.Expanding, Qt.QSizePolicy.Expanding)

        context = parent

        self.__memoryMap: MemoryMap | None = None
        self.__rom: GBAFile | None = None

        self.setFocusPolicy(Qt.Qt.StrongFocus)

        layout = Qt.QVBoxLayout(self)
        self.setLayout(layout)

        self.__toolbar = Qt.QToolBar(self)
        self.__hexaStruct = HexaStructView(self)
        self.__statusbar = Qt.QStatusBar(self)

        self.__searchSappySongHeaders = sappy_content.SearchSappySongHeadersFromSongTable()
        self.__searchSappySongHeaders.setContext(context)
        self.__searchSappyTrackers = sappy_content.SearchSappyTracksFromSongTable()
        self.__searchSappyTrackers.setContext(context)
        self.__searchSappyKeySplitTable = sappy_content.SearchSappyKeySplitTableFromInstrumentTable()
        self.__searchSappyKeySplitTable.setContext(context)
        self.__searchSappySample = sappy_content.SearchSappySampleFromInstrumentTable()
        self.__searchSappySample.setContext(context)

        spacer = Qt.QWidget(self.__toolbar)
        spacer.setSizePolicy(Qt.QSizePolicy.Expanding, Qt.QSizePolicy.Expanding)
        self.__toolbar.addWidget(spacer)

        toolButton = Qt.QToolButton(self)
        toolButton.setPopupMode(Qt.QToolButton.InstantPopup)
        toolButton.setIcon(Qt.QIcon("icons:tool.png"))
        self.__toolbar.addWidget(toolButton)

        toolMenu = Qt.QMenu(toolButton)
        toolButton.setMenu(toolMenu)

        toolMenu.addSection("From sappy song table")

        action = Qt.QAction(self)
        action.triggered.connect(self.__searchSappySongHeaders.run)
        action.setText("Extract song headers")
        action.setToolTip("Extract referenced sappy song headers from song table")
        action.setIcon(Qt.QIcon("icons:music.png"))
        toolMenu.addAction(action)

        action = Qt.QAction(self)
        action.triggered.connect(self.__searchSappyTrackers.run)
        action.setText("Extract tracks")
        action.setToolTip("Extract referenced tracks from song table")
        action.setIcon(Qt.QIcon("icons:music.png"))
        toolMenu.addAction(action)

        toolMenu.addSection("From sappy instrument table")

        action = Qt.QAction(self)
        action.triggered.connect(self.__searchSappyKeySplitTable.run)
        action.setText("Extract key split table")
        action.setToolTip("Extract referenced key split table from instrument table")
        action.setIcon(Qt.QIcon("icons:instrument.png"))
        toolMenu.addAction(action)

        action = Qt.QAction(self)
        action.triggered.connect(self.__searchSappySample.run)
        action.setText("Extract samples")
        action.setToolTip("Extract referenced samples from instrument table")
        action.setIcon(Qt.QIcon("icons:sample.png"))
        toolMenu.addAction(action)

        self.__table = HexaArrayView(self)

        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(self.__toolbar)
        layout.addWidget(self.__hexaStruct)
        layout.addWidget(self.__table)
        layout.addWidget(self.__statusbar)
        layout.setStretchFactor(self.__table, 1)

        self.__table.selectionModel().selectionChanged.connect(self.__selectionChanged)

    def __selectionChanged(self):
        data = self.__table.selectedItemData()
        if data is None:
            self.__hexaStruct.setStruct(None)
            return
        address = self.__table.selectedItemAddress()
        dataType = self.__memoryMap.data_type if self.__memoryMap else None
        desc = DESCRIPTION.get(dataType)
        if desc is None:
            self.__hexaStruct.setStruct(None)
            return
        if desc.item_struct is None:
            self.__hexaStruct.setStruct(None)
            return
        dataStruct = desc.item_struct.parse_struct(data)
        self.__hexaStruct.setStruct(dataStruct, address)

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

    def __instrumentDescription(self, row: int, data: bytes) -> str:
        inst = sappy_utils.InstrumentItem.parse(data)
        return inst.short_description

    def __songDescription(self, row: int, data: bytes) -> str:
        songAddress = sappy_utils.SongTableItem.parse(data)
        return songAddress.short_description

    def _updateData(self):
        rom = self.__rom
        mem = self.__memoryMap
        if rom is None or mem is None:
            self.__table.setMemory(io.BytesIO(b""))
            return

        array = rom.extract_data(mem)
        data = array.tobytes()

        model = self.__table.model()
        dataType = self.__memoryMap.data_type if self.__memoryMap else None

        desc = DESCRIPTION.get(dataType)
        if desc is None:
            model.setItemSize(16)
            model.setDescriptionMethod(None)
            self.__table.setVisible(True)
            self.__hexaStruct.setVisible(False)
        elif desc.is_array:
            self.__table.setVisible(True)
            self.__table.setMemory(io.BytesIO(data), address=mem.byte_offset)
            model.setItemSize(desc.item_size)
            if dataType == DataType.MUSIC_SONG_TABLE_SAPPY:
                model.setDescriptionMethod(self.__songDescription)
            elif dataType == DataType.MUSIC_INSTRUMENT_SAPPY:
                model.setDescriptionMethod(self.__instrumentDescription)
            else:
                model.setDescriptionMethod(None)
            self.__hexaStruct.setVisible(True)
            self.__hexaStruct.setStruct(None)
        else:
            dataStruct = desc.struct.parse_struct(data)
            self.__table.setVisible(False)
            self.__hexaStruct.setVisible(True)
            self.__hexaStruct.setStruct(dataStruct, address=mem.byte_offset)
