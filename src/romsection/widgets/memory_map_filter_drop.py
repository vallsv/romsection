from PyQt5 import Qt
from functools import partial

from ..model import DataType, DataTypeGroup
from . import ui_styles
from .memory_map_proxy_model import MemoryMapFilter


class MemoryMapFilterDrop(Qt.QToolButton):

    filterChanged = Qt.pyqtSignal(object)

    def __init__(self, parent: Qt.QWidget | None):
        Qt.QToolButton.__init__(self, parent=parent)
        self.setPopupMode(Qt.QToolButton.InstantPopup)

        self.__filter: MemoryMapFilter | None = None
        self.__updateIcon()

        self.__toolMenu = Qt.QMenu(self)
        self.setMenu(self.__toolMenu)
        self.__toolMenu.aboutToShow.connect(self.__menuAboutToShow)

    def __updateIcon(self):
        if self.__filter is None:
            self.setIcon(Qt.QIcon("icons:filter.png"))
            self.setToolTip("Filter the memory map list")
        else:
            self.setIcon(Qt.QIcon("icons:filter-none.png"))
            self.setToolTip("Filter the memory map list")

    def __menuAboutToShow(self):
        menu = self.__toolMenu
        menu.clear()

        action = Qt.QAction(self)
        action.setCheckable(True)
        action.setText("Image")
        action.setChecked(self.__isDataTypeGroupShown(DataTypeGroup.IMAGE))
        action.triggered.connect(partial(self.__setDataTypeGroupShown, DataTypeGroup.IMAGE))
        action.setIcon(ui_styles.getIcon(DataTypeGroup.IMAGE))
        menu.addAction(action)

        action = Qt.QAction(self)
        action.setCheckable(True)
        action.setText("Tile set")
        action.setChecked(self.__isDataTypeGroupShown(DataTypeGroup.TILE_SET))
        action.triggered.connect(partial(self.__setDataTypeGroupShown, DataTypeGroup.TILE_SET))
        action.setIcon(ui_styles.getIcon(DataTypeGroup.TILE_SET))
        menu.addAction(action)

        action = Qt.QAction(self)
        action.setCheckable(True)
        action.setText("Palette")
        action.setChecked(self.__isDataTypeGroupShown(DataTypeGroup.PALETTE))
        action.triggered.connect(partial(self.__setDataTypeGroupShown, DataTypeGroup.PALETTE))
        action.setIcon(ui_styles.getIcon(DataTypeGroup.PALETTE))
        menu.addAction(action)

        action = Qt.QAction(self)
        action.setCheckable(True)
        action.setText("Sample")
        action.setChecked(self.__isDataTypeGroupShown(DataTypeGroup.SAMPLE))
        action.triggered.connect(partial(self.__setDataTypeGroupShown, DataTypeGroup.SAMPLE))
        action.setIcon(ui_styles.getIcon(DataTypeGroup.SAMPLE))
        menu.addAction(action)

        action = Qt.QAction(self)
        action.setCheckable(True)
        action.setText("Music")
        action.setChecked(self.__isDataTypeGroupShown(DataTypeGroup.MUSIC))
        action.triggered.connect(partial(self.__setDataTypeGroupShown, DataTypeGroup.MUSIC))
        action.setIcon(ui_styles.getIcon(DataTypeGroup.MUSIC))
        menu.addAction(action)

        action = Qt.QAction(self)
        action.setCheckable(True)
        action.setText("Padding")
        action.setChecked(self.__isDataTypeShown(DataType.PADDING))
        action.triggered.connect(partial(self.__setDataTypeShown, DataType.PADDING))
        action.setIcon(ui_styles.getIcon(DataType.PADDING))
        menu.addAction(action)

        action = Qt.QAction(self)
        action.setCheckable(True)
        action.setText("Unknown")
        action.setChecked(self.__isDataTypeShown(DataType.UNKNOWN))
        action.triggered.connect(partial(self.__setDataTypeShown, DataType.UNKNOWN))
        action.setIcon(ui_styles.getIcon(DataType.UNKNOWN))
        menu.addAction(action)

        menu.addSeparator()

        action = Qt.QAction(self)
        action.setText("Unknown palettes")
        action.triggered.connect(self.__unknownPalettes)
        action.setIcon(ui_styles.getIcon(DataType.PALETTE))
        menu.addAction(action)

        menu.addSeparator()

        action = Qt.QAction(self)
        action.setText("Clear filters" if self.__filter is not None else "No filters")
        action.setEnabled(self.__filter is not None)
        action.triggered.connect(self.__clearFilter)
        action.setIcon(Qt.QIcon("icons:clear.png"))
        menu.addAction(action)

    def __isDataTypeGroupShown(self, dataTypeGroup: DataTypeGroup) -> bool:
        filter = self.__filter
        if filter is None:
            return True
        shownDataTypes = filter.shownDataTypes
        if shownDataTypes is None:
            return True
        for dataType in DataType:
            if dataType.value.group == dataTypeGroup:
                if dataType in shownDataTypes:
                    return True
        return False

    def __isDataTypeShown(self, dataType: DataType) -> bool:
        filter = self.__filter
        if filter is None:
            return True
        shownDataTypes = filter.shownDataTypes
        if shownDataTypes is None:
            return True
        return dataType in shownDataTypes

    def __shownDataTypeSet(self) -> set[DataType]:
        filter = self.__filter
        if filter is None:
            return set(DataType)
        shownDataTypes = filter.shownDataTypes
        if shownDataTypes is None:
            return set(DataType)
        return set(shownDataTypes)

    def __createMemoryMap(
        self,
        shownDataTypes: set[DataType] | None,
    ) -> MemoryMapFilter | None:
        if shownDataTypes == set(DataType):
            shownDataTypes = None
        filter = self.__filter
        minBytePayload = filter.minBytePayload if filter else None
        maxBytePayload = filter.maxBytePayload if filter else None
        if shownDataTypes is None and minBytePayload is None and maxBytePayload is None:
            return None
        return MemoryMapFilter(
            shownDataTypes=shownDataTypes,
            minBytePayload=minBytePayload,
            maxBytePayload=maxBytePayload,
        )

    def __setDataTypeGroupShown(self, dataTypeGroup: DataTypeGroup, shown: bool):
        new = self.__shownDataTypeSet()
        if shown:
            for dataType in DataType:
                if dataType.value.group == dataTypeGroup:
                    new.add(dataType)
        else:
            for dataType in DataType:
                if dataType.value.group == dataTypeGroup:
                    new.discard(dataType)
        filter = self.__createMemoryMap(new)
        self.setFilter(filter)

    def __setDataTypeShown(self, dataType: DataType, shown: bool):
        new = self.__shownDataTypeSet()
        if shown:
            new.add(dataType)
        else:
            new.discard(dataType)
        filter = self.__createMemoryMap(new)
        self.setFilter(filter)

    def __unknownPalettes(self):
        filter = MemoryMapFilter(
            shownDataTypes={DataType.UNKNOWN},
            minBytePayload=32,
            maxBytePayload=32,
        )
        self.setFilter(filter)

    def __clearFilter(self):
        self.setFilter(None)

    def setFilter(self, filter: MemoryMapFilter | None):
        if self.__filter == filter:
            return
        self.__filter = filter
        self.__updateIcon()
        self.filterChanged.emit(filter)
