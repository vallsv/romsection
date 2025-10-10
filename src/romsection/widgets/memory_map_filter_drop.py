from PyQt5 import Qt
from functools import partial

from ..model import DataType, DataTypeGroup
from . import ui_styles


class MemoryMapFilterDrop(Qt.QToolButton):

    shownDataTypeChanged = Qt.pyqtSignal(object)

    def __init__(self, parent: Qt.QWidget | None):
        Qt.QToolButton.__init__(self, parent=parent)
        self.setPopupMode(Qt.QToolButton.InstantPopup)

        self.__allDataTypes: set[DataType] = set(DataType)
        self.__shownDataTypes: set[DataType] = self.__allDataTypes
        self.__updateIcon()

        self.__toolMenu = Qt.QMenu(self)
        self.setMenu(self.__toolMenu)
        self.__toolMenu.aboutToShow.connect(self.__menuAboutToShow)

    def __updateIcon(self):
        if self.__shownDataTypes == self.__allDataTypes:
            self.setIcon(Qt.QIcon("icons:filter.png"))
            self.setToolTip("Filter the memory map list (no filters)")
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
        action.setChecked(DataType.PADDING in self.__shownDataTypes)
        action.triggered.connect(partial(self.__setDataTypeShown, DataType.PADDING))
        action.setIcon(ui_styles.getIcon(DataType.PADDING))
        menu.addAction(action)

        action = Qt.QAction(self)
        action.setCheckable(True)
        action.setText("Unknown")
        action.setChecked(DataType.UNKNOWN in self.__shownDataTypes)
        action.triggered.connect(partial(self.__setDataTypeShown, DataType.UNKNOWN))
        action.setIcon(ui_styles.getIcon(DataType.UNKNOWN))
        menu.addAction(action)

    def __isDataTypeGroupShown(self, dataTypeGroup: DataTypeGroup) -> bool:
        for dataType in DataType:
            if dataType.value.group == dataTypeGroup:
                if dataType in self.__shownDataTypes:
                    return True
        return False

    def __setDataTypeGroupShown(self, dataTypeGroup: DataTypeGroup, shown: bool):
        new = set(self.__shownDataTypes)
        if shown:
            for dataType in DataType:
                if dataType.value.group == dataTypeGroup:
                    new.add(dataType)
        else:
            for dataType in DataType:
                if dataType.value.group == dataTypeGroup:
                    new.discard(dataType)
        if new == self.__shownDataTypes:
            return
        self.__shownDataTypes = new
        self.__updateIcon()
        self.shownDataTypeChanged.emit(set(self.__shownDataTypes))

    def __setDataTypeShown(self, dataType: DataType, shown: bool):
        new = set(self.__shownDataTypes)
        if shown:
            new.add(dataType)
        else:
            new.discard(dataType)
        if new == self.__shownDataTypes:
            return
        self.__shownDataTypes = new
        self.__updateIcon()
        self.shownDataTypeChanged.emit(set(self.__shownDataTypes))
