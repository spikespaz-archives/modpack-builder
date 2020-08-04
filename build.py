#! /usr/bin/env python

import os

from pathlib import Path

from distribution_tools import pyinstaller_compile
from modpack_builder.gui import PROGRAM_NAME


pyqt5_runtime_hook = "import os; os.environ['QT_API'] = 'pyqt5'"
pyside2_runtime_hook = "import os; os.environ['QT_API'] = 'pyside2'"


def build_version_pyqt5(distpath, workpath, onefile=True, clean_build=True):
    workpath.mkdir(parents=True, exist_ok=True)

    with open(pyqt5_runtime_hook_file := workpath / "pyqt5_runtime_hook.py", "w") as file:
        file.write(pyqt5_runtime_hook + "\n")

    pyinstaller_compile(
        filenames=(Path("modpack_builder/gui/__main__.py"),),
        name=f"{PROGRAM_NAME} (PyQt5)",
        icon_file=Path("icon/icon.ico"),
        # console=False,
        onefile=onefile,
        noconfirm=True,
        clean_build=clean_build,
        noupx=True,
        datas=(
            (Path("modpack_builder/gui/ui"), "modpack_builder/gui/ui"),
            (Path("icon/icon.ico"), "icon")
        ),
        runtime_hooks=(pyqt5_runtime_hook_file,),
        specpath=workpath,
        distpath=distpath,
        workpath=workpath
    )


def build_version_pyside2(distpath, workpath, onefile=True, clean_build=True):
    workpath.mkdir(parents=True, exist_ok=True)

    with open(pyside2_runtime_hook_file := workpath / "pyside2_runtime_hook.py", "w") as file:
        file.write(pyside2_runtime_hook + "\n")

    pyinstaller_compile(
        filenames=(Path("modpack_builder/gui/__main__.py"),),
        name=f"{PROGRAM_NAME} (PySide2)",
        icon_file=Path("icon/icon.ico"),
        # console=False,
        onefile=onefile,
        noconfirm=True,
        clean_build=clean_build,
        noupx=True,
        hiddenimports=("PySide2.QtXml",),
        datas=(
            (Path("modpack_builder/gui/ui"), "modpack_builder/gui/ui"),
            (Path("icon/icon.ico"), "icon")
        ),
        runtime_hooks=(pyside2_runtime_hook_file,),
        specpath=workpath,
        distpath=distpath,
        workpath=workpath
    )


if __name__ == "__main__":
    if os.environ["QT_API"] == "pyqt5":
        print(f"Building {PROGRAM_NAME} (PyQt5)")
        build_version_pyqt5(Path(".output"), Path(".build_pyqt5"), onefile=False)
    elif os.environ["QT_API"] == "pyside2":
        print(f"Building {PROGRAM_NAME} (PySide2)")
        build_version_pyside2(Path(".output"), Path(".build_pyside2"), onefile=False)
