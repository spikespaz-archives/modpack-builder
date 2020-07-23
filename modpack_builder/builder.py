import os
import sys
import json
import shutil
import itertools
import subprocess
import concurrent.futures

from pathlib import Path
from zipfile import ZipFile
from tempfile import TemporaryDirectory
from concurrent.futures import ThreadPoolExecutor

from . import utilities
from . import curseforge

from .utilities import TqdmTracker

import arrow

from tqdm import tqdm


TQDM_OPTIONS = {
    "file": sys.stdout,
    "unit": "b",
    "unit_scale": True,
    "dynamic_ncols": True,
    "miniters": -1
}


class ModpackBuilder:
    def __init__(self, meta, mc_dir, client=True, concurrent_requests=8, concurrent_downloads=8, stdout=sys.stdout):
        self.meta = meta
        self.mc_dir = Path(mc_dir)
        self.client = client
        self.concurrent_requests = concurrent_requests
        self.concurrent_downloads = concurrent_downloads
        self.stdout = stdout

        if self.client:
            self.profile_dir = self.mc_dir / "profiles" / self.meta["profile_id"]
        else:
            self.profile_dir = self.mc_dir

        self.mods_dir = self.profile_dir / "mods"
        self.runtime_dir = self.profile_dir / "runtime"
        self.version_dir = self.mc_dir / "versions" / self.meta["version_label"]
        self.modlist = None
        self.modlist_path = self.profile_dir / "modlist.json"
        self.java_path = None

        self.profiles_file = self.mc_dir / "launcher_profiles.json"
        self.profile_id_file = self.profile_dir / "profile_id"
        self.profile_id = None

        self.__exit = False

    def __thread(self, target):
        def __wrapper(*args, **kwargs):
            if self.__exit:
                return

            return target(*args, **kwargs)

        return __wrapper

    def stop(self):
        self.__exit = True

    def install(self):
        self.install_mods()
        self.install_externals()
        self._fetch_runtime()
        self._fetch_forge()

        if self.client:
            self.install_profile()

    def update(self):
        self._fetch_modlist()
        self.update_mods()
        self.update_externals()
        self._fetch_runtime()
        self._fetch_forge()
        
        if self.client:
            self.update_profile()

    def _fetch_modlist(self):
        if self.modlist_path.exists() and self.modlist_path.is_file():
            self.load_modlist()
        else:
            self.create_modlist()

    def load_modlist(self):
        print("Loading modlist indormation...", file=self.stdout)

        with open(self.modlist_path, "r") as file:
            self.modlist = json.load(file)

    def _create_modlist(self, client=False):
        modlist = {}
        key = "client" if client else "server"

        with ThreadPoolExecutor(max_workers=self.concurrent_requests) as executor:
            print(f"Fetching modlist information for {key} mods...", file=self.stdout)

            futures_map = {}
            
            for identifier in self.meta[key]["curseforge_mods"]:
                if ":" in identifier:
                    project_slug, release_preference = map(str.strip, identifier.split(":"))
                    
                    if release_preference not in utilities.RELEASE_TYPES:
                        release_preference = int(release_preference)
                else:
                    project_slug, release_preference = identifier, self.meta["release_preference"]

                future = executor.submit(self.__thread(curseforge.get_mod_lock_info), project_slug, self.meta["game_versions"], release_preference)
                futures_map[future] = project_slug
            
            for project_slug, external_url in self.meta[key]["external_mods"].items():
                future = executor.submit(self.__thread(utilities.get_external_mod_lock_info), external_url)
                futures_map[future] = project_slug
            
            try:
                for future in concurrent.futures.as_completed(futures_map):
                    project_slug = futures_map[future]
                    mod_info = future.result()
                    
                    if project_slug in self.meta["load_priority"]:
                        priority_index = self.meta["load_priority"].index(project_slug)
                        mod_info["file_name"] = f"_{priority_index}-{mod_info['file_name']}"

                    modlist[project_slug] = mod_info

                    if project_slug in self.meta[key]["external_mods"]:
                        utilities.print_external_mod_lock_info(project_slug, **mod_info)
                    else:
                        utilities.print_curseforge_mod_lock_info(project_slug, **mod_info)
            except KeyboardInterrupt as error:
                self.stop()
                raise error

        return modlist

    def create_modlist(self):
        self.modlist = self._create_modlist(client=False)

        if self.client:
            self.modlist = {**self.modlist, **self._create_modlist(client=True)}

        print("Dumping modlist information...", file=self.stdout)

        self.profile_dir.mkdir(parents=True, exist_ok=True)

        with open(self.modlist_path, "w") as file:
            json.dump(self.modlist, file, indent=2)

    def clean_mods(self):
        print("Cleaning mod directory of unlisted files...", file=self.stdout)
        file_names = [mod_info["file_name"] for mod_info in self.modlist.values()]

        for file_path in self.mods_dir.glob("*.jar"):
            if not file_path.is_file():
                continue

            if file_path.name not in file_names:
                print(f"Removing unlisted mod file: {file_path.name}", file=self.stdout)

                file_path.unlink()

    def install_mods(self):
        if not self.modlist:
            self._fetch_modlist()

        print("Checking for existing mod files...", file=self.stdout)

        download_mods = []

        for mod_info in self.modlist.values():
            mod_path = self.mods_dir / mod_info["file_name"]

            if mod_path.exists() and mod_path.is_file():
                print(f"Found existing mod file: {mod_info['file_name']}", file=self.stdout)
                continue

            download_mods.append(mod_info)

        with ThreadPoolExecutor(
            max_workers=self.concurrent_downloads,
            initializer=tqdm.set_lock,
            initargs=(tqdm.get_lock(),)
        ) as executor:
            print("Downloading missing mod files...", file=self.stdout)

            self.mods_dir.mkdir(parents=True, exist_ok=True)

            futures_map = {}

            for mod_info in download_mods:
                future = executor.submit(
                    self.__thread(utilities.download_as_stream),
                    file_url=mod_info["file_url"],
                    file_path=mod_info["file_name"],
                    tracker=TqdmTracker(desc=mod_info["file_name"], **TQDM_OPTIONS)
                )
                futures_map[future] = mod_info["file_name"]

            try:
                for future in concurrent.futures.as_completed(futures_map):
                    shutil.move(futures_map[future], self.mods_dir)
            except KeyboardInterrupt as error:
                self.stop()
                raise error

    def _install_externals(self, patterns, overwrite=False):
        # Loop through all file paths from all glob patterns in sequence
        for file_path in itertools.chain(*(Path().glob(pattern) for pattern in patterns)):
            if not file_path.is_file():  # Make sure the path returned by glob is actually a file
                continue

            dest_path = self.profile_dir / file_path

            if dest_path.exists():
                if overwrite:
                    print(f"Overwriting external file: {file_path}", file=self.stdout)
                else:
                    print(f"Skipping existing external file: {file_path}", file=self.stdout)
                    continue  # Skip to the next without overwriting the current file
            else:
                print(f"Copying external file: {file_path}", file=self.stdout)

            dest_path.parent.mkdir(parents=True, exist_ok=True)  # Ensure that the parents dirs of the file exist
            shutil.copyfile(file_path, dest_path)

    def install_externals(self, update=False):
        log_verb = "Updating" if update else "Installing"

        print(f"{log_verb} external files for server...", file=self.stdout)

        # Install overwritable external server files and maybe overwrite existing
        self._install_externals(self.meta["server"]["external_files"]["overwrite"], overwrite=update)
        # Install immutable external client files and never overwrite existing
        self._install_externals(self.meta["server"]["external_files"]["immutable"], overwrite=False)

        if self.client:
            if not update:
                print(f"{log_verb} external files for client...", file=self.stdout)

            # Install overwritable external client files and maybe overwrite existing
            self._install_externals(self.meta["client"]["external_files"]["overwrite"], overwrite=update)
            # Install immutable external client files and never overwrite existing
            self._install_externals(self.meta["client"]["external_files"]["immutable"], overwrite=False)

    def update_mods(self):
        self.create_modlist()
        self.clean_mods()
        self.install_mods()

    def update_externals(self):
        self.install_externals(update=True)

    def install_runtime(self):
        print("Downloading Java runtime...", file=self.stdout)

        file_url = self.meta["java_download"][{"win32": "win", "darwin": "mac"}.get(sys.platform, sys.platform)]
        file_name = file_url.rsplit("/", 1)[1]
        utilities.download_as_stream(file_url, file_name, tracker=TqdmTracker(desc=file_name, **TQDM_OPTIONS))

        print("Extracting Java runtime...", file=self.stdout)

        with ZipFile(file_name) as java_zip:
            java_zip.extractall(self.runtime_dir)

        self.java_path = Path(next(self.runtime_dir.glob("**/bin/javaw*")))

    def _fetch_runtime(self):
        java_path = next(self.runtime_dir.glob("**/bin/javaw*"), None)

        if java_path:
            print(f"Java runtime already installed: {java_path.relative_to(self.runtime_dir)}", file=self.stdout)
            self.java_path = Path(java_path)
            return

        self.install_runtime()

    def install_forge(self):
        if not self.java_path:
            self._fetch_runtime()

        print("Downloading Minecraft Forge installer...", file=self.stdout)

        file_name = self.meta["forge_download"].rsplit("/", 1)[1]
        utilities.download_as_stream(self.meta["forge_download"], file_name, tracker=TqdmTracker(desc=file_name, **TQDM_OPTIONS))

        print(f"Executing Minecraft Forge installer: {file_name}", file=self.stdout)

        subprocess.run([str(self.java_path), "-jar", file_name], stdout=subprocess.DEVNULL)

    def _fetch_forge(self):
        if self.version_dir.exists() and self.version_dir.is_dir():
            print(f"Forge version already installed: {self.meta['version_label']}", file=self.stdout)
            return

        self.install_forge()

    def install_profile(self, update=False):
        self.profile_id = utilities.get_profile_id(self.profile_id_file)

        with open(self.profiles_file, "r") as file:
            profiles = json.load(file)

        if self.profile_id in profiles["profiles"]:
            if update:
                print(f"Updating launcher profile: {self.profile_id}", file=self.stdout)
            else:
                print(f"Launcher profile already exists: {self.profile_id}", file=self.stdout)
                return
        else:
            print("Installing launcher profile...", file=self.stdout)
        
        utc_now = str(arrow.utcnow()).replace("+00:00", "Z")

        profiles["profiles"][self.profile_id] = {
            "created": utc_now,
            "gameDir": str(self.profile_dir.resolve()),
            "icon": self.meta["profile_icon"],
            "javaArgs": self.meta["client"]["java_args"],
            "javaDir": str(self.java_path.resolve()),
            "lastUsed": utc_now,
            "lastVersionId": self.meta["version_label"],
            "name": self.meta["profile_name"],
            "type": "custom"
        }

        print(f"Setting selected launcher profile: {self.profile_id}", file=self.stdout)
        
        profiles["selectedUser"]["profile"] = self.profile_id

        with open(self.profiles_file, "w") as file:
            json.dump(profiles, file, indent=2)

    def update_profile(self):
        self.install_profile(update=True)

    def remove_profile(self):
        self.profile_id = utilities.get_profile_id(self.profile_id_file)
        print(f"Uninstalling launcher profile: {self.profile_id}", file=self.stdout)

        with open(self.profiles_file, "r") as file:
            profiles = json.load(file)

        del profiles["profiles"][self.profile_id]

        selected_profile = next(iter(profiles["profiles"]))

        print(f"Setting selected launcher profile: {selected_profile}", file=self.stdout)
        profiles["selectedUser"]["profile"] = selected_profile

        with open(self.profiles_file, "w") as file:
            json.dump(profiles, file, indent=2)

    def uninstall(self):
        try:
            self.remove_profile()
        except KeyError:
            print(f"Launcher profile not found: {self.profile_id}", file=self.stdout)

        print("Removing modpack files...", file=self.stdout)

        directories = []

        for path in self.profile_dir.glob("**/*"):
            if path.is_dir():
                directories.append(path)
                continue

            print(f"Deleting file: {path.relative_to(self.profile_dir)}", file=self.stdout)
            path.unlink()

        for path in reversed(directories):
            print(f"Deleting directory: {path.relative_to(self.profile_dir)}", file=self.stdout)
            path.rmdir()

        print("Deleting profile directory...", file=self.stdout)
        self.profile_dir.rmdir()
