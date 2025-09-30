import sys
from PyQt5 import Qt
import argparse
from importlib.metadata import version
from .gba_file import GBAFile


parser = argparse.ArgumentParser(
    prog='RomSection',
    description='Dissect GameBoyAdvance ROMs',
    epilog='Text at the bottom of help')

parser.add_argument(
    "filename",
    nargs='?',
    help="Filename of a .gba ROM file"
)
parser.add_argument(
    "--version",
    action="version",
    version=f"%(prog)s {version('romsection')}"
)

args = parser.parse_args()
app = Qt.QApplication([])

from . import resources
resources.initResources()

from .extractor import Extractor
win = Extractor()

if args.filename is not None:
    win.loadFilename(args.filename)

win.show()
app.exec()
