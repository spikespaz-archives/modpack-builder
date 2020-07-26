import os
import shlex
import base64
import binascii

from pathlib import Path

import markdown2

from qtpy.QtWidgets import QMainWindow, QLabel
from qtpy.QtWebEngineWidgets import QWebEnginePage
from qtpy.QtGui import QDesktopServices, QPixmap, QStandardItemModel, QStandardItem, QValidator
from qtpy import QtCore
from qtpy import uic

from . import helpers

from .builder import ModpackBuilder
from .multi_progress_dialog import MultiProgressDialog


class SlugValidator(QValidator):
    def __init__(self, parent=None, **kwargs):
        super().__init__(parent)

        self.__kwargs = kwargs

    def validate(self, text, cursor_pos):
        return (
            QValidator.Acceptable,
            helpers.slugify(text, **self.__kwargs),
            min(cursor_pos, len(text))
        )


class PathValidator(QValidator):
    def __init__(self, parent=None, file=False, extensions=None):
        super().__init__(parent)

        self.__file = file
        self.__extensions = extensions

    def validate(self, text, cursor_pos):
        path = Path(text)
        validity = None

        if not path.exists():
            if path.parent.exists() and path.parent.is_dir():
                # If the parent directory exists the path has been valid until the last part was added.
                # The state should be intermediate because it could be a typo or in-between changes.
                validity = QValidator.Intermediate
            else:
                # The parent either doesn't exist or is a file.
                # Return an invalid state to prevent the user from typing and not realizing the mistake.
                validity = QValidator.Invalid
        elif self.__file and path.is_file():
            if self.__extensions and (path.suffix in self.__extensions or "".join(path.suffixes) in self.__extensions):
                validity = QValidator.Acceptable
            elif self.__extensions:
                # The user probably hasn't typed the extension yet, so an intermediate state is returned.
                # This branch won't be run if `self.__extensions` contains an empty string,
                # so that the user can match any filename without an extension.
                validity = QValidator.Intermediate
            else:
                # No extensions provided to match, any file is acceptable.
                validity = QValidator.Acceptable
        elif self.__file and path.is_dir():
            # The current text is probably a parent of the final file path.
            validity = QValidator.Intermediate
        elif path.is_dir():
            # The validator is not expected to match a file and a directory is acceptable.
            validity = QValidator.Acceptable

        # If the below assertion fails I have made a mistake and did not predict some form of input.
        assert validity is not None
        return validity, text, cursor_pos


class LockedWebEnginePage(QWebEnginePage):
    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        if nav_type == QWebEnginePage.NavigationTypeTyped:
            return super().acceptNavigationRequest(url, nav_type, is_main_frame)

        QDesktopServices.openUrl(url)
        return False


class ModpackBuilderWindow(QMainWindow):
    __profile_id_length_limit = 32

    def __init__(self, builder, *args, **kwargs):
        super().__init__(*args, **kwargs)

        uic.loadUi(str((Path(__file__).parent / "ui/modpack_builder_window.ui").resolve()), self)

        self.__last_modpack_package_path = None
        self.__should_reset_profile_icon_path = False

        self.builder = builder

        # Fix for PyQt5
        if os.environ["QT_API"] == "pyqt5":
            self.setContentsMargins(9, 9, 9, 9)

        # Fix for the lack of a widthForHeight method of QWidget
        def __on_profile_icon_image_label_resize_event(event):
            self.profile_icon_image_label.setMinimumWidth(event.size().height())
            self.profile_icon_image_label.setMaximumWidth(event.size().height())
            QLabel.resizeEvent(self.profile_icon_image_label, event)

        self.profile_icon_image_label.resizeEvent = __on_profile_icon_image_label_resize_event

        # Set up the QWebEngineView for the markdown information view
        self.information_tab_frame.layout().setContentsMargins(0, 0, 0, 0)
        self.information_web_engine_page = LockedWebEnginePage()
        self.information_web_engine_view.setPage(self.information_web_engine_page)
        self.information_web_engine_view.setContextMenuPolicy(QtCore.Qt.PreventContextMenu)
        self.information_web_engine_view.setZoomFactor(0.75)

        self.__loading_priority_item_model = QStandardItemModel()
        self.loading_priority_list_view.setModel(self.__loading_priority_item_model)

        self.modpack_package_line_edit.setValidator(PathValidator(file=True, extensions=(".zip",)))
        self.profile_id_line_edit.setValidator(SlugValidator(size=self.__profile_id_length_limit))

        self.__set_spin_box_and_slider_ranges()
        self.__bind_spin_boxes_and_sliders()
        self.__bind_file_and_directory_picker_buttons()
        self.__bind_synchronized_line_edits()

        self.__load_values_from_builder()

    def __bind_spin_boxes_and_sliders(self):
        @helpers.make_slot(float)
        @helpers.connect_slot(self.client_allocated_memory_spin_box.valueChanged)
        def __on_client_allocated_memory_spin_box_value_changed(value):
            self.client_allocated_memory_slider.setValue(int(value * 2))
            self.builder.client_allocated_memory = value

        @helpers.make_slot(int)
        @helpers.connect_slot(self.client_allocated_memory_slider.valueChanged)
        def __on_client_allocated_memory_slider_value_changed(value):
            self.client_allocated_memory_spin_box.setValue(value / 2)
        
        @helpers.make_slot(float)
        @helpers.connect_slot(self.server_allocated_memory_spin_box.valueChanged)
        def __on_server_allocated_memory_spin_box_value_changed(value):
            self.server_allocated_memory_slider.setValue(int(value * 2))
            self.builder.server_allocated_memory = value

        @helpers.make_slot(int)
        @helpers.connect_slot(self.server_allocated_memory_slider.valueChanged)
        def __on_server_allocated_memory_slider_value_changed(value):
            self.server_allocated_memory_spin_box.setValue(value / 2)

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
        maximum_memory = ModpackBuilder._get_maximum_memory()
        self.client_allocated_memory_spin_box.setRange(2, maximum_memory)
        self.client_allocated_memory_slider.setRange(4, maximum_memory * 2)
        self.server_allocated_memory_spin_box.setRange(2, maximum_memory)
        self.server_allocated_memory_slider.setRange(4, maximum_memory * 2)

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
            self.modpack_package_line_edit.editingFinished.emit()

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
        @helpers.connect_slot(self.profiles_directory_select_button.clicked)
        def __on_profiles_directory_select_button_clicked():
            minecraft_directory = helpers.pick_directory(
                parent=self,
                title="Select Minecraft Profiles Directory",
                path=Path(self.profiles_directory_line_edit.text())
            ).resolve()

            self.profiles_directory_line_edit.setText(str(minecraft_directory))

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

    def __bind_synchronized_line_edits(self):
        @helpers.make_slot()
        @helpers.connect_slot(self.modpack_package_line_edit.editingFinished)
        def __on_modpack_package_line_edit_editing_finished():
            # Due to an old bug where this signal is fired multiple times, first when the user presses Enter and then
            # when the widget loses focus (https://bugreports.qt.io/browse/QTBUG-40),
            # the second call of this slot must be ignored if no changes have been tracked.
            # The path is resolved to ensure that the modpack is not reloaded if for whatever reason two equivalent
            # relative or absolute directories replace each other.
            if (path := Path(self.modpack_package_line_edit.text()).resolve()) == self.__last_modpack_package_path:
                return

            self.__last_modpack_package_path = path

            # No errors are expected from this relating to the path because the validator should have
            # already taken care of that. Should be safe.
            self.__load_package(path)

        # *** Information ***

        # *** Profile Options ***

        @helpers.make_slot(str)
        @helpers.connect_slot(self.profile_name_line_edit.textChanged)
        def __on_profile_name_line_edit_text_changed(text):
            # Conversion of name to slug is handled by the validator.
            # No need to call 'helpers.slugify' twice.
            self.profile_id_line_edit.setText(text)
            self.builder.manifest.profile_name = text

        @helpers.make_slot(str)
        @helpers.connect_slot(self.profile_id_line_edit.textChanged)
        def __on_profile_id_line_edit_text_changed(text):
            profile_directory = Path(self.builder.profiles_directory / text)
            self.profile_directory_line_edit.setText(str(profile_directory))
            self.builder.manifest.profile_id = text
            self.builder.manifest.profile_directory = profile_directory

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

        # ***CurseForge Mods***

        # ***External Mods***

        # ***Loading Priority***

        # ***Minecraft Forge***

        # ***Java Runtime***

        @helpers.make_slot(str)
        @helpers.connect_slot(self.client_jvm_arguments_text_edit.textChanged)
        def __on_client_jvm_arguments_text_edit_text_changed():
            self.builder.manifest.client_java_args = " ".join(
                shlex.split(self.client_jvm_arguments_text_edit.toPlainText())
            )

        @helpers.make_slot(str)
        @helpers.connect_slot(self.server_jvm_arguments_text_edit.textChanged)
        def __on_server_jvm_arguments_text_edit_text_changed():
            self.builder.manifest.server_java_args = " ".join(
                shlex.split(self.server_jvm_arguments_text_edit.toPlainText())
            )

        @helpers.make_slot(str)
        @helpers.connect_slot(self.java_download_url_mac_line_edit.textChanged)
        def __on_java_download_url_mac_line_edit_text_changed(text):
            self.builder.manifest.java_downloads.darwin = text

        @helpers.make_slot(str)
        @helpers.connect_slot(self.java_download_url_linux_line_edit.textChanged)
        def __on_java_download_url_linux_line_edit_text_changed(text):
            self.builder.manifest.java_downloads.linux = text

        @helpers.make_slot(str)
        @helpers.connect_slot(self.java_download_url_windows_line_edit.textChanged)
        def __on_java_download_url_windows_line_edit_text_changed(text):
            self.builder.manifest.java_downloads.windows = text

        # ***External Resources***

        # *** Application Settings ***

        @helpers.make_slot(str)
        @helpers.connect_slot(self.minecraft_directory_line_edit.textChanged)
        def __on_minecraft_directory_line_edit_text_changed(text):
            self.builder.minecraft_directory = Path(text)

        @helpers.make_slot(str)
        @helpers.connect_slot(self.profiles_directory_line_edit.textChanged)
        def __on_profiles_directory_line_edit_text_changed(text):
            self.builder.profiles_directory = Path(text)

        @helpers.make_slot(str)
        @helpers.connect_slot(self.minecraft_launcher_line_edit.textChanged)
        def __on_minecraft_launcher_line_edit_text_changed(text):
            self.builder.minecraft_launcher_path = Path(text)

    def __load_package(self, path):
        progress_dialog = MultiProgressDialog(parent=self)

        progress_dialog.setWindowTitle("Extracting Modpack Package")

        self.builder.reporter = progress_dialog.main_reporter
        self.builder.logger = progress_dialog.log

        @helpers.make_slot()
        @helpers.connect_slot(progress_dialog.completed)
        def __on_progress_dialog_completed():
            self.__load_values_from_builder()
            progress_dialog.close()

        @helpers.make_thread(daemon=True)
        def __builder_load_package_thread():
            self.builder.remove_extracted()
            self.builder.load_package(path)
            progress_dialog.completed.emit()

        # @helpers.make_slot()
        # @helpers.connect_slot(progress_dialog.cancel_request)
        # def __on_cancel_request():
        #     progress_dialog.completed.emit()

        progress_dialog.show()
        __builder_load_package_thread.start()

    def __load_values_from_builder(self):
        # *** Information ***

        if self.builder.readme_path:
            self.show_information_markdown(self.builder.readme_path)

        # *** Profile Options ***

        if self.builder.manifest.profile_name:
            self.profile_name_line_edit.setText(self.builder.manifest.profile_name)

        if self.builder.manifest.profile_id:
            self.profile_id_line_edit.setText(self.builder.manifest.profile_id)

        if self.builder.manifest.version_label:
            if self.version_label_combo_box.findText(self.builder.manifest.version_label) == -1:
                self.version_label_combo_box.addItem(self.builder.manifest.version_label)

            self.version_label_combo_box.setCurrentText(self.builder.manifest.version_label)

        if self.builder.manifest.profile_icon:
            self.profile_icon_base64_line_edit.setText(self.builder.manifest.profile_icon)

        # ***CurseForge Mods***

        # ***External Mods***

        # ***Loading Priority***

        for identifier in self.builder.manifest.load_priority:
            self.__loading_priority_item_model.appendRow(QStandardItem(identifier))

        # ***Minecraft Forge***

        # ***Java Runtime***

        self.client_allocated_memory_spin_box.setValue(self.builder.client_allocated_memory)
        self.server_allocated_memory_spin_box.setValue(self.builder.server_allocated_memory)

        if self.builder.manifest.client_java_args:
            self.client_jvm_arguments_text_edit.setPlainText(
                "    ".join(shlex.split(self.builder.manifest.client_java_args))
            )
        if self.builder.manifest.server_java_args:
            self.server_jvm_arguments_text_edit.setPlainText(
                "    ".join(shlex.split(self.builder.manifest.server_java_args))
            )

        if self.builder.manifest.java_downloads.darwin:
            self.java_download_url_mac_line_edit.setText(self.builder.manifest.java_downloads.darwin)
        if self.builder.manifest.java_downloads.linux:
            self.java_download_url_linux_line_edit.setText(self.builder.manifest.java_downloads.linux)
        if self.builder.manifest.java_downloads.windows:
            self.java_download_url_windows_line_edit.setText(self.builder.manifest.java_downloads.windows)

        # ***External Resources***

        # *** Application Settings ***

        if self.builder.minecraft_directory:
            self.minecraft_directory_line_edit.setText(str(self.builder.minecraft_directory))

        if self.builder.profiles_directory:
            self.profiles_directory_line_edit.setText(str(self.builder.profiles_directory))

        if self.builder.minecraft_launcher_path:
            self.minecraft_launcher_line_edit.setText(str(self.builder.minecraft_launcher_path))

        # Set the value for concurrent requests and downloads spin boxes
        self.concurrent_requests_spin_box.setValue(self.builder.concurrent_requests)
        self.concurrent_downloads_spin_box.setValue(self.builder.concurrent_downloads)

    def show_information_markdown(self, path):
        with open((Path(__file__).parent / "ui/markdown.css").resolve(), "r", encoding="utf-8") as markdown_css_file:
            markdown_css = markdown_css_file.read()

        with open(path, "r", encoding="utf-8") as readme_file:
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
