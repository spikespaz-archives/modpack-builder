import sys
import time

from qtpy.QtCore import Slot
from qtpy.QtWidgets import QApplication, QPushButton

import modpack_builder.utilities as utilities
import modpack_builder.gui.helpers as helpers

from modpack_builder.gui.multi_progress_dialog import MultiProgressDialog


if __name__ == "__main__":
    app = QApplication(list())
    dialog = MultiProgressDialog()
    dialog.setWindowTitle("Example Progress Reporter Dialog")

    add_reporter_button = QPushButton("Add Reporter", dialog)
    dialog.cancel_button_layout.addWidget(add_reporter_button)

    reporters = []
    reporter_count = 8

    dialog.main_reporter.maximum = reporter_count

    @Slot()
    @helpers.connect_slot(add_reporter_button.clicked)
    def __add_reporter():
        reporters.append(dialog.reporter())
        reporters[-1].maximum = 100
        reporters[-1].value = min(len(reporters) / reporter_count * 100, 100)
        reporters[-1].text = f"Reporter {len(reporters)}: %p%"

        dialog.main_reporter.value = len(reporters)

        dialog.log(f"Added reporter {len(reporters)} with value of {reporters[-1].value}")

    @utilities.make_thread(daemon=True)
    def __add_reporters_thread():
        for number in range(reporter_count):
            if dialog.cancel_requested:
                return

            time.sleep(0.5)
            __add_reporter()

    @utilities.make_thread(daemon=True)
    def __remove_reporters_thread():
        for reporter in reporters:
            time.sleep(0.5)
            reporter.done()
            dialog.log(f"Removed reporter: {str(reporter)}")


    @utilities.make_thread(daemon=True)
    def __cancel_thread():
        __add_reporters_thread.join()
        __remove_reporters_thread.start()
        __remove_reporters_thread.join()

        dialog.completed.emit()

    dialog.cancel_request.connect(__cancel_thread.start)

    dialog.show()
    __add_reporters_thread.start()

    sys.exit(app.exec_())
