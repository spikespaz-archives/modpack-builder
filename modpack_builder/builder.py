import os
import math
import json
import psutil
import platform

from enum import Enum
from pathlib import Path
from zipfile import ZipFile
from tempfile import TemporaryDirectory

import recordclass

from .helpers import ProgressReporter


PLATFORM = platform.system()


class ReleaseType(Enum):
    release = "release"
    beta = "beta"
    alpha = "alpha"


class ModpackManifest:
    __curseforge_mod_url = "https://www.curseforge.com/minecraft/mc-mods/{}"

    JavaDownloads = recordclass.recordclass("JavaDownloads", ("windows", "darwin", "linux"))
    ExternalFile = recordclass.recordclass("ExternalFile", ("pattern", "immutable"), hashable=True)
    ExternalMod = recordclass.recordclass("ExternalMod", ("identifier", "name", "version", "url", "server"), hashable=True)
    CurseForgeMod = recordclass.recordclass("CurseForgeMod", ("identifier", "url", "server"), hashable=True)

    def __init__(self, data):
        self.profile_name = data.get("profile_name")
        self.profile_id = data.get("profile_id")
        self.profile_icon = data.get("profile_icon")
        self.game_versions = set(data.get("game_versions", tuple()))

        java_downloads = data.get("java_downloads", {})

        self.java_downloads = ModpackManifest.JavaDownloads(
            windows=java_downloads.get("windows"),
            darwin=java_downloads.get("darwin"),
            linux=java_downloads.get("linux")
        )

        self.forge_download = data.get("forge_download")
        self.version_label = data.get("version_label")
        self.release_preference = ReleaseType(data.get("release_preference", ReleaseType.release))
        self.load_priority = set(data.get("load_priority", tuple()))

        client_data = data.get("client", {})
        server_data = data.get("server", {})

        self.client_java_args = client_data.get("java_args")
        self.client_external_files = set()

        self.server_java_args = server_data.get("java_args")
        self.server_external_files = set()

        for entry in client_data.get("external_files", {}).get("overwrite", tuple()):
            self.client_external_files.add(ModpackManifest.ExternalFile(pattern=entry, immutable=False))

        for entry in client_data.get("external_files", {}).get("immutable", tuple()):
            self.client_external_files.add(ModpackManifest.ExternalFile(pattern=entry, immutable=True))

        for entry in server_data.get("external_files", {}).get("overwrite", tuple()):
            self.server_external_files.add(ModpackManifest.ExternalFile(pattern=entry, immutable=False))

        for entry in server_data.get("external_files", {}).get("immutable", tuple()):
            self.server_external_files.add(ModpackManifest.ExternalFile(pattern=entry, immutable=True))

        self.external_mods = set()

        for identifier, entry in client_data.get("external_mods", {}).items():
            corrected_entry = {"name": None, "version": None}
            corrected_entry.update(entry)
            self.client_external_files.add(ModpackManifest.ExternalMod(
                identifier=identifier,
                **corrected_entry,
                server=False
            ))

        for identifier, entry in server_data.get("external_mods", {}).items():
            corrected_entry = {"name": None, "version": None}
            corrected_entry.update(entry)
            self.server_external_files.add(ModpackManifest.ExternalMod(
                identifier=identifier,
                **corrected_entry,
                server=True
            ))

        self.curseforge_mods = set()

        for identifier in client_data.get("curseforge_mods", tuple()):
            self.curseforge_mods.add(ModpackManifest.CurseForgeMod(
                identifier=identifier,
                url=self.__curseforge_mod_url.format(identifier),
                server=False
            ))

        for identifier in server_data.get("curseforge_mods", tuple()):
            self.curseforge_mods.add(ModpackManifest.CurseForgeMod(
                identifier=identifier,
                url=self.__curseforge_mod_url.format(identifier),
                server=True
            ))


class ModpackBuilder:
    # I would love to find a way to make everything below into static,
    # read-only properties as they are intended to be easily-referenced yet still hard-coded values.
    # Alas, I have given up for now and accepted the fact that Python does not follow C-style access levels.
    max_concurrent_requests = 16
    max_concurrent_downloads = 16
    max_recommended_memory = 8
    # The absolute lower limit of memory to be allocated to Minecraft.
    # The game will not run well at all if it has any less memory than this.
    min_recommended_memory = 2
    # The minimum amount of memory that should be saved for the system, and Minecraft should never
    # be allocated more than the virtual system memory minus this value.
    min_reserved_system_memory = 1
    # These are the file extensions for markdown files supported by GitHub.
    # We align with these to discourage incompatibility with repository file previews.
    markdown_file_extensions = (".txt", ".md", ".mkd", ".mkdn", ".mdown", ".markdown")

    def __init__(self):
        self.__logger = print
        self.__reporter = ProgressReporter(None)

        self.__temporary_directory = TemporaryDirectory()

        self.temporary_directory = Path(self.__temporary_directory.name)

        self.__package_contents_directory = self.temporary_directory / "extracted"
        self.__package_contents_directory.mkdir()

        self.concurrent_requests = 8
        self.concurrent_downloads = 8

        self.readme_path = None

        self.manifest = ModpackManifest({})

        self.minecraft_directory = self.get_default_minecraft_directory()
        self.minecraft_launcher_path = self.get_minecraft_launcher_path()

        self.profiles_directory = self.minecraft_directory / "profiles"
        self.profile_directory = None

        self.client_allocated_memory = self.get_recommended_memory()
        self.server_allocated_memory = self.get_recommended_memory(maximum=0)

    def __del__(self):
        self.__temporary_directory.cleanup()

    def __setattr__(self, name, value):
        if name == "logger":
            self.__logger = value
        elif name == "reporter":
            self.__reporter = value
        else:
            super().__setattr__(name, value)

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
        self.__logger(f"Reading package contents: {path.name}")
        self.__reporter.text = f"Extracting {path.name}: %p%"

        with ZipFile(path, "r") as package_zip:
            package_info_list = package_zip.infolist()

            self.__reporter.maximum = len(package_info_list)
            self.__logger(f"Extracting package to: {self.__package_contents_directory}")

            for member_info in package_info_list:
                self.__logger(f"Extracting member: {member_info.filename}")
                self.__reporter.value += 1

                package_zip.extract(member_info, self.__package_contents_directory)

            self.__logger("Done extracting package!")
            self.__reporter.done()

    def load_package(self, path):
        self.extract_package(path)

        self.__logger("Loading package manifest...")

        with open(self.__package_contents_directory / "manifest.json", "r") as manifest_file:
            self.manifest = ModpackManifest(json.load(manifest_file))

        if self.minecraft_directory:
            self.profile_directory = self.profiles_directory / self.manifest.profile_id

        for file_path in self.__package_contents_directory.iterdir():
            if not file_path.is_file() or not file_path.suffix:
                continue

            if file_path.stem.lower() == "readme" and file_path.suffix.lower() in self.markdown_file_extensions:
                self.__logger(f"Found README file: {file_path.name}")
                self.readme_path = file_path
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
    def get_system_memory():
        return math.ceil(psutil.virtual_memory().total / 1024 / 1024 / 1024)

    @staticmethod
    def get_maximum_memory():
        return ModpackBuilder.get_system_memory() - ModpackBuilder.min_reserved_system_memory

    @staticmethod
    def get_recommended_memory(minimum=min_recommended_memory, maximum=max_recommended_memory):
        system_memory = ModpackBuilder.get_system_memory()

        if system_memory == 4:
            result = 3
        elif system_memory < 8:
            result = system_memory - 2
        else:
            result = system_memory / 2

        if minimum:
            result = max(result, minimum)

        if maximum:
            result = min(result, maximum)

        return result

    @staticmethod
    def get_default_minecraft_directory():
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
    def get_minecraft_launcher_path():
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

            user_shell_folders_key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\User Shell Folders"
            )
            programs_directory = Path(os.path.expandvars(winreg.QueryValueEx(user_shell_folders_key, "Programs")[0]))
            user_shell_folders_key.Close()

            minecraft_launcher_path = __find_minecraft_launcher_path(programs_directory)

            if minecraft_launcher_path is not None and minecraft_launcher_path.exists() and minecraft_launcher_path.is_file():
                return minecraft_launcher_path

        elif PLATFORM == "Darwin":
            return None

        elif PLATFORM == "Linux":
            return None
