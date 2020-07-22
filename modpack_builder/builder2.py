import os
import math
import psutil
import platform

from enum import Enum
from pathlib import Path


PLATFORM = platform.system()


class ReleaseType(Enum):
    release = "release"
    beta = "beta"
    alpha = "alpha"


class ProgressReporter:
    def __init__(self, callback):
        self._maximum = 100
        self._value = 0
        self._done = False
        self.__callback = callback

    @property
    def maximum(self):
        return self._maximum

    @maximum.setter
    def maximum(self, value):
        self._maximum = value

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self._value = value

    def done(self):
        self._done = True

        if self.__callback:
            self.__callback(self)

    def is_done(self):
        return self._done


class ModpackBuilder:
    _max_concurrent_requests = 16
    _max_concurrent_downloads = 16
    _max_recommended_java_runtime_memory = 8

    def __init__(self):
        self.modpack_package = None

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

    def install_modpack(self):
        pass

    def update_modpack(self):
        pass

    def update_profile(self):
        pass

    def launch_minecraft(self):
        pass

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
