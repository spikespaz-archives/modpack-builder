import os
import sys

from pathlib import Path

os.environ["QT_API"] = "pyqt5"

from qtpy.QtWidgets import QApplication, QMainWindow
from qtpy import uic


class ModpackBuilderWindow(QMainWindow):
    __should_reset_profile_icon_path = False
    
    def __init__(self, builder, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.builder = builder

        uic.loadUi(str((Path(__file__).parent / "interface.ui").resolve()), self)

        # Fix for PyQt5
        if os.environ["QT_API"] == "pyqt5":
            self.setContentsMargins(9, 9, 9, 9)


if __name__ == "__main__":
    app = QApplication([])
    window = ModpackBuilderWindow(None)

    window.show()
    sys.exit(app.exec_())
