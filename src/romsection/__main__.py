import sys
from PyQt5 import Qt

from .gba_file import GBAFile

filename = sys.argv[1]
print(f"ROM filename: {filename}")
rom = GBAFile(filename)
print(f"ROM size:     {rom.size // 1000 // 1000:.2f}MB")

app = Qt.QApplication([])

from . import resources
resources.initResources()

from .extractor import Extractor
win = Extractor()
win.setRom(rom)
win.show()
app.exec()
