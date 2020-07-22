import os
import sys
import base64
import binascii

from pathlib import Path

import markdown2

os.environ["QT_API"] = "pyqt5"

from qtpy.QtWidgets import QApplication, QMainWindow, QDialog, QMessageBox
from qtpy.QtWebEngineWidgets import QWebEnginePage
from qtpy.QtGui import QDesktopServices, QPixmap, QStandardItemModel, QStandardItem
from qtpy import QtCore
from qtpy import uic

import helpers

from builder2 import ModpackBuilder


class LockedWebEnginePage(QWebEnginePage):
    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        if nav_type == QWebEnginePage.NavigationTypeTyped:
            return super().acceptNavigationRequest(url, nav_type, is_main_frame)

        QDesktopServices.openUrl(url)
        return False


class MultiProgressDialog(QDialog):
    class ProgressBarReporter(ProgressReporter):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

            self.__progress_bar = None
            self._text = "%p%"

        @property
        def progress_bar(self):
            return self.__progress_bar

        @progress_bar.setter
        def progress_bar(self, widget):
            self.__progress_bar = widget
            self.__progress_bar.setMaximum(self._maximum)
            self.__progress_bar.setValue(self._value)
            self.__progress_bar.setFormat(self._text)

        @ProgressReporter.maximum.setter
        def maximum(self, value):
            ProgressReporter.maximum.fset(self, value)

            if self.__progress_bar:
                self.__progress_bar.setMaximum(value)

        @ProgressReporter.value.setter
        def value(self, value):
            ProgressReporter.value.fset(self, value)

            if self.__progress_bar:
                self.__progress_bar.setValue(value)

        @property
        def text(self):
            return self._text

        @text.setter
        def text(self, value):
            self._text = value

            if self.__progress_bar:
                self.__progress_bar.setFormat(value)

    reporter_created = QtCore.Signal(ProgressBarReporter)
    cancel_request = QtCore.Signal()
    cancel_completed = QtCore.Signal()
    cancel_confirmation_text = "Are you sure you want to cancel the current task?"
    cancel_confirmation_title = "Cancel Confirmation"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.__allow_close = False
        self.__cancel_requested = False

        uic.loadUi(str((Path(__file__).parent / "multiprogressdialog.ui").resolve()), self)

        self.__progress_bar_widgets = []
        self.__progress_log_scroll_repositioned = False
        self.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)

        self.progress_bar_container_widget.setVisible(False)
        self.progress_bar_divider_line.setVisible(False)

        self.__progress_log_model = QStandardItemModel()
        self.progress_log_list_view.setModel(self.__progress_log_model)
        self.progress_log_list_view.setFocusPolicy(QtCore.Qt.ClickFocus)

        self.cancel_button.clicked.connect(self.close)
        self.__bind_cancel_request_and_completed()
        self.__bind_auto_scroll_handlers()
        self.__bind_reporter_created()

    def __bind_cancel_request_and_completed(self):
        @helpers.make_slot()
        @helpers.connect_slot(self.cancel_request)
        def __on_cancel_request():
            self.__cancel_requested = True
            self.cancel_button.setEnabled(False)

        @helpers.make_slot()
        @helpers.connect_slot(self.cancel_completed)
        def __on_cancel_completed():
            self.__allow_close = True
            self.cancel_button.setText("Close")
            self.cancel_button.setEnabled(True)

    def __bind_auto_scroll_handlers(self):
        progress_log_scroll_bar = self.progress_log_list_view.verticalScrollBar()
        self.__scroll_bar_was_at_bottom = False

        @helpers.make_slot()
        @helpers.connect_slot(self.__progress_log_model.rowsAboutToBeInserted)
        def __on_progress_log_model_rows_about_to_be_inserted():
            self.__scroll_bar_was_at_bottom = progress_log_scroll_bar.value() == progress_log_scroll_bar.maximum()

        @helpers.make_slot(int, int)
        @helpers.connect_slot(progress_log_scroll_bar.rangeChanged)
        def __on_progress_log_scroll_bar_range_changed(_, max_value):
            if self.__scroll_bar_was_at_bottom:
                progress_log_scroll_bar.setValue(max_value)

    def keyPressEvent(self, event):
        if event.key() != QtCore.Qt.Key_Escape:
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

    def log(self, message):
        self.__progress_log_model.appendRow(QStandardItem(message))

    @property
    def cancel_requested(self):
        return self.__cancel_requested


class ModpackBuilderWindow(QMainWindow):
    __should_reset_profile_icon_path = False
    
    def __init__(self, builder, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.builder = builder

        uic.loadUi(str((Path(__file__).parent / "interface.ui").resolve()), self)

        # Fix for PyQt5
        if os.environ["QT_API"] == "pyqt5":
            self.setContentsMargins(9, 9, 9, 9)

        # Set up the QWebEngineView for the markdown information view
        self.information_tab_frame.layout().setContentsMargins(0, 0, 0, 0)
        self.information_web_engine_page = LockedWebEnginePage()
        self.information_web_engine_view.setPage(self.information_web_engine_page)
        self.information_web_engine_view.setContextMenuPolicy(QtCore.Qt.PreventContextMenu)
        self.information_web_engine_view.setZoomFactor(0.75)

        self.__bind_spin_boxes_and_sliders()
        self.__set_spin_box_and_slider_ranges()
        self.__bind_file_and_directory_picker_buttons()

    def __bind_spin_boxes_and_sliders(self):
        @helpers.make_slot(float)
        @helpers.connect_slot(self.allocated_memory_spin_box.valueChanged)
        def __on_allocated_memory_spin_box_value_changed(value):
            self.allocated_memory_slider.setValue(value * 2)
            self.builder.java_runtime_memory = value * 1024

        @helpers.make_slot(int)
        @helpers.connect_slot(self.allocated_memory_slider.valueChanged)
        def __on_allocated_memory_slider_value_changed(value):
            self.allocated_memory_spin_box.setValue(value / 2)

        @helpers.make_slot(int)
        @helpers.connect_slot(self.concurrent_requests_spin_box.valueChanged)
        def __on_concurrent_requests_spin_box_value_changed(value):
            self.builder.concurrent_requests = value

        @helpers.make_slot(int)
        @helpers.connect_slot(self.concurrent_downloads_spin_box.valueChanged)
        def __on_concurrent_downloads_spin_box_value_changed(value):
            self.builder.concurrent_downloads = value

    def __set_spin_box_and_slider_ranges(self):
        # Set the min and max range for concurrent requests and downloads sliders/spin boxes
        self.concurrent_requests_spin_box.setRange(1, ModpackBuilder._max_concurrent_requests)
        self.concurrent_requests_slider.setRange(1, ModpackBuilder._max_concurrent_requests)
        self.concurrent_downloads_spin_box.setRange(1, ModpackBuilder._max_concurrent_downloads)
        self.concurrent_downloads_slider.setRange(1, ModpackBuilder._max_concurrent_downloads)

        # Set the min and max range for the Java runtime allocated memory slider and spin box
        max_recommended_memory = ModpackBuilder._get_max_recommended_memory()
        self.allocated_memory_spin_box.setRange(1, max_recommended_memory)
        self.allocated_memory_slider.setRange(2, max_recommended_memory * 2)

    def __bind_file_and_directory_picker_buttons(self):
        @helpers.make_slot()
        @helpers.connect_slot(self.modpack_package_select_button.clicked)
        def __on_modpack_package_select_button_clicked():
            modpack_package_path = helpers.pick_file(
                parent=self,
                title="Select Modpack Package",
                path=Path(self.modpack_package_line_edit.text()),
                types=("Zip Archive (*.zip)",)
            ).resolve()

            self.modpack_package_line_edit.setText(str(modpack_package_path))


        @helpers.make_slot()
        @helpers.connect_slot(self.profile_icon_path_select_button.clicked)
        def __on_profile_icon_path_select_button_clicked():
            profile_icon_path = helpers.pick_file(
                parent=self,
                title="Select Profile Icon",
                path=Path(self.profile_icon_path_line_edit.text()),
                types=("Portable Network Graphics (*.png)",)
            ).resolve()

            self.profile_icon_path_line_edit.setText(str(profile_icon_path))
            self.__should_reset_profile_icon_path = False

            with open(profile_icon_path, "rb") as image:
                self.profile_icon_base64_line_edit.setText(base64.b64encode(image.read()).decode())

        @helpers.make_slot()
        @helpers.connect_slot(self.minecraft_directory_select_button.clicked)
        def __on_minecraft_directory_select_button_clicked():
            minecraft_directory = helpers.pick_directory(
                parent=self,
                title="Select Minecraft Directory",
                path=Path(self.minecraft_directory_line_edit.text())
            ).resolve()

            self.minecraft_directory_line_edit.setText(str(minecraft_directory))

        @helpers.make_slot()
        @helpers.connect_slot(self.minecraft_launcher_select_button.clicked)
        def __on_minecraft_launcher_select_button_clicked():
            minecraft_launcher_path = helpers.pick_file(
                parent=self,
                title="Select Minecraft Launcher",
                path=Path(self.minecraft_launcher_line_edit.text()),
                types=("Executable Files (*.exe)",)
            ).resolve()

            self.minecraft_launcher_line_edit.setText(str(minecraft_launcher_path))

    def __bind_other_synchronized_line_edits(self):
        @helpers.make_slot(str)
        @helpers.connect_slot(self.profile_icon_base64_line_edit.textChanged)
        def __on_profile_icon_base64_line_edit_text_changed(text):
            try:
                qpixmap = QPixmap()
                qpixmap.loadFromData(base64.b64decode(text), "png")
                qpixmap = qpixmap.scaledToHeight(
                    self.profile_icon_image_label.contentsRect().height(),
                    QtCore.Qt.SmoothTransformation
                )
                self.profile_icon_image_label.setPixmap(qpixmap)
                self.builder.profile_icon_base64 = text
            except binascii.Error:
                pass

            if self.__should_reset_profile_icon_path:
                self.profile_icon_path_line_edit.setText("")

            self.__should_reset_profile_icon_path = True

    def __load_values_from_builder(self):
        # self.show_information_markdown((Path(__file__).parent.parent / "modpack/README.md").resolve())

        # Set the value for concurrent requests and downloads spin boxes
        self.concurrent_requests_spin_box.setValue(self.builder.concurrent_requests)
        self.concurrent_downloads_spin_box.setValue(self.builder.concurrent_downloads)

        # Set default values
        self.allocated_memory_spin_box.setValue(self.builder.java_runtime_memory)
        self.minecraft_directory_line_edit.setText(str(self.builder.minecraft_directory))
        self.minecraft_launcher_line_edit.setText(str(self.builder.minecraft_launcher_path))

    def show_information_markdown(self, readme_path):
        with open((Path(__file__).parent / "markdown.css").resolve(), "r", encoding="utf-8") as markdown_css_file:
            markdown_css = markdown_css_file.read()

        with open(readme_path, "r", encoding="utf-8") as readme_file:
            readme_markdown = readme_file.read()

        readme_html = markdown2.markdown(
            readme_markdown,
            extras="cuddled-lists fenced-code-blocks smartypants spoiler strike tables tag-friendly task_list".split()
        )
        readme_html = f"""
        <html>
            <head>
                <style>
                    body {{
                        margin: 20px 30px;
                        user-select: none;
                    }}

                    {markdown_css}
                </style>
            </head>
            <body class='markdown-body'>
                {readme_html}
            </body>
        </html>
        """

        self.information_web_engine_page.setHtml(readme_html)


if __name__ == "__main__":
    app = QApplication([])
    builder = ModpackBuilder()
    window = ModpackBuilderWindow(builder)

    window.show()
    sys.exit(app.exec_())
