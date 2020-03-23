import os
import sys
import json
import shutil
import itertools
import subprocess

from pathlib import Path
from zipfile import ZipFile
from tempfile import TemporaryDirectory

from . import utilities
from . import curseforge

from .utilities import TqdmTracker

import arrow


TQDM_OPTIONS = {
    "unit": "b",
    "unit_scale": True,
    "dynamic_ncols": True
}


class ModpackBuilder:
    def __init__(self, meta, mc_dir, client=True):
        self.meta = meta
        self.mc_dir = Path(mc_dir)
        self.client = client
        self.profile_dir = self.mc_dir / "profiles" / self.meta["profile_id"]
        self.mods_dir = self.profile_dir / "mods"
        self.runtime_dir = self.profile_dir / "runtime"
        self.modlist = None
        self.modlist_path = self.profile_dir / "modlist.json"
        self.java_path = None

        self.profiles_file = self.mc_dir / "launcher_profiles.json"
        self.profile_id_file = self.profile_dir / "profile_id"
        self.profile_id = None

    def install(self):
        self.clean()
        self.install_mods()
        self.install_externals()
        self.install_runtime()
        self.install_forge()
        self.install_profile()

    def update(self):
        self.update_mods()
        self.update_externals()

    def clean(self):
        self.clean_mods()
        self.clean_externals()

    def _fetch_modlist(self):
        if self.modlist_path.exists() and self.modlist_path.is_file():
            self.load_modlist()
        else:
            self.create_modlist()

    def load_modlist(self):
        print("Loading modlist indormation...")

        with open(self.modlist_path, "r") as file:
            self.modlist = json.load(file)

    def _create_modlist(self, client=False):
        self.modlist = {}
        key = "client" if client else "server"

        print(f"Fetching modlist information for CurseForge {key} mods...")

        for project_slug, mod_lock_info in self.meta[key]["curseforge_mods"]:
            print("Fetching project information: " + project_slug)

            mod_lock_info = curseforge.get_mod_lock_info(project_slug, self.meta["game_versions"], self.meta["release_preference"])
            utilities.print_mod_lock_info(**mod_lock_info)
            self.modlist[project_slug] = mod_lock_info

        print(f"Creating modlist information for external {key} mods...")

        for project_slug, external_url in self.meta[{key}]["external_mods"]:
            response = requests.head(external_url)
            response.raise_for_status()

            self.modlist[project_slug] = {
                "external": True,
                "file_name": external_url.rsplit("/", 1)[1],
                "file_url": external_url,
                "timestamp": arrow.get(response.headers.get("last-modified", None)).timestamp
            }

    def create_modlist(self):
        self.modlist = _create_modlist(client=False)

        if self.client:
            self.modlist = {**self.modlist, **_create_modlist(client=True)}

        print("Dumping modlist information...")

        self.profile_dir.mkdir(parents=True, exist_ok=True)

        with open(self.modlist_path, "w") as file:
            json.dump(self.modlist, file, indent=True)

    def clean_mods(self):
        pass

    def clean_externals(self):
        pass

    def install_mods(self):
        self.mods_dir.mkdir(parents=True, exist_ok=True)

        if not self.modlist:
            self._fetch_modlist()

        print("Downloading CurseForge mod files...")

        for mod_info in self.modlist.values():
            mod_path = self.mods_dir / mod_info["file_name"]

            if mod_path.exists() and mod_path.is_file():
                print("Found existing mod file: " + mod_info["file_name"])
                continue

            utilities.download_as_stream(mod_info["file_url"], mod_info["file_name"], tracker=TqdmTracker(desc=mod_info["file_name"], **TQDM_OPTIONS))
            shutil.move(mod_info["file_name"], mod_path)

    def _install_externals(self, client=False):
        key = "client" if client else "server"

        print(f"Installing external files for {key}...")

        for file_path in itertools.chain(*(Path().resolve().glob(pattern) for pattern in self.meta[key]["external_files"])):
            if not file_path.is_file():
                continue

            short_path = file_path.relative_to(Path().resolve())
            dest_path = self.profile_dir / short_path

            if dest_path.exists() and dest_path.is_file():
                print("Found existing external file: " + str(short_path))
                continue

            print("Copying external file: " + str(short_path))

            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(file_path, dest_path)

    def install_externals(self):
        self._install_externals(client=False)

        if self.client:
            self._install_externals(client=True)

    def update_mods(self):
        pass

    def update_externals(self):
        pass

    def install_runtime(self):
        print("Downloading Java runtime...")

        file_url = self.meta["java_download"][{"win32": "win", "darwin": "mac"}.get(sys.platform, sys.platform)]
        file_name = file_url.rsplit("/", 1)[1]
        utilities.download_as_stream(file_url, file_name, tracker=TqdmTracker(desc=file_name, **TQDM_OPTIONS))

        print("Extracting Java runtime...")

        with ZipFile(file_name) as java_zip:
            java_zip.extractall(self.runtime_dir)

        self.java_path = Path(next(self.runtime_dir.glob("**/bin/javaw*")))

    def install_forge(self):
        if not self.java_path:
            self.install_runtime()

        print("Downloading Minecraft Forge installer...")

        file_name = self.meta["forge_download"].rsplit("/", 1)[1]
        utilities.download_as_stream(self.meta["forge_download"], file_name, tracker=TqdmTracker(desc=file_name, **TQDM_OPTIONS))

        print("Executing Minecraft Forge installer...")

        subprocess.run([str(self.java_path), "-jar", file_name], stdout=subprocess.DEVNULL)

    def install_profile(self):
        print("Installing launcher profile...")

        self.profile_id = utilities.get_profile_id(self.profile_id_file)

        with open(self.profiles_file, "r") as file:
            profiles = json.load(file)

        if self.profile_id in profiles["profiles"]:
            print("Launcher profile already exists: " + self.profile_id)
        else:
            utc_now = str(arrow.utcnow()).replace("+00:00", "Z")

            profiles["profiles"][self.profile_id] = {
                "created": utc_now,
                "gameDir": str(self.profile_dir.resolve()),
                "icon": self.meta["profile_icon"],
                "javaArgs": self.meta["java_args"],
                "javaDir": str(self.java_path.resolve()),
                "lastUsed": utc_now,
                "lastVersionId": self.meta["version_label"],
                "name": self.meta["profile_name"],
                "type": "custom"
            }

            print("Setting selected launcher profile: " + self.profile_id)
            
            profiles["selectedUser"]["profile"] = self.profile_id

            with open(self.profiles_file, "w") as file:
                json.dump(profiles, file, indent=2)

    def update_profile(self):
        pass

    def uninstall(self):
        pass
