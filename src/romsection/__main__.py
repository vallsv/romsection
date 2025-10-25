import sys
from PyQt5 import Qt
import argparse
from importlib.metadata import version
from .gba_file import GBAFile


def main():
    parser = argparse.ArgumentParser(
        prog='romsection',
        description='Dissect GameBoyAdvance ROMs',
    )

    parser.add_argument(
        "filename",
        nargs='?',
        help="A .gba ROM file or a .toml containing ROM description"
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
