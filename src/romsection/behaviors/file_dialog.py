import os
from PyQt5 import Qt


def getTomlOrRomFilenameFromDialog(extractor) -> str | None:
    """
    Return an existing filename of a TOML or ROM.
    """
    dialog = Qt.QFileDialog(extractor)
    dialog.setWindowTitle("Load a file")
    dialog.setModal(True)
    filters = [
        "Any file (*.gba *.toml)",
        "TOML file (*.toml)",
        "GBA ROM file (*.gba)",
        "All files (*)",
    ]
    dialog.setNameFilters(filters)
    dialog.setFileMode(Qt.QFileDialog.ExistingFile)

    if extractor._dialogDirectory is not None and os.path.exists(extractor._dialogDirectory):
        dialog.setDirectory(extractor._dialogDirectory)

    result = dialog.exec_()
    if not result:
        # Cancelled
        return None

    extractor._dialogDirectory = str(dialog.directory())
    if len(dialog.selectedFiles()) != 1:
        # Probably cancelled
        return None

    filename = dialog.selectedFiles()[0]
    return filename


def getRomFilenameFromDialog(extractor) -> str | None:
    """
    Return an existing filename of a ROM.
    """
    dialog = Qt.QFileDialog(extractor)
    dialog.setWindowTitle("Load a ROM")
    dialog.setModal(True)
    filters = [
        "GBA ROM file (*.gba)",
        "All files (*)",
    ]
    dialog.setNameFilters(filters)
    dialog.setFileMode(Qt.QFileDialog.ExistingFile)

    if extractor._dialogDirectory is not None and os.path.exists(extractor._dialogDirectory):
        dialog.setDirectory(extractor._dialogDirectory)

    result = dialog.exec_()
    if not result:
        # Cancelled
        return None

    extractor._dialogDirectory = str(dialog.directory())
    if len(dialog.selectedFiles()) != 1:
        # Probably cancelled
        return None

    filename = dialog.selectedFiles()[0]
    return filename


def getSaveTomlFilenameFromDialog(extractor) -> str | None:
    """
    Return a filename which will be used for TOML saving.
    """
    dialog = Qt.QFileDialog(extractor)
    dialog.setWindowTitle("Save")
    dialog.setModal(True)
    filters = [
        "TOML file (*.toml)",
        "All files (*)",
    ]
    dialog.setNameFilters(filters)
    dialog.setFileMode(Qt.QFileDialog.AnyFile)
    dialog.setAcceptMode(Qt.QFileDialog.AcceptSave)

    if extractor._dialogDirectory is not None and os.path.exists(extractor._dialogDirectory):
        dialog.setDirectory(extractor._dialogDirectory)

    if extractor._filename is not None:
        dialog.selectFile(f"{os.path.basename(extractor._filename)}.toml")
    elif extractor._rom is not None:
        dialog.selectFile(f"{os.path.basename(extractor._rom.filename)}.toml")

    result = dialog.exec_()
    if not result:
        # Cancelled
        return None

    extractor._dialogDirectory = str(dialog.directory())
    if len(dialog.selectedFiles()) != 1:
        # Probably cancelled
        return None

    filename = dialog.selectedFiles()[0]
    return filename
