import os
import sys
import json
import shutil
import subprocess

from pathlib import Path
from zipfile import ZipFile
from tempfile import TemporaryDirectory

from mpbldr import curseforge
from mpbldr import utility

from mpbldr.utility import TqdmTracker


TQDM_OPTIONS = {
    "unit": "b",
    "unit_scale": True,
    "dynamic_ncols": True
}


if __name__ == "__main__":
    mc_dir = Path(os.getenv("appdata")) / ".minecraft"
    profile_dir = mc_dir / "profiles"
    temp_dir_manager = TemporaryDirectory()
    temp_dir = Path(temp_dir_manager.name)
    orig_dir = Path(os.getcwd())
    modlist_lock_path = orig_dir / "modpack/modlist.lock.json"
    modlist_lock = None
    mods_dir = orig_dir / "mods"
    mods_dir.mkdir(exist_ok=True)
    pack_manifest_path = orig_dir / "modpack/modpack.json"

    java_path = "java"

    os.chdir(temp_dir)

    pack_meta = None

    print("Loading modpack metadata...")

    with open(pack_manifest_path, "r") as file:
        pack_meta = json.load(file)

    print("Downloading Minecraft Forge installer...")

    forge_jar_name = pack_meta["forge_download"].rsplit("/", 1)[1]
    forge_jar_path = temp_dir / forge_jar_name

    utility.download_as_stream(pack_meta["forge_download"], forge_jar_path, tracker=TqdmTracker(desc=forge_jar_name, **TQDM_OPTIONS))

    print("Executing Minecraft Forge installer...")

    subprocess.run([java_path, "-jar", str(forge_jar_path)], stdout=subprocess.DEVNULL)

    os.chdir(orig_dir)
    temp_dir_manager.cleanup()


class ModpackBuilder:
    def __init__(self, meta, mc_dir):
        self.meta = meta
        self.mc_dir = Path(mc_dir)
        self.profile_dir = self.mc_dir / "profiles" / self.meta["profile_id"]
        self.mods_dir = self.profile_dir / "mods"
        self.config_dir = self.profile_dir / "config"
        self.modlist = None
        self.modlist_path = self.profile_dir / "modlist.json"

    def install(self):
        self.clean()
        self.install_mods()
        self.install_configs()
        self.install_runtime()
        self.install_forge()
        self.install_profile()

    def update(self):
        self.update_mods()
        self.update_configs()

    def clean(self):
        self.clean_mods()
        self.clean_configs()

    def _fetch_modlist(self):
        if self.modlist_path.exists() and self.modlist_path.is_file():
            self.load_modlist()
        else:
            self.create_modlist()

    def load_modlist(self):
        print("Loading modlist indormation...")

        with open(self.modlist_path, "r") as file:
            self.modlist = json.load(file)

    def create_modlist(self):
        print("Creating modlist information...")

        self.modlist = {}

        for project_slug in self.meta["curse_mods"]:
            print("Fetching project information: " + project_slug)
            
            self.modlist[project_slug] = curseforge.get_mod_lock_info(project_slug, self.meta["game_versions"], self.meta["release_preference"])
            
            print((
                "  Project ID: {project_id}\n" +
                "  Project URL: {project_url}\n" + 
                "  Project Name: {project_name}\n" +
                "  File ID: {file_id}\n" +
                "  File URL: {file_url}\n" +
                "  File Name: {file_name}\n" +
                "  Release Type: {release_type}"
                ).format(**self.modlist[project_slug]))

        print("Dumping modlist information...")

        self.profile_dir.mkdir(parents=True, exist_ok=True)

        with open(self.modlist_path, "w") as file:
            json.dump(self.modlist, file, indent=True)

    def clean_mods(self):
        pass

    def clean_configs(self):
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

            utility.download_as_stream(mod_info["file_url"], mod_info["file_name"], tracker=TqdmTracker(desc=mod_info["file_name"], **TQDM_OPTIONS))
            shutil.move(mod_info["file_name"], mod_path)

        print("Downloading external mod files...")

        for mod_url in self.meta["external_mods"]:
            file_name = mod_url.rsplit("/", 1)[1]
            mod_path = self.mods_dir / file_name

            if mod_path.exists() and mod_path.is_file():
                print("Found existing mod file: " + file_name)
                continue
            
            utility.download_as_stream(mod_url, file_name, tracker=TqdmTracker(desc=file_name, **TQDM_OPTIONS))
            shutil.move(file_name, mod_path)


    def install_configs(self):
        self.configs_dir.mkdir(parents=True, exist_ok=True)

    def update_mods(self):
        pass

    def update_configs(self):
        pass

    def install_runtime(self):
        pass

    def install_forge(self):
        pass

    def install_profile(self):
        pass

    def update_profile(self):
        pass

    def uninstall(self):
        pass
