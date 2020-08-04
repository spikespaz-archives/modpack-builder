import sys

from pathlib import Path

from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QApplication

import modpack_builder

from modpack_builder.builder import ModpackBuilder
from modpack_builder.gui.application import ModpackBuilderWindow


app = QApplication(list())
builder = ModpackBuilder()
window = ModpackBuilderWindow(builder)

icon_path = (Path(modpack_builder.__file__).parent.parent / "icon/icon.ico").resolve()
window.setWindowIcon(QIcon(str(icon_path)))

window.show()
sys.exit(app.exec_())
