import os
import math
import json
import psutil
import platform

from enum import Enum
from pathlib import Path
from zipfile import ZipFile
from tempfile import TemporaryDirectory

from .helpers import ProgressReporter


PLATFORM = platform.system()


class ReleaseType(Enum):
    release = "release"
    beta = "beta"
    alpha = "alpha"


class ModpackBuilder:
    _max_concurrent_requests = 16
    _max_concurrent_downloads = 16
    _max_recommended_java_runtime_memory = 8
    _markdown_file_extensions = ("txt", "md", "mkd", "mkdn", "mdown", "markdown")

    def __init__(self):
        self.__logger = print
        self.__reporter = ProgressReporter(None)
        self.__temporary_directory = TemporaryDirectory()

        self.temporary_directory = Path(self.__temporary_directory.name)

        self.__package_contents_path = self.temporary_directory / "extracted_package"
        self.__package_contents_path.mkdir()

        self.modpack_package = None
        self.modpack_readme_path = None
        self.manifest_json = None

        self.profile_name = ""
        self.profile_directory = None
        self.profile_id = ""
        self.profile_icon_base64 = ""

        self.compatible_minecraft_versions = []
        self.preferred_mod_release_type = ReleaseType.release

        self.curseforge_mods = {}
        self.external_mods = {}

        self.mod_loading_priority = []

        self.forge_minecraft_version = ""
        self.forge_version = ""

        self.java_runtime_memory = self._get_recommended_memory()
        self.java_runtime_arguments = []

        self.java_download_urls = {}

        self.external_resource_globs = []

        self.minecraft_directory = self._get_default_minecraft_directory()
        self.minecraft_launcher_path = self._get_minecraft_launcher_path()

        self.concurrent_requests = 8
        self.concurrent_downloads = 8

    def __del__(self):
        self.__temporary_directory.cleanup()

    def set_logger(self, logger):
        self.__logger = logger

    def set_reporter(self, reporter):
        self.__reporter = reporter

    def install_modpack(self):
        pass

    def update_modpack(self):
        pass

    def update_profile(self):
        pass

    def launch_minecraft(self):
        pass

    def dump_manifest(self):
        pass

    def extract_package(self, path):
        self.__logger("Reading package contents: " + path.name)

        with ZipFile(path, "r") as package_zip:
            package_info_list = package_zip.infolist()

            self.__reporter.maximum = len(package_info_list)
            self.__logger(f"Extracting package to: {self.__package_contents_path}")

            for member_info in package_info_list:
                self.__logger("Extracting member: " + member_info.filename)
                self.__reporter.value += 1

                package_zip.extract(member_info, self.__package_contents_path)

            self.__logger("Done extracting package.")
            self.__reporter.done()

    def load_package(self, path):
        self.extract_package(path)

        self.__logger("Loading package manifest...")

        with open(self.__package_contents_path / "manifest.json", "r") as manifest_file:
            self.manifest_json = json.load(manifest_file)

        for file_path in self.__package_contents_path.iterdir():
            if not file_path.is_file() or not file_path.suffix:
                continue

            if file_path.stem.lower() == "readme" and file_path.suffix.lower() in self._markdown_file_extensions:
                self.__logger(f"Found README file: {file_path.name}")
                self.modpack_readme_path = file_path
        else:
            self.__logger("No README file found in package!")

    def export_package(self):
        pass

    def install_server(self):
        pass

    def install_forge_client(self):
        pass

    def install_forge_server(self):
        pass

    def download_java_runtime(self):
        pass

    def install_external_resources(self):
        pass

    @staticmethod
    def _get_system_memory():
        return math.ceil(psutil.virtual_memory().total / 1024 / 1024 / 1024)

    @staticmethod
    def _get_max_recommended_memory():
        return ModpackBuilder._get_system_memory() - 1

    @staticmethod
    def _get_recommended_memory():
        system_memory = ModpackBuilder._get_system_memory()

        if system_memory == 4:
            return 3
        elif system_memory < 8:
            return system_memory - 2
        else:
            return min(system_memory / 2, ModpackBuilder._max_recommended_java_runtime_memory)

    @staticmethod
    def _get_default_minecraft_directory():
        minecraft_directory = None

        if PLATFORM == "Windows":
            minecraft_directory = Path(os.environ["appdata"], ".minecraft")
        elif PLATFORM == "Darwin":
            minecraft_directory = Path.home().joinpath("/Library/Application Support/minecraft")
        elif PLATFORM == "Linux":
            minecraft_directory = Path.home().joinpath(".minecraft")

        if minecraft_directory.exists() and minecraft_directory.is_dir():
            return minecraft_directory.resolve()

        return None

    @staticmethod
    def _get_minecraft_launcher_path():
        if PLATFORM == "Windows":
            import win32com.client

            shell = win32com.client.Dispatch("WScript.Shell")

            def __find_minecraft_launcher_path(directory):
                for link_file in directory.glob("**/*.lnk"):
                    shortcut = shell.CreateShortcut(str(link_file))

                    if shortcut.Targetpath.lower().endswith("minecraftlauncher.exe"):
                        return Path(shortcut.Targetpath).resolve()

                return None

            programs_directory = Path(os.environ["programdata"], "Microsoft\\Windows\\Start Menu\\Programs")
            minecraft_launcher_path = __find_minecraft_launcher_path(programs_directory)

            if minecraft_launcher_path is not None and minecraft_launcher_path.exists() and minecraft_launcher_path.is_file():
                return minecraft_launcher_path

            import winreg

            user_shell_folders_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                                    "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\User Shell Folders")
            programs_directory = Path(os.path.expandvars(winreg.QueryValueEx(user_shell_folders_key, "Programs")[0]))
            user_shell_folders_key.Close()

            minecraft_launcher_path = __find_minecraft_launcher_path(programs_directory)

            if minecraft_launcher_path is not None and minecraft_launcher_path.exists() and minecraft_launcher_path.is_file():
                return minecraft_launcher_path

        elif PLATFORM == "Darwin":
            return None

        elif PLATFORM == "Linux":
            return None
