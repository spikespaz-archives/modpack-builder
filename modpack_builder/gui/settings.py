import os
import json
import shutil
import platform

from pathlib import Path

from . import PROGRAM_NAME

PLATFORM = platform.system()

if PLATFORM == "Windows":
    import winreg


class ModpackBuilderSettings:
    def __init__(self, builder, path=None):
        self.json_indent = 2

        self.builder = builder

        if path:
            settings_directory = path
        else:
            settings_directory = ModpackBuilderSettings.get_settings_directory()

        if not settings_directory:
            settings_directory = (Path.home() / ".modpack_builder").resolve()

        self.settings_directory = settings_directory

        self.curseforge_cache = dict()

    def load_settings(self):
        if not self.__settings_file.exists() and not self.__settings_file.is_file():
            return False

        with open(self.__settings_file, "r") as file:
            data = json.load(file)

            self.builder.concurrent_requests = data.get("concurrent_requests", self.builder.concurrent_requests)
            self.builder.concurrent_downloads = data.get("concurrent_downloads", self.builder.concurrent_downloads)
            self.builder.minecraft_directory = data.get("minecraft_directory", self.builder.minecraft_directory)
            self.builder.minecraft_launcher_path = data.get("minecraft_launcher_path",
                                                            self.builder.minecraft_launcher_path)
            self.builder.profiles_directory = data.get("profiles_directory", self.builder.profiles_directory)

        return True

    def load_curseforge_cache(self):
        if not self.__curseforge_cache_file.exists() and not self.__curseforge_cache_file.is_file():
            return False

        with open(self.__curseforge_cache_file, "r") as file:
            self.curseforge_cache.update(json.load(file))

        return True

    def dump_settings(self):
        with open(self.__settings_file, "w") as file:
            json.dump(self.dictionary, file, indent=self.json_indent)

    def dump_curseforge_cache(self):
        with open(self.__curseforge_cache_file, "w") as file:
            json.dump(self.curseforge_cache, file, indent=self.json_indent)

    @staticmethod
    def get_settings_directory():
        if PLATFORM == "Windows":
            program_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"SOFTWARE\{PROGRAM_NAME}")
            settings_path = Path(os.path.expandvars(winreg.QueryValueEx(program_key, "SettingsDirectory")[0]))

            program_key.Close()

            return settings_path

        elif PLATFORM == "Darwin":
            return None

        elif PLATFORM == "Linux":
            return None

    @staticmethod
    def set_settings_directory(path):
        if PLATFORM == "Windows":
            program_key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, rf"SOFTWARE\{PROGRAM_NAME}")

            winreg.SetValueEx(program_key, "SettingsDirectory", None, winreg.REG_EXPAND_SZ, path.resolve())
            winreg.FlushKey(program_key)

            program_key.Close()

        elif PLATFORM == "Darwin":
            pass

        elif PLATFORM == "Linux":
            pass

    @property
    def settings_directory(self):
        return self.__settings_path

    @settings_directory.setter
    def settings_directory(self, value):
        (value := value.resolve()).mkdir(parents=True, exist_ok=True)

        if self.settings_directory.exists() and self.settings_directory.is_dir():
            shutil.move(str(self.settings_directory), str(value))

        self.__settings_path = value
        self.__settings_file = value / "settings.json"
        self.__curseforge_cache_file = value / "curseforge_cache.json"

        ModpackBuilderSettings.set_settings_directory(value)

    @property
    def concurrent_requests(self):
        return self.builder.concurrent_requests

    @concurrent_requests.setter
    def concurrent_requests(self, value):
        self.builder.concurrent_requests = value
        self.dump_settings()

    @property
    def concurrent_downloads(self):
        return self.builder.concurrent_downloads

    @concurrent_downloads.setter
    def concurrent_downloads(self, value):
        self.builder.concurrent_downloads = value
        self.dump_settings()

    @property
    def minecraft_directory(self):
        return self.builder.minecraft_directory

    @minecraft_directory.setter
    def minecraft_directory(self, value):
        self.builder.minecraft_directory = value
        self.dump_settings()

    @property
    def minecraft_launcher_path(self):
        return self.builder.minecraft_launcher_path

    @minecraft_launcher_path.setter
    def minecraft_launcher_path(self, value):
        self.builder.minecraft_launcher_path = value
        self.dump_settings()

    @property
    def profiles_directory(self):
        return self.builder.profiles_directory

    @profiles_directory.setter
    def profiles_directory(self, value):
        self.builder.profiles_directory = value
        self.dump_settings()

    @property
    def dictionary(self):
        return {
            "concurrent_requests": self.concurrent_requests,
            "concurrent_downloads": self.concurrent_downloads,
            "minecraft_directory": self.minecraft_directory.resolve(),
            "minecraft_launcher_path": self.minecraft_launcher_path.resolve(),
            "profiles_directory": self.profiles_directory.resolve()
        }
