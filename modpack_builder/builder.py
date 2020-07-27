import os
import math
import json
import shlex
import platform
import dataclasses

from enum import Enum
from pathlib import Path
from zipfile import ZipFile
from tempfile import TemporaryDirectory

import psutil

from orderedset import OrderedSet

from .helpers import ProgressReporter


PLATFORM = platform.system()


class ReleaseType(Enum):
    release = "release"
    beta = "beta"
    alpha = "alpha"


class ModpackManifest:
    __curseforge_mod_url = "https://www.curseforge.com/minecraft/mc-mods/{}"

    @dataclasses.dataclass
    class JavaDownloads:
        windows: str = None
        darwin: str = None
        linux: str = None

    @dataclasses.dataclass(frozen=True)
    class ExternalFile:
        pattern: str = None
        immutable: bool = None
        server: bool = None

    @dataclasses.dataclass(frozen=True)
    class ExternalMod:
        identifier: str = None
        name: str = None
        version: str = None
        url: str = None
        server: bool = None

    @dataclasses.dataclass(frozen=True)
    class CurseForgeMod:
        identifier: str = None
        version: str = None
        url: str = None
        server: bool = None

    def __init__(self, data):
        self.profile_name = data.get("profile_name")
        self.profile_id = data.get("profile_id")
        self.profile_icon = data.get("profile_icon")
        self.game_versions = OrderedSet(data.get("game_versions", tuple()))

        java_downloads = data.get("java_downloads", dict())

        self.java_downloads = ModpackManifest.JavaDownloads(
            windows=java_downloads.get("windows"),
            darwin=java_downloads.get("darwin"),
            linux=java_downloads.get("linux")
        )

        self.forge_download = data.get("forge_download")
        self.version_label = data.get("version_label")
        self.release_preference = ReleaseType(data.get("release_preference", ReleaseType.release))
        self.load_priority = OrderedSet(data.get("load_priority", tuple()))

        client_data = data.get("client", dict())
        server_data = data.get("server", dict())

        # These don't need to be sets because for some strange reasons the arguments might
        # actually need to occur multiple times. For example, if an argument such as '--include <path>' is
        # split with 'shlex.split', the argument flag may be included multiple times for multiple paths.
        self.client_java_args = shlex.split(client_data.get("java_args", str()))
        self.server_java_args = shlex.split(server_data.get("java_args", str()))

        self.external_files = set()

        for pattern in client_data.get("external_files", dict()).get("overwrite", tuple()):
            self.external_files.add(ModpackManifest.ExternalFile(pattern=pattern, immutable=False, server=False))

        for pattern in client_data.get("external_files", dict()).get("immutable", tuple()):
            self.external_files.add(ModpackManifest.ExternalFile(pattern=pattern, immutable=True, server=False))

        for pattern in server_data.get("external_files", dict()).get("overwrite", tuple()):
            self.external_files.add(ModpackManifest.ExternalFile(pattern=pattern, immutable=False, server=True))

        for pattern in server_data.get("external_files", dict()).get("immutable", tuple()):
            self.external_files.add(ModpackManifest.ExternalFile(pattern=pattern, immutable=True, server=True))

        self.external_mods = set()

        for identifier, entry in client_data.get("external_mods", dict()).items():
            self.external_mods.add(ModpackManifest.ExternalMod(identifier=identifier, **entry, server=False))

        for identifier, entry in server_data.get("external_mods", dict()).items():
            self.external_mods.add(ModpackManifest.ExternalMod(identifier=identifier, **entry, server=True))

        self.curseforge_mods = set()

        for identifier in client_data.get("curseforge_mods", tuple()):
            identifier, _, version = identifier.lower().partition(":")

            if version in (member.value for member in ReleaseType):
                version = ReleaseType(version)

            self.curseforge_mods.add(ModpackManifest.CurseForgeMod(
                identifier=identifier,
                version=version if version else None,
                url=self.__curseforge_mod_url.format(identifier),
                server=False
            ))

        for identifier in server_data.get("curseforge_mods", tuple()):
            identifier, _, version = identifier.lower().partition(":")

            if version in (member.value for member in ReleaseType):
                version = ReleaseType(version)

            self.curseforge_mods.add(ModpackManifest.CurseForgeMod(
                identifier=identifier,
                version=version if version else None,
                url=self.__curseforge_mod_url.format(identifier),
                server=True
            ))

    @property
    def dictionary(self):
        dictionary = dict()

        dictionary["profile_name"] = self.profile_name
        dictionary["profile_id"] = self.profile_id
        dictionary["profile_icon"] = self.profile_icon
        dictionary["game_versions"] = list(self.game_versions)
        dictionary["java_downloads"] = self.java_downloads._asdict()
        dictionary["forge_download"] = self.forge_download
        dictionary["version_label"] = self.version_label
        dictionary["release_preference"] = self.release_preference.value
        dictionary["load_priority"] = list(self.load_priority)

        client_data = dict()
        server_data = dict()

        client_data["java_args"] = " ".join(self.client_java_args)
        server_data["java_args"] = " ".join(self.server_java_args)

        client_external_files = {
            "immutable": [],
            "overwrite": []
        }
        server_external_files = {
            "immutable": [],
            "overwrite": []
        }

        for entry in self.external_files:
            if entry.server and entry.immutable:
                server_external_files["immutable"].append(entry.pattern)
            elif entry.server:  # entry.server and not entry.immutable
                server_external_files["overwrite"].append(entry.pattern)
            elif entry.immutable:  # not entry.server and entry.immutable
                client_external_files["immutable"].append(entry.pattern)
            else:  # not entry.server and not entry.immutable
                client_external_files["overwrite"].append(entry.pattern)

        client_data["external_files"] = client_external_files
        server_data["external_files"] = server_external_files

        client_external_mods = dict()
        server_external_mods = dict()

        for entry in self.external_mods:
            entry_dict = entry._asdict()

            del entry_dict["identifier"]
            del entry_dict["server"]

            if entry.server:
                server_external_mods[entry.identifier] = entry_dict
            else:
                client_external_mods[entry.identifier] = entry_dict

        client_data["external_mods"] = client_external_mods
        server_data["external_mods"] = server_external_mods

        client_curseforge_mods = list()
        server_curseforge_mods = list()

        for entry in self.curseforge_mods:
            if entry.server:
                server_curseforge_mods.append(
                    f"{entry.identifier}:{entry.version}" if entry.version else entry.identifier
                )
            else:
                client_curseforge_mods.append(
                    f"{entry.identifier}:{entry.version}" if entry.version else entry.identifier
                )

        client_curseforge_mods.sort()
        server_curseforge_mods.sort()

        client_data["curseforge_mods"] = client_curseforge_mods
        server_data["curseforge_mods"] = server_curseforge_mods

        dictionary["client"] = client_data
        dictionary["server"] = server_data

        return dictionary


class ModpackBuilder:
    # I would love to find a way to make everything below into static,
    # read-only properties as they are intended to be easily-referenced yet still hard-coded values.
    # Alas, I have given up for now and accepted the fact that Python does not follow C-style access levels.

    # Max concurrent requests is for any batch of HTTP requests made,
    # but this default number specifically is meant to be nice to the CurseForge API.
    max_concurrent_requests = 16
    # Also a default chosen to not put too much stress on the CurseForge mirrors.
    max_concurrent_downloads = 16
    # Generally Minecraft can benefit from extra memory up to a certain point.
    # The value of this is the cap imposed by `ModpackBuilder._get_recommended_memory`,
    # but can be overridden or set to 0 to remove the limit entirely (for example, servers).
    # It is highly recommended to use the keyword argument provided by that function rather than
    # changing the value of this variable.
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

    def __init__(self, minecraft_directory=None, minecraft_launcher_path=None, client_allocated_memory=None,
                 server_allocated_memory=None):
        self.__logger = print
        self.__reporter = ProgressReporter(None)

        self.__temporary_directory = TemporaryDirectory()

        self.temporary_directory = Path(self.__temporary_directory.name)

        self.__package_contents_directory = self.temporary_directory / "extracted"
        self.__package_contents_directory.mkdir()

        self.concurrent_requests = 8
        self.concurrent_downloads = 8

        self.readme_path = None

        self.manifest = ModpackManifest(dict())

        self.minecraft_directory = minecraft_directory or self.get_default_minecraft_directory()
        self.minecraft_launcher_path = minecraft_launcher_path or self.get_minecraft_launcher_path()

        self.profiles_directory = self.minecraft_directory / "profiles"
        self.profile_directory = None

        self.client_allocated_memory = client_allocated_memory or self.get_recommended_memory()
        self.server_allocated_memory = server_allocated_memory or self.get_recommended_memory(maximum=0)

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

    def remove_extracted(self):
        if not (contents := tuple(self.__package_contents_directory.glob("**/*"))):
            return

        self.__reporter.maximum = len(contents)
        self.__reporter.value = 0
        self.__reporter.text = "Removing old files: %p%"
        self.__logger("Deleting previous package contents...")

        directories = []

        for item_path in contents:
            if item_path.is_file():
                self.__logger(f"Deleting file: {item_path.relative_to(self.__package_contents_directory)}")
                item_path.unlink()
                self.__reporter.value += 1
            elif item_path.is_dir():
                directories.append(item_path)

        for directory in reversed(directories):
            self.__logger(f"Removing directory: {directory.relative_to(self.__package_contents_directory)}")
            directory.rmdir()
            self.__reporter.value += 1

    def extract_package(self, path):
        self.__logger(f"Reading package contents: {path.name}")
        self.__reporter.value = 0
        self.__reporter.text = f"Extracting '{path.name}': %p%"

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
        self.remove_extracted()
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

                break
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
