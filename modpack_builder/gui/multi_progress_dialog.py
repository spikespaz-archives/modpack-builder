from pathlib import Path

from qtpy import uic
from qtpy.QtGui import QStandardItemModel, QStandardItem
from qtpy.QtCore import Qt, QObject, Signal, QTimer, QEvent, QMimeData
from qtpy.QtWidgets import QDialog, QMessageBox, QProgressBar, QListView, QVBoxLayout

import modpack_builder.gui.helpers as helpers

from modpack_builder.builder import ProgressReporter


class ProgressBarReporter(ProgressReporter, QObject):
    # The signals below are intentionally protected (mangled).
    # They should only ever be used internally by this class only.
    __set_maximum = Signal(int)
    __set_value = Signal(int)
    __set_text = Signal(str)

    def __init__(self, parent=None, *args, **kwargs):
        ProgressReporter.__init__(self, *args, **kwargs)
        QObject.__init__(self, parent)

        self.__progress_bar = None
        self._text = "%p%"

    @property
    def progress_bar(self):
        return self.__progress_bar

    @progress_bar.setter
    def progress_bar(self, widget):
        self.__progress_bar = widget

        self.__set_maximum.connect(self.__progress_bar.setMaximum)
        self.__set_value.connect(self.__progress_bar.setValue)
        self.__set_text.connect(self.__progress_bar.setFormat)

        self.__progress_bar.setMaximum(self._maximum)
        self.__progress_bar.setValue(self._value)
        self.__progress_bar.setFormat(self._text)

    @ProgressReporter.maximum.setter
    def maximum(self, value):
        ProgressReporter.maximum.fset(self, value)
        self.__set_maximum.emit(int(value))

    @ProgressReporter.value.setter
    def value(self, value):
        ProgressReporter.value.fset(self, value)
        self.__set_value.emit(int(value))

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, value):
        self._text = value
        self.__set_text.emit(value)


class ProgressLogItemModel(QStandardItemModel):
    __row_appended = Signal()

    def __init__(self, parent=None, limit=1000, refresh=20):
        super().__init__(parent)

        self.limit = limit
        self.buffer = list()
        self.timer = QTimer()

        self.timer.setSingleShot(True)
        self.timer.setInterval(refresh)

        @helpers.make_slot()
        @helpers.connect_slot(self.__row_appended)
        def __on_row_appended():
            if not self.timer.isActive():
                self.timer.start()

        @helpers.make_slot()
        @helpers.connect_slot(self.timer.timeout)
        def __on_timer_timeout():
            self.__dump_buffer()

    def __dump_buffer(self):
        self.insertRows(self.rowCount(), len(self.buffer))  # Append rows for each item in the buffer

        # Set the items for each new row
        for offset, item in enumerate(self.buffer):
            self.setItem(self.rowCount() - len(self.buffer) + offset, 0, item)

        self.buffer.clear()  # Reset the buffer

    def __apply_limit(self):
        if self.rowCount() > self.limit:
            # Remove rows from the beginning, count being the number of rows over the limit
            self.removeRows(0, self.rowCount() - self.limit)

    def insertRows(self, row, count, _=None):
        super().insertRows(row, count)
        self.__apply_limit()

    def appendRow(self, item):
        # Append the QStandardItem to the internal list to be popped into the model on the next timeout
        self.buffer.append(item)
        self.__row_appended.emit()


class MultiProgressDialog(QDialog):
    # I have found the below refresh-rate for update to be the best at keeping up with
    # the monitor and still reducing flickering, 60 does work but is more noticeable
    update_refresh_rate = 50
    reporter_created = Signal(ProgressBarReporter)
    cancel_request = Signal()
    completed = Signal()
    cancel_confirmation_text = "Are you sure you want to cancel the current task?"
    cancel_confirmation_title = "Cancel Confirmation"

    def __init__(self, log_limit=1000, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.__allow_close = False
        self.__cancel_requested = False

        uic.loadUi(str((Path(__file__).parent / "ui/multi_progress_dialog.ui").resolve()), self)

        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        self.progress_bar_container_widget.setVisible(False)
        self.progress_bar_divider_line.setVisible(False)

        self.__main_reporter = ProgressBarReporter()
        self.__main_reporter.progress_bar = self.main_progress_bar
        self.__reporter_map = dict()
        self.__progress_log_item_model = ProgressLogItemModel(limit=log_limit)

        self.progress_log_list_view.setModel(self.__progress_log_item_model)

        self.cancel_button.clicked.connect(self.close)
        self.progress_log_list_view.installEventFilter(self)

        self.__bind_cancel_request_and_completed()
        self.__bind_auto_scroll_handlers()
        self.__bind_reporter_created()

    def eventFilter(self, source, event):
        if isinstance(source, QListView):
            if event.type() is QEvent.KeyPress and event.key() == Qt.Key_C and event.modifiers() & Qt.ControlModifier:
                rows = sorted(source.selectionModel().selectedRows())
                data = QMimeData()
                data.setText("\n".join(str(source.model().data(row)) for row in rows))

                QApplication.instance().clipboard().setMimeData(data)

                return True

        return False

    @property
    def main_reporter(self):
        return self.__main_reporter

    @property
    def cancel_requested(self):
        return self.__cancel_requested

    def __bind_cancel_request_and_completed(self):
        @helpers.make_slot()
        @helpers.connect_slot(self.cancel_request)
        def __on_cancel_request():
            self.__cancel_requested = True
            self.cancel_button.setEnabled(False)

        @helpers.make_slot()
        @helpers.connect_slot(self.completed)
        def __on_completed():
            self.__allow_close = True
            self.cancel_button.setText("Close")
            self.cancel_button.setEnabled(True)

    def __bind_auto_scroll_handlers(self):
        progress_log_scroll_bar = self.progress_log_list_view.verticalScrollBar()
        self.__scroll_bar_was_at_bottom = False

        @helpers.make_slot()
        @helpers.connect_slot(self.__progress_log_item_model.rowsAboutToBeInserted)
        def __on_progress_log_model_rows_about_to_be_inserted():
            self.__scroll_bar_was_at_bottom = progress_log_scroll_bar.value() == progress_log_scroll_bar.maximum()

        @helpers.make_slot(int, int)
        @helpers.connect_slot(progress_log_scroll_bar.rangeChanged)
        def __on_progress_log_scroll_bar_range_changed(_, max_value):
            if self.__scroll_bar_was_at_bottom:
                progress_log_scroll_bar.setValue(max_value)

    def __reporter_done_callback(self, reporter):
        progress_bar = self.__reporter_map[reporter]
        self.progress_bar_container_layout.removeWidget(progress_bar)
        progress_bar.deleteLater()
        del self.__reporter_map[reporter]

        if not any(self.__reporter_map.values()):
            self.progress_bar_container_widget.setVisible(False)
            self.progress_bar_divider_line.setVisible(False)

    def __bind_reporter_created(self):
        @helpers.make_slot(ProgressBarReporter)
        @helpers.connect_slot(self.reporter_created)
        def __on_reporter_created(reporter):
            initial_geometry = self.geometry()

            self.progress_bar_container_widget.setVisible(True)
            self.progress_bar_divider_line.setVisible(True)

            progress_bar = QProgressBar(self.progress_bar_container_widget)
            progress_bar.setAlignment(Qt.AlignCenter)

            reporter.progress_bar = progress_bar
            self.__reporter_map[reporter] = progress_bar
            self.progress_bar_container_layout.addWidget(progress_bar)
            progress_bar.show()

            current_geometry = self.geometry()
            current_geometry.moveCenter(initial_geometry.center())
            self.setGeometry(current_geometry)

    def keyPressEvent(self, event):
        if event.key() != Qt.Key_Escape:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        if self.__allow_close:
            super().closeEvent(event)
        elif self.__cancel_requested:
            event.ignore()
        else:
            event.ignore()

            confirm_response = QMessageBox.question(
                self,
                self.cancel_confirmation_title,
                self.cancel_confirmation_text,
                QMessageBox.Yes | QMessageBox.No
            )

            if confirm_response == QMessageBox.Yes:
                self.cancel_request.emit()

    def log(self, text):
        self.__progress_log_item_model.appendRow(QStandardItem(text))

    def reporter(self):
        progress_reporter = ProgressBarReporter(callback=self.__reporter_done_callback)
        self.__reporter_map[progress_reporter] = None

        self.reporter_created.emit(progress_reporter)

        return progress_reporter


if __name__ == "__main__":
    import sys
    import time

    from threading import Thread

    from qtpy.QtWidgets import QApplication, QPushButton

    app = QApplication([])
    window = MultiProgressDialog()
    window.setWindowTitle("Example Progress Reporter Dialog")

    add_reporter_button = QPushButton("Add Reporter", window)
    window.cancel_button_layout.addWidget(add_reporter_button)

    reporters = []
    reporter_count = 8

    window.main_reporter.maximum = reporter_count

    @helpers.make_slot()
    @helpers.connect_slot(add_reporter_button.clicked)
    def __add_reporter():
        reporters.append(window.reporter())
        reporters[-1].maximum = 100
        reporters[-1].value = min(len(reporters) / reporter_count * 100, 100)
        reporters[-1].text = f"Reporter {len(reporters)}: %p%"

        window.main_reporter.value = len(reporters)

        window.log(f"Added reporter {len(reporters)} with value of {reporters[-1].value}")

    window.show()

    def __add_reporters():
        for number in range(reporter_count):
            if window.cancel_requested:
                return

            time.sleep(0.5)
            __add_reporter()

    def __remove_reporters():
        for reporter in reporters:
            time.sleep(0.5)
            reporter.done()
            window.log(f"Removed reporter: {str(reporter)}")

    add_reporters_thread = Thread(target=__add_reporters, daemon=True)
    remove_reporters_thread = Thread(target=__remove_reporters, daemon=True)

    def __cancel():
        add_reporters_thread.join()
        remove_reporters_thread.start()
        remove_reporters_thread.join()

        window.completed.emit()

    cancel_thread = Thread(target=__cancel, daemon=True)

    add_reporters_thread.start()

    window.cancel_request.connect(cancel_thread.start)

    sys.exit(app.exec_())
