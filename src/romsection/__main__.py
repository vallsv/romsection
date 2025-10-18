import sys
from PyQt5 import Qt
import argparse
from importlib.metadata import version
from .gba_file import GBAFile


def main():
    parser = argparse.ArgumentParser(
        prog='RomSection',
        description='Dissect GameBoyAdvance ROMs',
    )

    parser.add_argument(
        "filename",
        nargs='?',
        help="Filename of a .gba ROM file or .toml file"
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


if __name__ == "__main__":
    main()
