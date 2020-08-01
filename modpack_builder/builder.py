import os
import math
import json
import shutil
import platform

from pathlib import Path
from zipfile import ZipFile
from tempfile import TemporaryDirectory
from concurrent.futures import ThreadPoolExecutor

import psutil

from . import utilities

from .manifest import ModpackManifest
from .utilities import ProgressReporter
from .curseforge import CurseForgeMod, CURSEFORGE_MOD_BASE_URL

PLATFORM = platform.system()

if PLATFORM == "Windows":
    import winreg
    import win32com.client


class ModpackBuilder:
    # I would love to find a way to make everything below into static,
    # read-only properties as they are intended to be easily-referenced yet still hard-coded values.
    # Alas, I have given up for now and accepted the fact that Python does not follow C-style access levels.

    # Max concurrent requests is for any batch of HTTP requests made,
    # but this default number specifically is meant to be nice to the CurseForge API.
    max_concurrent_requests = 16
    # Also a default chosen to not put too much stress on the CurseForge mirrors.
    max_concurrent_downloads = 16
    # Block size for file stream downloads.
    download_block_size = 1024
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
        self.__task_aborted = False

        self.__logger = print
        self.__reporter = ProgressReporter(None)

        self.__temporary_directory = TemporaryDirectory()

        self.temporary_directory = Path(self.__temporary_directory.name)

        self.__package_contents_directory = self.temporary_directory / "extracted"
        self.__package_contents_directory.mkdir()

        self.__downloads_directory = self.temporary_directory / "downloads"
        self.__downloads_directory.mkdir()

        self.concurrent_requests = 8
        self.concurrent_downloads = 8

        self.readme_path = None

        self.manifest = ModpackManifest(dict())

        self.curseforge_mods = dict()
        self.curseforge_files = dict()

        self.minecraft_directory = minecraft_directory or ModpackBuilder.get_default_minecraft_directory()
        self.minecraft_launcher_path = minecraft_launcher_path or ModpackBuilder.get_minecraft_launcher_path()

        self.profiles_directory = self.minecraft_directory / "profiles"
        self.profile_directory = None
        self.mods_directory = None
        self.runtime_directory = None

        self.client_allocated_memory = client_allocated_memory or ModpackBuilder.get_recommended_memory()
        self.server_allocated_memory = server_allocated_memory or ModpackBuilder.get_recommended_memory(maximum=0)

    def __del__(self):
        self.__temporary_directory.cleanup()

    def __setattr__(self, name, value):
        if name == "logger":
            self.__logger = value
        elif name == "reporter":
            self.__reporter = value
        else:
            super().__setattr__(name, value)

    def abort(self):
        self.__task_aborted = True

    def fetch_curseforge_mods(self, skip_identifiers=None):
        self.curseforge_mods.clear()

        identifiers = set(self.manifest.curseforge_mods.keys())

        if skip_identifiers:
            identifiers -= set(skip_identifiers)

        self.__reporter.maximum = len(identifiers)
        self.__reporter.value = 0
        self.__logger("Retrieving information for all identifiers...")

        executor = ThreadPoolExecutor(max_workers=self.concurrent_requests)
        futures = dict()
        failures = list()

        def __target(identifier_):
            if self.__task_aborted:
                return

            return CurseForgeMod.get(identifier_)

        for identifier in identifiers:
            futures[executor.submit(__target, identifier)] = self.manifest.curseforge_mods[identifier]

        for future in futures:
            # Abort the loop if the task has been cancelled
            if self.__task_aborted:
                break

            try:
                # Ensure that the thread returned a value, if it hasn't the task is probably cancelled
                assert (entry := future.result())

                self.curseforge_mods[entry.identifier] = entry

                self.__logger(f"Retrieved information: {entry.identifier}")
            except Exception as error:
                self.__logger(
                    f"Failed: {futures[future].identifier}\n"
                    f"Error message: {error}"
                )

            self.__reporter.value += 1

        executor.shutdown(True)

        if self.__task_aborted:
            self.__task_aborted = False  # Reset as to not conflict with other tasks

            self.curseforge_mods.clear()  # Remove the results that have already been retrieved

            self.__logger("Information retrieval cancelled.")
        else:
            self.__logger("Finished fetching information for all identifiers.")

            if failures:
                self.__logger(f"Failed identifiers: {', '.join(entry.identifier for entry in failures)}")

        self.__reporter.done()

    def find_curseforge_files(self):
        assert self.curseforge_mods

        self.curseforge_files.clear()

        self.__reporter.maximum = len(self.curseforge_mods)
        self.__reporter.value = 0
        self.__logger("Searching for suitable releases for all identifiers...")

        failures = list()

        for entry in self.curseforge_mods.values():
            version = self.manifest.curseforge_mods[entry.identifier].version

            if isinstance(version, int):
                file = entry.file(version)
            else:
                if version is None:
                    version = self.manifest.release_preference

                file = entry.best_file(self.manifest.game_versions, version)

            if file:
                self.__logger(f"Found '{file.type.value}' file for '{entry.identifier}': {file.name}")
                self.curseforge_files[entry.identifier] = file
            else:
                failures.append(entry)
                self.__logger(f"Could not find suitable release for: {entry.identifier}")

            self.__reporter.value += 1

        self.__logger("Finished fetching releases for all identifiers.")

        if failures:
            self.__logger(f"Failed identifiers: {', '.join(entry.identifier for entry in failures)}")

        self.__reporter.done()

    def download_curseforge_files(self, reporter_factory=lambda: ProgressReporter()):
        assert self.curseforge_files

        self.mods_directory.mkdir(exist_ok=True, parents=True)

        self.__reporter.maximum = len(self.curseforge_files)
        self.__reporter.value = 0
        self.__logger("Downloading all CurseForge files...")

        executor = ThreadPoolExecutor(max_workers=self.concurrent_downloads)
        futures = dict()
        failures = dict()

        for identifier, file in self.curseforge_files.items():
            destination = self.__downloads_directory / file.name

            if destination.exists():
                self.__logger(f"File already exists: {file.name}")

                continue

            reporter = reporter_factory()
            reporter.maximum = 0
            reporter.value = 1

            futures[executor.submit(
                utilities.download_as_stream,
                file.download,
                destination,
                reporter=reporter,
                block_size=ModpackBuilder.download_block_size
            )] = (identifier, file)

        for future, (identifier, file) in futures.items():
            try:
                path = future.result()
                # Apparently 'shutil' doesn't support path-like objects (yet?)
                # so the source path must be changed to a string.
                shutil.move(str(path), str(self.mods_directory / file.name))
                self.__logger(f"Downloaded '{identifier}' file: {path.name}")
            except Exception as error:
                self.__logger(
                    f"Download for '{identifier}' failed: {file.name}\n"
                    f"Error message: {error}"
                )

            self.__reporter.value += 1

        self.__logger("Finished downloading all CurseForge files...")

        if failures:
            self.__logger(f"Failed downloads: {', '.join(file.name for file in failures.values())}")

        self.__reporter.done()

    def add_curseforge_mod(self, identifier):
        if (curseforge_mod := CurseForgeMod.get(identifier)) is None:
            self.__logger(f"Unable to retrieve mod information: {identifier}")
            return False

        curseforge_file = curseforge_mod.best_file(
            self.manifest.game_versions,
            self.manifest.release_preference
        )

        if curseforge_file is None:
            self.__logger(f"Unable to find file: {identifier}")
            return False

        self.manifest.curseforge_mods[identifier] = ModpackManifest.CurseForgeMod(
            identifier=identifier,
            version=None,
            url=CURSEFORGE_MOD_BASE_URL.format(identifier),
            server=True
        )

        self.curseforge_mods[identifier] = curseforge_mod
        self.curseforge_files[identifier] = curseforge_file

        return True

    def install_mods(self):
        self.fetch_curseforge_mods()
        self.find_curseforge_files()
        self.download_curseforge_files()

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
        self.__logger("Deleting previous package contents...")

        directories = list()

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

        self.__logger("Finished removing previous package contents.")
        self.__reporter.done()

    def extract_package(self, path):
        self.__logger(f"Reading package contents: {path.name}")
        self.__reporter.maximum = 1
        self.__reporter.value = 0

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

            user_shell_folders_key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
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

    @property
    def manifest(self):
        return self.__manifest

    @manifest.setter
    def manifest(self, manifest):
        # This abhorrent monkey-patch deserves explanation.
        # This is here because some attributes of this class need to be updated when attributes of `self.__manifest`
        # are updated. Unfortunately it seems that this is the only way to handle this specific issue.
        # A property getter for each field to generate on demand is not an ideal solution because
        # values could not be set without breaking synonomy with changes made to the manifest.
        # If properties were to be used for this class's fields, any user of this class would have to update
        # attributes of the manifest, and then the values generated could not possibly be diverged
        # from the default dependencies in the manifest.
        # A reference to this class's instance given to the manifest is also not an option because
        # the manifest class should be agnostic to any parents it may have.
        # Making this class inherit the manifest would pollute the namespace and is therefore also not an option.

        class __ModpackManifest(manifest.__class__):
            def __setattr__(self_, name, value):
                if name == "profile_id" and self_.profile_id:
                    if self.profile_directory is None or self.profile_directory.parent == self.profiles_directory:
                        self.profile_directory = self.profiles_directory / value

                    if self.mods_directory is None or self.mods_directory.parent == self.profile_directory:
                        self.mods_directory = self.profile_directory / "mods"

                    if self.runtime_directory is None or self.runtime_directory.parent == self.profile_directory:
                        self.runtime_directory = self.profile_directory / "runtime"

                super().__setattr__(name, value)

        manifest.__class__ = __ModpackManifest
        manifest.profile_id = manifest.profile_id

        self.__manifest = manifest
