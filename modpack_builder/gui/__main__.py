import sys

from qtpy.QtWidgets import QApplication

from modpack_builder.builder import ModpackBuilder
from modpack_builder.gui.application import ModpackBuilderWindow


app = QApplication(list())
builder = ModpackBuilder()
window = ModpackBuilderWindow(builder)

window.show()
sys.exit(app.exec_())
