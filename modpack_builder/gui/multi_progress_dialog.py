import os

from pathlib import Path

from qtpy import uic
from qtpy.QtGui import QStandardItem
from qtpy.QtCore import Qt, QObject, Signal, QEvent, QMimeData
from qtpy.QtWidgets import QDialog, QMessageBox, QProgressBar, QListView, QApplication

import modpack_builder.gui.helpers as helpers

from modpack_builder.builder import ProgressReporter
from modpack_builder.gui.models import BufferedItemModel


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


class MultiProgressDialog(QDialog):
    reporter_created = Signal(ProgressBarReporter)
    cancel_request = Signal()
    completed = Signal()
    cancel_confirmation_text = "Are you sure you want to cancel the current task?"
    cancel_confirmation_title = "Cancel Confirmation"

    def __init__(self, parent=None, log_limit=1000, log_refresh=20, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self.__allow_close = False
        self.__cancel_requested = False

        uic.loadUi(str((Path(__file__).parent / "ui/multi_progress_dialog.ui").resolve()), self)

        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        self.progress_bar_container_widget.setVisible(False)
        self.progress_bar_divider_line.setVisible(False)

        self.__main_reporter = ProgressBarReporter()
        self.__main_reporter.progress_bar = self.main_progress_bar
        self.__reporter_map = dict()

        self.progress_log_item_model = BufferedItemModel(limit=log_limit, refresh=log_refresh)
        self.progress_log_list_view.setModel(self.progress_log_item_model)

        self.cancel_button.clicked.connect(self.close)
        self.progress_log_list_view.installEventFilter(self)

        self.__bind_cancel_request_and_completed()
        self.__bind_auto_scroll_handlers()
        self.__bind_reporter_created()

    def show(self):
        # Fix for PySide2 not putting the dialog in the middle of the parent like it should
        if os.environ["QT_API"] == "pyside2":
            geometry = self.geometry()
            geometry.moveCenter(self.parent().geometry().center())
            self.setGeometry(geometry)

        super().show()

    def eventFilter(self, source, event):
        if isinstance(source, QListView):
            if event.type() == QEvent.KeyPress and event.key() == Qt.Key_C and event.modifiers() & Qt.ControlModifier:
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
        @helpers.connect_slot(self.progress_log_item_model.rowsAboutToBeInserted)
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
        self.progress_log_item_model.appendRow(QStandardItem(text))

    def reporter(self):
        progress_reporter = ProgressBarReporter(callback=self.__reporter_done_callback)
        self.__reporter_map[progress_reporter] = None

        self.reporter_created.emit(progress_reporter)

        return progress_reporter
