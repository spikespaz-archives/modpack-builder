import sys

from qtpy.QtWidgets import QApplication

from ..builder import ModpackBuilder
from .application import ModpackBuilderWindow


app = QApplication([])
builder = ModpackBuilder()
window = ModpackBuilderWindow(builder)

window.show()
sys.exit(app.exec_())
