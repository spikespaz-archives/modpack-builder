import sys

from qtpy.QtWidgets import QApplication

from .application import ModpackBuilderWindow
from .builder2 import ModpackBuilder


app = QApplication([])
builder = ModpackBuilder()
window = ModpackBuilderWindow(builder)

window.show()
sys.exit(app.exec_())
