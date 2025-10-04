from PyQt5 import Qt
from ..gba_file import GBAFile
from .behavior import Behavior
from ..format_utils import format_address

class SearchSappyTag(Behavior):
    """
    Search for sappy empty bank.

    See https://www.romhacking.net/documents/462/
    """
    def run(self):
        unused_instrument = b"\x01\x3c\x00\x00\x02\x00\x00\x00\x00\x00\x0f\x00"
        context = self.context()
        rom = context.rom()
        result = rom.search_for_bytes(0, rom.size, unused_instrument)

        if result:
            offsets = [format_address(offset) for offset in result]
            string = ", ".join(offsets)
            Qt.QMessageBox.information(
                context,
                "Result",
                f"The following offsets looks like SAPPY empty instrument bank:\n{string}"
            )
        else:
            Qt.QMessageBox.information(
                context,
                "Result",
                "Nothing was found"
            )
