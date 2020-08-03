import os
import json
import pickle
import shutil
import platform

from pathlib import Path
from json import JSONDecodeError

from modpack_builder.gui import PROGRAM_NAME

PLATFORM = platform.system()

if PLATFORM == "Windows":
    import winreg


class ModpackBuilderSettings:
    def __init__(self, builder, path=None):
        self.json_indent = 2

        self.builder = builder

        self.__settings_directory = None
        self.__settings_file = None
        self.__curseforge_cache_file = None

        if path:
            settings_directory = path
        else:
            settings_directory = ModpackBuilderSettings.get_settings_directory()

        if not settings_directory:
            settings_directory = (Path.home() / ".modpack_builder").resolve()

        self.settings_directory = settings_directory

        self.curseforge_cache = dict()

    def load_settings(self):
        if not self.__settings_file.exists() or not self.__settings_file.is_file():
            return False

        try:
            with open(self.__settings_file, "r") as file:
                data = json.load(file)

                self.builder.concurrent_requests = data.get("concurrent_requests", self.builder.concurrent_requests)
                self.builder.concurrent_downloads = data.get("concurrent_downloads", self.builder.concurrent_downloads)

                if (minecraft_directory := data.get("minecraft_directory")) is not None:
                    self.builder.minecraft_directory = Path(minecraft_directory).resolve()

                if (minecraft_launcher_path := data.get("minecraft_launcher_path")) is not None:
                    self.builder.minecraft_launcher_path = Path(minecraft_launcher_path).resolve()

                if (profiles_directory := data.get("profiles_directory")) is not None:
                    self.builder.profiles_directory = Path(profiles_directory).resolve()

        except JSONDecodeError:
            self.__settings_file.unlink()
            return False

        return True

    def load_curseforge_cache(self):
        try:
            with open(self.__curseforge_cache_file, "rb") as file:
                self.curseforge_cache.update(pickle.load(file))

        except (FileNotFoundError, Exception) as exception:
            if type(exception) is not FileNotFoundError:
                self.__curseforge_cache_file.unlink()

            if self.__curseforge_cache_backup_file.exists() and self.__curseforge_cache_backup_file.is_file():
                shutil.move(str(self.__curseforge_cache_backup_file), str(self.__curseforge_cache_file))

                return self.load_curseforge_cache()

            return False

        return True

    def dump_settings(self):
        with open(self.__settings_file, "w") as file:
            json.dump(self.dictionary, file, indent=self.json_indent)

    def dump_curseforge_cache(self, purge=True):
        if self.__curseforge_cache_file.exists() and self.__curseforge_cache_file.is_file():
            shutil.move(str(self.__curseforge_cache_file), str(self.__curseforge_cache_backup_file))

        if purge:
            for entry in self.curseforge_cache.values():
                entry.__setattr__(f"_{type(entry).__name__}__description", None)

        with open(self.__curseforge_cache_file, "wb") as file:
            pickle.dump(self.curseforge_cache, file)

    @staticmethod
    def get_settings_directory():
        if PLATFORM == "Windows":
            try:
                program_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"SOFTWARE\{PROGRAM_NAME}")
                settings_path = Path(os.path.expandvars(winreg.QueryValueEx(program_key, "SettingsDirectory")[0]))

                program_key.Close()

                return settings_path
            except FileNotFoundError:
                return None

        elif PLATFORM == "Darwin":
            return None

        elif PLATFORM == "Linux":
            return None

    @staticmethod
    def set_settings_directory(path):
        if PLATFORM == "Windows":
            program_key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, rf"SOFTWARE\{PROGRAM_NAME}")

            winreg.SetValueEx(program_key, "SettingsDirectory", None, winreg.REG_EXPAND_SZ, str(path.resolve()))
            winreg.FlushKey(program_key)

            program_key.Close()

        elif PLATFORM == "Darwin":
            pass

        elif PLATFORM == "Linux":
            pass

    @property
    def settings_directory(self):
        return self.__settings_directory

    @settings_directory.setter
    def settings_directory(self, value):
        (value := value.resolve()).mkdir(parents=True, exist_ok=True)

        if (
            self.__settings_file and
            self.__settings_file.exists() and
            self.__settings_file.is_file()
        ):
            shutil.move(str(self.__settings_file), str(value))

        if (
            self.__curseforge_cache_file and
            self.__curseforge_cache_file.exists() and
            self.__curseforge_cache_file.is_file()
        ):
            shutil.move(str(self.__curseforge_cache_file), str(value))

        if (
            self.settings_directory and
            self.settings_directory.exists() and
            self.settings_directory.is_dir() and
            not tuple(self.settings_directory.iterdir())
        ):
            self.settings_directory.rmdir()

        self.__settings_directory = value
        self.__settings_file = value / "settings.json"
        self.__curseforge_cache_file = value / "curseforge_cache.dat"
        self.__curseforge_cache_backup_file = value / "curseforge_cache.dat.bak"

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
        dictionary = dict()

        dictionary["concurrent_requests"] = self.concurrent_requests
        dictionary["concurrent_downloads"] = self.concurrent_downloads

        if self.minecraft_directory:
            dictionary["minecraft_directory"] = str(self.minecraft_directory.resolve())
        else:
            dictionary["minecraft_directory"] = None

        if self.minecraft_launcher_path:
            dictionary["minecraft_launcher_path"] = str(self.minecraft_launcher_path.resolve())
        else:
            dictionary["minecraft_launcher_path"] = None

        if self.profiles_directory:
            dictionary["profiles_directory"] = str(self.profiles_directory.resolve())
        else:
            dictionary["profiles_directory"] = None

        return dictionary
