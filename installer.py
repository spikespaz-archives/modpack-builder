import os
import sys
import json

from pathlib import Path

from mpbldr import curseforge
from mpbldr import utility

from mpbldr.utility import TqdmTracker


TQDM_OPTIONS = {
    "unit": "b",
    "unit_scale": True,
    "dynamic_ncols": True
}


if __name__ == "__main__":
    print("Loading modpack metadata...")

    pack_meta = None

    with open("modpack/modpack.json", "r") as file:
        pack_meta = json.load(file)

    modlist_lock_path = Path("modlist.lock.json")
    modlist_lock = None

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

    mods_dir = Path("mods")
    mods_dir.mkdir(exist_ok=True)

    for mod_info in modlist_lock.values():
        utility.download_as_stream(mod_info["file_url"], mods_dir / mod_info["file_name"], tracker=TqdmTracker(desc=mod_info["file_name"], **TQDM_OPTIONS))

    # minecraft_dir = Path(os.getenv("appdata")) / ".minecraft"

    # install_mc_forge(minecraft_dir, pack_meta["forge_download"], "java", tracker=TqdmTracker(**TQDM_OPTIONS))
