import json
import shutil

from pathlib import Path


class ModpackBuilderSettings:
    def __init__(self, builder, path=Path("~/.modpack-builder")):
        self.json_indent = 2

        self.builder = builder
        self.settings_path = path
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

    @property
    def settings_path(self):
        return self.__settings_path

    @settings_path.setter
    def settings_path(self, value):
        (value := value.resolve()).mkdir(parents=True, exist_ok=True)

        if self.settings_path.exists() and self.settings_path.is_dir():
            shutil.move(str(self.settings_path), str(value))

        self.__settings_path = value
        self.__settings_file = value / "settings.json"
        self.__curseforge_cache_file = value / "curseforge_cache.json"

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
