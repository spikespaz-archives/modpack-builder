import os
import shlex
import base64
import binascii
import subprocess

from pathlib import Path
from subprocess import Popen

import markdown2

from qtpy import uic
from qtpy.QtGui import QDesktopServices, QPixmap
from qtpy.QtWidgets import QMainWindow, QHeaderView
from qtpy.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from qtpy.QtCore import Qt, QModelIndex, QSysInfo, QEvent, QItemSelection

from .. import utilities

from ..builder import ModpackBuilder
from ..curseforge import ReleaseType

from . import helpers

from .validators import SlugValidator, PathValidator
from .multi_progress_dialog import MultiProgressDialog
from .models import LoadingPriorityTableModel, CurseForgeModsTableModel


class LockedWebEnginePage(QWebEnginePage):
    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        if nav_type == QWebEnginePage.NavigationTypeTyped:
            return super().acceptNavigationRequest(url, nav_type, is_main_frame)

        QDesktopServices.openUrl(url)
        return False


class ModpackBuilderWindow(QMainWindow):
    # The length limit for profile IDs is imposed without any real reason other than keeping
    # the directory names tidy and preventing auto-generated folder names from getting
    # unwieldy due to potentially abhorrently long modpack names.
    profile_id_length_limit = 32

    def __init__(self, builder, *args, **kwargs):
        super().__init__(*args, **kwargs)

        print(f"QT_API = {os.environ['QT_API']}")

        uic.loadUi(str((Path(__file__).parent / "ui/modpack_builder_window.ui").resolve()), self)

        self.__last_modpack_package_path = None
        self.__should_reset_profile_icon_path = False

        self.builder = builder

        # Fix for PyQt5
        if os.environ["QT_API"] == "pyqt5":
            self.setContentsMargins(9, 9, 9, 9)

        self.release_type_combo_box.addItems(value.title() for value in ReleaseType.values)

        self.loading_priority_table_model = LoadingPriorityTableModel(
            self.builder,
            parent=self.loading_priority_table_view
        )
        self.loading_priority_table_view.setModel(self.loading_priority_table_model)

        self.loading_priority_table_view.horizontalHeader().setStretchLastSection(True)
        self.loading_priority_table_view.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

        self.curseforge_mods_table_model = CurseForgeModsTableModel(
            self.builder,
            parent=self.curseforge_mods_table_view
        )
        self.curseforge_mods_table_view.setModel(self.curseforge_mods_table_model)

        self.curseforge_mods_table_view.horizontalHeader().setStretchLastSection(True)
        self.curseforge_mods_table_view.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

        self.__create_information_view()
        self.__install_event_filters()
        self.__set_text_input_validators()
        self.__set_spin_box_and_slider_ranges()
        self.__set_widget_stylesheets()
        self.__bind_spin_boxes_and_sliders()
        self.__bind_file_and_directory_picker_buttons()
        self.__bind_action_buttons()
        self.__bind_synchronized_controls()
        self.__bind_table_selection_changes()

        self.__load_values_from_builder()

    def eventFilter(self, source, event):
        if source is self.curseforge_mods_table_view:
            if event.type() == QEvent.Resize:
                self.curseforge_mods_table_view.setColumnWidth(0, event.size().width() * (3 / 13))
                self.curseforge_mods_table_view.setColumnWidth(1, event.size().width() * (4 / 13))
                self.curseforge_mods_table_view.setColumnWidth(2, event.size().width() * (1 / 13))

        elif source is self.loading_priority_table_view:
            if event.type() == QEvent.Resize:
                # Fix for no sensible way of specifying column size stretch ratios
                # Resize all columns except the last leaving the stretch logic in Qt to do the work (prevents scrollbar)
                self.loading_priority_table_view.setColumnWidth(0, event.size().width() * (3 / 12))
                self.loading_priority_table_view.setColumnWidth(1, event.size().width() * (4 / 12))

        elif source is self.profile_icon_image_label:
            if event.type() == QEvent.Resize:
                # Keep the preview image square because 'widthForHeight' is not an option
                self.profile_icon_image_label.setMinimumWidth(event.size().height())
                self.profile_icon_image_label.setMaximumWidth(event.size().height())

        return False  # Default to allow the event to be handled further (order of the filters is unknown)

    def __create_information_view(self):
        self.information_web_engine_view = QWebEngineView(self.information_tab_frame)
        self.information_web_engine_page = LockedWebEnginePage(self.information_web_engine_view)

        self.information_tab_frame_layout.addWidget(self.information_web_engine_view)
        self.information_web_engine_view.setPage(self.information_web_engine_page)
        self.information_web_engine_view.setContextMenuPolicy(Qt.PreventContextMenu)
        self.information_web_engine_view.setZoomFactor(0.75)

    def __install_event_filters(self):
        self.profile_icon_image_label.installEventFilter(self)
        self.curseforge_mods_table_view.installEventFilter(self)
        self.loading_priority_table_view.installEventFilter(self)

    def __set_text_input_validators(self):
        # File and directory path edits
        self.modpack_package_line_edit.setValidator(PathValidator(file=True, extensions=(".zip",)))
        self.profile_icon_path_line_edit.setValidator(PathValidator(file=True, extensions=(".png",)))
        self.minecraft_directory_line_edit.setValidator(PathValidator())
        self.minecraft_launcher_line_edit.setValidator(PathValidator(file=True, extensions=(".exe",)))

        # Identifier / slug edits
        self.profile_id_line_edit.setValidator(SlugValidator(size=self.profile_id_length_limit, rstrip=True))
        self.curseforge_mod_identifier_line_edit.setValidator(SlugValidator())
        self.external_mod_identifier_line_edit.setValidator(SlugValidator())
        self.loading_priority_mod_identifier_line_edit.setValidator(SlugValidator())

    def __set_spin_box_and_slider_ranges(self):
        # Set the min and max range for concurrent requests and downloads sliders/spin boxes
        self.concurrent_requests_spin_box.setRange(1, ModpackBuilder.max_concurrent_requests)
        self.concurrent_requests_slider.setRange(1, ModpackBuilder.max_concurrent_requests)
        self.concurrent_downloads_spin_box.setRange(1, ModpackBuilder.max_concurrent_downloads)
        self.concurrent_downloads_slider.setRange(1, ModpackBuilder.max_concurrent_downloads)

        # Set the min and max range for the Java runtime allocated memory slider and spin box
        maximum_memory = ModpackBuilder.get_maximum_memory()
        self.client_allocated_memory_spin_box.setRange(ModpackBuilder.min_recommended_memory, maximum_memory)
        self.client_allocated_memory_slider.setRange(ModpackBuilder.min_recommended_memory * 2, maximum_memory * 2)
        self.server_allocated_memory_spin_box.setRange(ModpackBuilder.min_recommended_memory, maximum_memory)
        self.server_allocated_memory_slider.setRange(ModpackBuilder.min_recommended_memory * 2, maximum_memory * 2)

    def __set_widget_stylesheets(self):
        self.profile_icon_image_label.setStyleSheet(
            f"QLabel {{ background: #262626 }}"
        )

        # Fix for the bottom border missing on the table view's header, only on Windows 10
        if QSysInfo().windowsVersion() == QSysInfo.WV_WINDOWS10:
            table_view_header_css = """
                    QHeaderView::section {
                        border-style: solid;
                        border-color: #D8D8D8;
                        border-top-width: 0px;
                        border-bottom-width: 1px;
                        border-left-width: 0px;
                        border-right-width: 1px;
                    }
                    """

            self.curseforge_mods_table_view.horizontalHeader().setStyleSheet(table_view_header_css)
            self.external_mods_table_view.horizontalHeader().setStyleSheet(table_view_header_css)
            self.loading_priority_table_view.horizontalHeader().setStyleSheet(table_view_header_css)

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

    def __bind_file_and_directory_picker_buttons(self):
        @helpers.make_slot()
        @helpers.connect_slot(self.modpack_package_select_button.clicked)
        def __on_modpack_package_select_button_clicked():
            modpack_package_path = helpers.pick_file(
                parent=self,
                title="Select Modpack Package",
                path=Path(self.modpack_package_line_edit.text()),
                types=("Zip Archive (*.zip)",)
            )

            if modpack_package_path is None:
                return

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
            )

            if profile_icon_path is None:
                return

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
            )

            if minecraft_directory is None:
                return

            self.minecraft_directory_line_edit.setText(str(minecraft_directory))

        @helpers.make_slot()
        @helpers.connect_slot(self.profiles_directory_select_button.clicked)
        def __on_profiles_directory_select_button_clicked():
            profiles_directory = helpers.pick_directory(
                parent=self,
                title="Select Minecraft Profiles Directory",
                path=Path(self.profiles_directory_line_edit.text())
            )

            if profiles_directory is None:
                return

            self.profiles_directory_line_edit.setText(str(profiles_directory))

        @helpers.make_slot()
        @helpers.connect_slot(self.minecraft_launcher_select_button.clicked)
        def __on_minecraft_launcher_select_button_clicked():
            minecraft_launcher_path = helpers.pick_file(
                parent=self,
                title="Select Minecraft Launcher",
                path=Path(self.minecraft_launcher_line_edit.text()),
                types=("Executable Files (*.exe)",)
            )

            if minecraft_launcher_path is None:
                return

            self.minecraft_launcher_line_edit.setText(str(minecraft_launcher_path))

    def __bind_action_buttons(self):
        # *** Window General Actions ***

        @helpers.make_slot()
        @helpers.connect_slot(self.install_or_update_client_button.clicked)
        def __on_install_or_update_client_button_clicked():
            pass

        @helpers.make_slot()
        @helpers.connect_slot(self.install_or_update_server_button.clicked)
        def __on_install_or_update_server_button_clicked():
            pass

        @helpers.make_slot()
        @helpers.connect_slot(self.launch_minecraft_button.clicked)
        def __on_launch_minecraft_button_clicked():
            Popen(
                self.builder.minecraft_launcher_path,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                close_fds=True,
                creationflags=(
                    subprocess.CREATE_NEW_PROCESS_GROUP |
                    subprocess.DETACHED_PROCESS |
                    subprocess.CREATE_BREAKAWAY_FROM_JOB
                )
            )

        @helpers.make_slot()
        @helpers.connect_slot(self.export_package_button.clicked)
        def __on_export_package_button_clicked():
            import json

            with open(Path("./dumped-manifest.json"), "w") as manifest_file:
                json.dump(self.builder.manifest.dictionary, manifest_file, indent=2)

        # *** Profile Options ***

        @helpers.make_slot()
        @helpers.connect_slot(self.update_profile_button.clicked)
        def __on_update_profile_button_clicked():
            pass

        # *** CurseForge Mods ***

        @helpers.make_slot()
        @helpers.connect_slot(self.curseforge_mod_add_button.clicked)
        def __on_curseforge_mod_add_button_clicked():
            text = self.curseforge_mod_identifier_line_edit.text()

            if not self.builder.add_curseforge_mod(text):
                return

            self.curseforge_mods_table_model.insertRow(0)
            self.curseforge_mods_table_model.setData(self.curseforge_mods_table_model.index(0, 0), text)
            self.curseforge_mods_table_view.selectRow(0)

        @helpers.make_slot()
        @helpers.connect_slot(self.curseforge_mod_remove_button.clicked)
        def __on_curseforge_mod_remove_button_clicked():
            if not (selection := self.curseforge_mods_table_view.selectionModel()).hasSelection():
                return

            selected_rows = sorted(index.row() for index in selection.selectedRows())
            contiguous_rows = utilities.sequence_groups(selected_rows)

            # Select the next row before removal otherwise the index must be recalculated
            self.curseforge_mods_table_view.selectRow(contiguous_rows[-1][-1] + 1)

            for rows in reversed(contiguous_rows):
                self.curseforge_mods_table_model.removeRows(min(rows), len(rows))

        @helpers.make_slot()
        @helpers.connect_slot(self.curseforge_mod_update_button.clicked)
        def __on_curseforge_mod_update_button_clicked():
            pass

        @helpers.make_slot()
        @helpers.connect_slot(self.curseforge_mod_disable_button.clicked)
        def __on_curseforge_mod_disable_button_clicked():
            pass

        # *** External Mods ***

        @helpers.make_slot()
        @helpers.connect_slot(self.external_mod_add_button.clicked)
        def __on_external_mod_add_button_clicked():
            pass

        @helpers.make_slot()
        @helpers.connect_slot(self.external_mod_remove_button.clicked)
        def __on_external_mod_remove_button_clicked():
            pass

        @helpers.make_slot()
        @helpers.connect_slot(self.external_mod_update_button.clicked)
        def __on_external_mod_update_button_clicked():
            pass

        @helpers.make_slot()
        @helpers.connect_slot(self.external_mod_disable_button.clicked)
        def __on_external_mod_disable_button_clicked():
            pass

        # *** Loading Priority ***

        @helpers.make_slot()
        @helpers.connect_slot(self.loading_priority_add_button.clicked)
        def __on_loading_priority_add_button_clicked():
            text = self.loading_priority_mod_identifier_line_edit.text()

            self.loading_priority_table_model.insertRow(0)
            self.loading_priority_table_model.setData(self.loading_priority_table_model.index(0, 0), text)
            self.loading_priority_table_view.selectRow(0)

        @helpers.make_slot()
        @helpers.connect_slot(self.loading_priority_remove_button.clicked)
        def __on_loading_priority_remove_button_clicked():
            if not (selection := self.loading_priority_table_view.selectionModel()).hasSelection():
                return

            selected_rows = sorted(index.row() for index in selection.selectedRows())
            contiguous_rows = utilities.sequence_groups(selected_rows)

            # Select the next row before removal otherwise the index must be recalculated
            self.loading_priority_table_view.selectRow(contiguous_rows[-1][-1] + 1)

            for rows in reversed(contiguous_rows):
                self.loading_priority_table_model.removeRows(min(rows), len(rows))

        def __load_priority_list_view_shift_rows(selection, offset):
            selected_rows = sorted(index.row() for index in selection.selectedRows())
            contiguous_rows = utilities.sequence_groups(selected_rows)

            parent_index = QModelIndex()

            for rows in contiguous_rows:
                self.loading_priority_table_model.moveRows(
                    parent_index,
                    min(rows),
                    len(rows),
                    parent_index,
                    min(rows) + offset if offset < 0 else max(rows) + offset + 1
                )

        @helpers.make_slot()
        @helpers.connect_slot(self.loading_priority_increase_button.clicked)
        def __on_loading_priority_increase_button_clicked():
            if not (selection := self.loading_priority_table_view.selectionModel()).hasSelection():
                return

            __load_priority_list_view_shift_rows(selection, -1)

        @helpers.make_slot()
        @helpers.connect_slot(self.loading_priority_decrease_button.clicked)
        def __on_loading_priority_decrease_button_button_clicked():
            if not (selection := self.loading_priority_table_view.selectionModel()).hasSelection():
                return

            __load_priority_list_view_shift_rows(selection, 1)

        # *** Minecraft Forge ***

        @helpers.make_slot()
        @helpers.connect_slot(self.minecraft_forge_install_client_button.clicked)
        def __on_minecraft_forge_install_client_button_clicked():
            pass

        @helpers.make_slot()
        @helpers.connect_slot(self.minecraft_forge_install_server_button.clicked)
        def __on_minecraft_forge_install_server_button_clicked():
            pass

        # *** Java Runtime ***

        @helpers.make_slot()
        @helpers.connect_slot(self.java_runtime_download_button.clicked)
        def __on_java_runtime_download_button_clicked():
            pass

    def __bind_synchronized_controls(self):
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
            # No need to call 'utilities.slugify' twice.
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
                pixmap = QPixmap()
                pixmap.loadFromData(base64.b64decode(text), "png")
                pixmap = pixmap.scaledToHeight(
                    self.profile_icon_image_label.contentsRect().height(),
                    Qt.SmoothTransformation
                )
                self.profile_icon_image_label.setPixmap(pixmap)
                self.builder.manifest.profile_icon = text
            except binascii.Error:
                pass

            if self.__should_reset_profile_icon_path:
                self.profile_icon_path_line_edit.setText(None)

            self.__should_reset_profile_icon_path = True

        # ***CurseForge Mods***

        @helpers.make_slot(str)
        @helpers.connect_slot(self.curseforge_mod_identifier_line_edit.textChanged)
        def __on_curseforge_mod_identifier_line_edit_text_changed(text):
            if text and text not in self.builder.curseforge_files:
                self.curseforge_mod_add_button.setEnabled(True)
            else:
                self.curseforge_mod_add_button.setEnabled(False)

            if text in self.curseforge_mods_table_model.identifiers:
                # Assumes that nothing is already selected
                self.curseforge_mods_table_view.selectRow(self.curseforge_mods_table_model.identifiers.index(text))

        @helpers.make_slot(str)
        @helpers.connect_slot(self.minecraft_versions_line_edit.textChanged)
        def __on_minecraft_versions_line_edit_text_changed(text):
            self.builder.manifest.game_versions.clear()

            for version in text.split(","):
                if version := version.strip():
                    self.builder.manifest.game_versions.add(version)

        @helpers.make_slot(str)
        @helpers.connect_slot(self.release_type_combo_box.currentTextChanged)
        def __on_release_type_combo_box_current_text_changed(text):
            self.builder.manifest.release_preference = ReleaseType(text.lower())

        # ***External Mods***

        # ***Loading Priority***

        @helpers.make_slot(str)
        @helpers.connect_slot(self.loading_priority_mod_identifier_line_edit.textChanged)
        def __on_loading_priority_mod_identifier_line_edit_text_changed(text):
            if (
                text and (
                    text in self.builder.curseforge_mods or
                    text in self.builder.manifest.external_mods
                ) and
                text not in self.builder.manifest.load_priority
            ):
                self.loading_priority_add_button.setEnabled(True)
            else:
                self.loading_priority_add_button.setEnabled(False)

            if text in self.builder.manifest.load_priority:
                # Assumes that nothing is already selected
                self.loading_priority_table_view.selectRow(self.builder.manifest.load_priority.index(text))

        # ***Minecraft Forge***

        # ***Java Runtime***

        @helpers.make_slot(str)
        @helpers.connect_slot(self.client_jvm_arguments_text_edit.textChanged)
        def __on_client_jvm_arguments_text_edit_text_changed():
            self.builder.manifest.client_java_args = shlex.split(self.client_jvm_arguments_text_edit.toPlainText())

        @helpers.make_slot(str)
        @helpers.connect_slot(self.server_jvm_arguments_text_edit.textChanged)
        def __on_server_jvm_arguments_text_edit_text_changed():
            self.builder.manifest.server_java_args = shlex.split(self.server_jvm_arguments_text_edit.toPlainText())

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

    def __bind_table_selection_changes(self):
        @helpers.make_slot(QItemSelection, QItemSelection)
        @helpers.connect_slot(self.loading_priority_table_view.selectionModel().selectionChanged)
        def __on_loading_priority_table_view_selection_model_selection_changed(*_):
            selected_rows = tuple(
                index.row() for index in self.loading_priority_table_view.selectionModel().selectedRows()
            )

            if len(selected_rows) == 0:
                self.loading_priority_mod_identifier_line_edit.setText(None)
                self.loading_priority_mod_identifier_line_edit.setEnabled(True)
            elif len(selected_rows) == 1:
                self.loading_priority_mod_identifier_line_edit.setText(
                    self.builder.manifest.load_priority[selected_rows[-1]]
                )
                self.loading_priority_mod_identifier_line_edit.setEnabled(True)
            else:
                self.loading_priority_mod_identifier_line_edit.setText(None)
                self.loading_priority_mod_identifier_line_edit.setEnabled(False)

            if len(selected_rows):
                self.loading_priority_remove_button.setEnabled(True)
                self.loading_priority_increase_button.setEnabled(True)
                self.loading_priority_decrease_button.setEnabled(True)
            else:
                self.loading_priority_remove_button.setEnabled(False)
                self.loading_priority_increase_button.setEnabled(False)
                self.loading_priority_decrease_button.setEnabled(False)

        @helpers.make_slot(QItemSelection, QItemSelection)
        @helpers.connect_slot(self.curseforge_mods_table_view.selectionModel().selectionChanged)
        def __on_curseforge_mods_table_view_selection_model_selection_changed(*_):
            selected_rows = tuple(
                index.row() for index in self.curseforge_mods_table_view.selectionModel().selectedRows()
            )

            if len(selected_rows) == 0:
                self.curseforge_mod_identifier_line_edit.setText(None)
                self.curseforge_mod_identifier_line_edit.setEnabled(True)
            elif len(selected_rows) == 1:
                self.curseforge_mod_identifier_line_edit.setText(
                    self.curseforge_mods_table_model.identifiers[selected_rows[-1]]
                )
                self.curseforge_mod_identifier_line_edit.setEnabled(True)
            else:
                self.curseforge_mod_identifier_line_edit.setText(None)
                self.curseforge_mod_identifier_line_edit.setEnabled(False)

            if len(selected_rows):
                self.curseforge_mod_remove_button.setEnabled(True)
            else:
                self.curseforge_mod_remove_button.setEnabled(False)

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

        @utilities.make_thread(daemon=True)
        def __builder_load_package_thread():
            self.builder.load_package(path)
            progress_dialog.completed.emit()

        @helpers.make_slot()
        @helpers.connect_slot(progress_dialog.cancel_request)
        def __on_cancel_request():
            self.builder.abort()
            progress_dialog.completed.emit()

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

        if self.builder.manifest.game_versions:
            self.minecraft_versions_line_edit.setText(", ".join(self.builder.manifest.game_versions))

        self.release_type_combo_box.setCurrentText(self.builder.manifest.release_preference.value.title())

        # ***External Mods***

        # ***Loading Priority***

        # ***Minecraft Forge***

        # ***Java Runtime***

        self.client_allocated_memory_spin_box.setValue(self.builder.client_allocated_memory)
        self.server_allocated_memory_spin_box.setValue(self.builder.server_allocated_memory)

        if self.builder.manifest.client_java_args:
            self.client_jvm_arguments_text_edit.setPlainText(
                "\n".join(self.builder.manifest.client_java_args)
            )
        if self.builder.manifest.server_java_args:
            self.server_jvm_arguments_text_edit.setPlainText(
                "\n".join(self.builder.manifest.server_java_args)
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
