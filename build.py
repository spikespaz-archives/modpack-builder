from pathlib import Path

from distribution_tools.pyinstaller_wrapper import pyinstaller_compile
from modpack_builder.gui import PROGRAM_NAME


pyinstaller_compile(
    filenames=(Path("modpack_builder/gui/__main__.py"),),
    name=PROGRAM_NAME,
    onefile=True,
    noconfirm=True,
    clean_build=True,
    hiddenimports=("PySide2.QtXml",),
    datas=((Path("modpack_builder/gui/ui"), "modpack_builder/gui/ui"),),
)
