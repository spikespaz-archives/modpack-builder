import os
import sys
import json

from pathlib import Path

from mpbldr import curseforge


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

    print("Gathering modlist information...\n")

    mods_lock = {}

    for mod_slug in pack_meta["curse_mods"]:
        print("Fetching project information: " + mod_slug)
        mods_lock[mod_slug] = curseforge.get_mod_lock_info(mod_slug, pack_meta["game_versions"], pack_meta["release_preference"])
        print((
            "  Project ID: {project_id}\n" +
            "  Project URL: {project_url}\n" + 
            "  Project Name: {project_name}\n" +
            "  File ID: {file_id}\n" +
            "  File URL: {file_url}\n" +
            "  File Name: {file_name}\n" +
            "  Release Type: {release_type}"
            ).format(**mods_lock[mod_slug]))

    print("Dumping modlist information...")

    with open("modlist.lock.json", "w") as file:
        json.dump(mods_lock, file, indent=True)

    # minecraft_dir = Path(os.getenv("appdata")) / ".minecraft"

    # mods_dir = Path("./mods")
    # os.makedirs(mods_dir, exist_ok=True)

    # install_mc_forge(minecraft_dir, pack_meta["forge_download"], "java", tracker=TqdmTracker(**TQDM_OPTIONS))
