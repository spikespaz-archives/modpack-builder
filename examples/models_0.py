import sys
import time

from qtpy.QtCore import Slot
from qtpy.QtGui import QStandardItem
from qtpy.QtWidgets import QApplication, QDialog, QListView, QVBoxLayout

import modpack_builder.utilities as utilities
import modpack_builder.gui.helpers as helpers

from modpack_builder.gui.models import BufferedItemModel


class ExampleProgressLogDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.resize(200, 300)

        self.progress_log_list_view = QListView(self)
        self.progress_log_item_model = BufferedItemModel(self.progress_log_list_view)

        self.progress_log_list_view.setUniformItemSizes(True)
        self.progress_log_list_view.setModel(self.progress_log_item_model)

        self.setLayout(QVBoxLayout(self))
        self.layout().addWidget(self.progress_log_list_view)

        self.__bind_auto_scroll_handlers()

    def __bind_auto_scroll_handlers(self):
        progress_log_scroll_bar = self.progress_log_list_view.verticalScrollBar()
        self.__scroll_bar_was_at_bottom = False

        @Slot()
        @helpers.connect_slot(self.progress_log_item_model.rowsAboutToBeInserted)
        def __on_progress_log_model_rows_about_to_be_inserted():
            self.__scroll_bar_was_at_bottom = progress_log_scroll_bar.value() == progress_log_scroll_bar.maximum()

        @Slot(int, int)
        @helpers.connect_slot(progress_log_scroll_bar.rangeChanged)
        def __on_progress_log_scroll_bar_range_changed(_, max_value):
            if self.__scroll_bar_was_at_bottom:
                progress_log_scroll_bar.setValue(max_value)

    def log(self, text):
        self.progress_log_item_model.appendRow(QStandardItem(text))


if __name__ == "__main__":
    app = QApplication(list())
    dialog = ExampleProgressLogDialog()
    dialog.setWindowTitle("Example Status Log Dialog")

    @utilities.make_thread(daemon=True)
    def __add_log_lines_thread():
        for line in range(10000):
            dialog.log(f"Example status line: {line}")
            time.sleep(0.01)  # Append rows at an interval of 10ms, faster than 50Hz

    dialog.show()
    __add_log_lines_thread.start()

    sys.exit(app.exec_())
