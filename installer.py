import os
import sys
import json
import subprocess

from pathlib import Path
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

    if modlist_lock_path.exists():
        print("Loading modlist information...")

        with open(modlist_lock_path, "r") as file:
            modlist_lock = json.load(file)
    else:
        print("Gathering modlist information...")

        modlist_lock = {}

        for mod_slug in pack_meta["curse_mods"]:
            print("Fetching project information: " + mod_slug)
            
            modlist_lock[mod_slug] = curseforge.get_mod_lock_info(mod_slug, pack_meta["game_versions"], pack_meta["release_preference"])
            
            print((
                "  Project ID: {project_id}\n" +
                "  Project URL: {project_url}\n" + 
                "  Project Name: {project_name}\n" +
                "  File ID: {file_id}\n" +
                "  File URL: {file_url}\n" +
                "  File Name: {file_name}\n" +
                "  Release Type: {release_type}"
                ).format(**modlist_lock[mod_slug]))

        print("Dumping modlist information...")

        with open(modlist_lock_path, "w") as file:
            json.dump(modlist_lock, file, indent=True)

    print("Downloading mod files...")

    for mod_info in modlist_lock.values():
        mod_file_path = mods_dir / mod_info["file_name"]

        if mod_file_path.exists() and mod_file_path.is_file():
            print("Found existing mod file: " + mod_info["file_name"])
            continue

        utility.download_as_stream(mod_info["file_url"], mod_file_path, tracker=TqdmTracker(desc=mod_info["file_name"], **TQDM_OPTIONS))

    print("Downloading external mod files...")

    for mod_url in pack_meta["external_mods"]:
        mod_file_name = mod_url.rsplit("/", 1)[1]

        mod_file_path = mods_dir / mod_file_name

        if mod_file_path.exists() and mod_file_path.is_file():
            print("Found existing mod file: " + mod_info["file_name"])
            continue

        utility.download_as_stream(mod_url, mod_file_path, tracker=TqdmTracker(desc=mod_file_name, **TQDM_OPTIONS))

    print("Downloading Minecraft Forge installer...")

    forge_jar_name = pack_meta["forge_download"].rsplit("/", 1)[1]
    forge_jar_path = temp_dir / forge_jar_name

    utility.download_as_stream(pack_meta["forge_download"], forge_jar_path, tracker=TqdmTracker(desc=forge_jar_name, **TQDM_OPTIONS))

    print("Executing Minecraft Forge installer...")

    subprocess.run([java_path, "-jar", str(forge_jar_path)], stdout=subprocess.DEVNULL)

    os.chdir(orig_dir)
    temp_dir_manager.cleanup()