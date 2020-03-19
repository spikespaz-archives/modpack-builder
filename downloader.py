import json
import requests
import sys
import os
import arrow

API_BASE_URL = "https://api.cfwidget.com/minecraft/mc-mods"


class VersionException(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


def get_mod_files(version_lists, game_versions):
    """
    Sort through versions of the mod files to find the best possible release.
    
    versions_lists: The version lists to sort through.
    game_versions: Compatible semantic versions that should be accepted, in descending order of preference.
    stable: If this is false, the latest beta will be used. If true, the latest release is preferred.
    """
    releases = None

    for version in game_versions:
        if version in version_lists:
            releases = version_lists[version]
            break
    else:
        raise VersionException("Unable to find a compatible version")

    # Sort the assets in descending order of the time of which they were uploaded
    releases = sorted(releases, key=lambda release: arrow.get(release["uploaded_at"]), reverse=True)

    latest = {}

    for release in releases:
        if release["type"] not in latest:
            latest[release["type"]] = release

    return latest


def get_mod_info(mod_slug, game_versions):
    """
    Takes a CurseForge project slug as input and returns original mod data, and only release
    assets compatible with listed game versions.
    """

    response = requests.get(API_BASE_URL + "/" + mod_slug)
    response.raise_for_status()
    mod_data = response.json()
    releases = get_mod_files(mod_data["versions"], game_versions)

    del mod_data["downloads"]
    del mod_data["files"]
    del mod_data["versions"]
    del mod_data["download"]

    mod_data["releases"] = releases

    return mod_data

if __name__ == "__main__":
    pack_meta = None
    mods_lock = {}

    with open("modpack.json", "r") as file:
        pack_meta = json.load(file)

    os.makedirs("mods", exist_ok=True)

    for mod_slug in pack_meta["curse_mods"]:
        mod_info = get_mod_info(mod_slug, pack_meta["game_versions"])
