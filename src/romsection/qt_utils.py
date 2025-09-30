import contextlib
import traceback
from PyQt5 import Qt


@contextlib.contextmanager
def blockSignals(widget: Qt.QWidget):
    try:
        old = widget.blockSignals(True)
        yield
    finally:
        widget.blockSignals(old)


@contextlib.contextmanager
def exceptionAsMessageBox(
    parent: Qt.QWidget | None = None,
    title: str = "Error",
):
    try:
        yield
        return True
    except Exception as e:
        try:
            msg = str(e.args[0])
        except Exception:
            msg = str(e)
        detail: str | None
        try:
            detail = traceback.format_exc()
        except Exception:
            detail = None

        msgBox = Qt.QMessageBox(parent)
        msgBox.setIcon(Qt.QMessageBox.Critical)
        msgBox.setText(msg)
        msgBox.setWindowTitle(title)
        if detail is not None:
            msgBox.setDetailedText(detail)
        msgBox.raise_()
        msgBox.exec_()
        return False
