from PyQt5 import Qt

from ..gba_file import DataType
from . import ui_styles


class DataTypeList(Qt.QListWidget):

    valueChanged = Qt.pyqtSignal(object)

    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QListWidget.__init__(self, parent)
        self.setUniformItemSizes(True)
        self.setVerticalScrollBarPolicy(Qt.Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(Qt.QSizePolicy.Expanding, Qt.QSizePolicy.Maximum)
        self.setSizeAdjustPolicy(Qt.QListWidget.AdjustToContents)
        self.setResizeMode(Qt.QListView.Fixed)

        item = Qt.QListWidgetItem()
        item.setText(f"GBA ROM header")
        item.setData(Qt.Qt.UserRole, DataType.GBA_ROM_HEADER)
        item.setIcon(ui_styles.getIcon(DataType.GBA_ROM_HEADER))
        self.addItem(item)

        item = Qt.QListWidgetItem()
        item.setText(f"Image")
        item.setData(Qt.Qt.UserRole, DataType.IMAGE)
        item.setIcon(ui_styles.getIcon(DataType.IMAGE))
        self.addItem(item)

        item = Qt.QListWidgetItem()
        item.setText(f"Palette")
        item.setData(Qt.Qt.UserRole, DataType.PALETTE)
        item.setIcon(ui_styles.getIcon(DataType.PALETTE))
        self.addItem(item)

        item = Qt.QListWidgetItem()
        item.setText(f"Tile set")
        item.setData(Qt.Qt.UserRole, DataType.TILE_SET)
        item.setIcon(ui_styles.getIcon(DataType.TILE_SET))
        self.addItem(item)

        item = Qt.QListWidgetItem()
        item.setText(f"Padding")
        item.setData(Qt.Qt.UserRole, DataType.PADDING)
        item.setIcon(ui_styles.getIcon(DataType.PADDING))
        self.addItem(item)

        item = Qt.QListWidgetItem()
        item.setText(f"Sample (sappy)")
        item.setData(Qt.Qt.UserRole, DataType.SAMPLE_SAPPY)
        item.setIcon(ui_styles.getIcon(DataType.SAMPLE_SAPPY))
        self.addItem(item)

        item = Qt.QListWidgetItem()
        item.setText(f"Sample Int8")
        item.setData(Qt.Qt.UserRole, DataType.SAMPLE_INT8)
        item.setIcon(ui_styles.getIcon(DataType.SAMPLE_INT8))
        self.addItem(item)

        item = Qt.QListWidgetItem()
        item.setText(f"Music instrument (sappy)")
        item.setData(Qt.Qt.UserRole, DataType.MUSIC_INSTRUMENT_SAPPY)
        item.setIcon(ui_styles.getIcon(DataType.MUSIC_INSTRUMENT_SAPPY))
        self.addItem(item)

        item = Qt.QListWidgetItem()
        item.setText(f"Music song address (sappy)")
        item.setData(Qt.Qt.UserRole, DataType.MUSIC_SONG_TABLE_SAPPY)
        item.setIcon(ui_styles.getIcon(DataType.MUSIC_SONG_TABLE_SAPPY))
        self.addItem(item)

        item = Qt.QListWidgetItem()
        item.setText(f"Music song header (sappy)")
        item.setData(Qt.Qt.UserRole, DataType.MUSIC_SONG_HEADER_SAPPY)
        item.setIcon(ui_styles.getIcon(DataType.MUSIC_SONG_HEADER_SAPPY))
        self.addItem(item)

        item = Qt.QListWidgetItem()
        item.setText(f"Music song track (sappy)")
        item.setData(Qt.Qt.UserRole, DataType.MUSIC_TRACK_SAPPY)
        item.setIcon(ui_styles.getIcon(DataType.MUSIC_TRACK_SAPPY))
        self.addItem(item)

        item = Qt.QListWidgetItem()
        item.setText(f"Music key split table (sappy)")
        item.setData(Qt.Qt.UserRole, DataType.MUSIC_KEY_SPLIT_TABLE_SAPPY)
        item.setIcon(ui_styles.getIcon(DataType.MUSIC_KEY_SPLIT_TABLE_SAPPY))
        self.addItem(item)

        item = Qt.QListWidgetItem()
        item.setText(f"Unknown")
        item.setData(Qt.Qt.UserRole, DataType.UNKNOWN)
        item.setIcon(ui_styles.getIcon(DataType.UNKNOWN))
        self.addItem(item)

        rect = self.visualItemRect(item)
        self.setMinimumHeight(rect.height() * self.count() + 4)
        self.setMaximumHeight(rect.height() * self.count() + 4)

        self.itemSelectionChanged.connect(self._onItemSelectionChanged)

    def _onItemSelectionChanged(self):
        self.valueChanged.emit(self.selectedValue())

    def selectedValue(self) -> DataType | None:
        items = self.selectedItems()
        if len(items) != 1:
            return None
        value = items[0].data(Qt.Qt.UserRole)
        return value

    def _findItemFromValue(self, value: DataType | None) -> Qt.QListWidgetItem | None:
        if value is None:
            return None
        for i in range(self.count()):
            item = self.item(i)
            if item.data(Qt.Qt.UserRole) == value:
                return item
        return None

    def selectValue(self, value: DataType | None):
        item = self._findItemFromValue(value)
        if item is not None:
            i = self.row(item)
            self.setCurrentRow(i)
        else:
            self.setCurrentRow(-1)
