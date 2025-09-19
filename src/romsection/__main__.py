import sys
from PyQt5 import Qt

from .extractor import GBAFile, Extractor

filename = sys.argv[1]
print(f"ROM filename: {filename}")
rom = GBAFile(filename)
print(f"ROM size:     {rom.size // 1000 // 1000:.2f}MB")

app = Qt.QApplication([])
win = Extractor()
win.setRom(rom)
win.show()
app.exec()
