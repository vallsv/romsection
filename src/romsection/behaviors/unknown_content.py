from PyQt5 import Qt
from ..gba_file import GBAFile
from .behavior import Behavior
from ..qt_utils import exceptionAsMessageBox
from ..model import ByteCodec, DataType


class ReplaceUnknownByPadding(Behavior):
    """
    Search and replace unknwn portions by padding when it's small and filled by zero
    """
    def run(self):
        Qt.QGuiApplication.setOverrideCursor(Qt.QCursor(Qt.Qt.WaitCursor))
        found = 0
        context = self.context()
        rom = context.rom()
        memoryMapList = context.memoryMapList()
        try:
            with exceptionAsMessageBox():
                for mem in memoryMapList:
                    if mem.data_type != DataType.UNKNOWN:
                        continue
                    if mem.byte_codec != ByteCodec.RAW:
                        continue
                    if mem.byte_length > 3:
                        continue
                    data = rom.extract_raw(mem)
                    if data.count("\x00") != mem.byte_length:
                        continue
                    # FIXME: We could chech adress alignement
                    #        but i feel like sometimes there is
                    #        surprisingly unaligned padding
                    mem.data_type = DataType.PADDING
                    memoryMapList.updatedObject(mem)
                    found += 1
        finally:
            Qt.QGuiApplication.restoreOverrideCursor()

        if found:
            Qt.QMessageBox.information(
                context,
                "Result",
                f"{found} memory maps were fixed"
            )
        else:
            Qt.QMessageBox.information(
                context,
                "Result",
                "Nothing was modified"
            )
