from PyQt5 import Qt


class ComboBox(Qt.QComboBox):
    """
    Override combobox to not use underlayer toolkit widget.

    This trick allow to use properly `maxVisibleItems`.
    """

    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QComboBox.__init__(self, parent)
        # Force the use of Qt style
        self.setEditable(True)
        # Tune it to restore the previous behaviour
        self.lineEdit().setFrame(False)
        self.lineEdit().setReadOnly(True)
