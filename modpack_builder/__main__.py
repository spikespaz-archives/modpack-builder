from .builder2 import ModpackBuilder

if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    from .application import ModpackBuilderWindow

    app = QApplication([])
    builder = ModpackBuilder()
    window = ModpackBuilderWindow(builder)

    window.show()
    sys.exit(app.exec_())
