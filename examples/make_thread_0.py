import sys
import time

from qtpy.QtWidgets import QApplication, QMainWindow, QLabel, QWidget, QVBoxLayout

import modpack_builder.gui.helpers as helpers


class ExampleMainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setCentralWidget(QWidget(self))
        self.centralWidget().setLayout(QVBoxLayout(self.centralWidget()))

        self.label = QLabel("If you see this immediately, the thread did not block.", self.centralWidget())

        self.centralWidget().layout().addWidget(self.label)

        # PySide2 has an issue setting the parent for the thread. If the thread has a parent, calling 'start' will
        # block the main thread. https://bugreports.qt.io/browse/PYSIDE-1359
        self.test_thread = helpers.create_thread(self.long_running_task, parent=self)
        self.test_thread.start()

    @staticmethod
    def long_running_task():
        print("Task started.")
        time.sleep(5)
        print("Task finished.")


if __name__ == "__main__":
    app = QApplication(list())
    window = ExampleMainWindow()

    window.show()
    sys.exit(app.exec_())
