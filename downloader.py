import json
import requests
import sys
import os
import arrow

API_BASE_URL = "https://api.cfwidget.com/minecraft/mc-mods"


class VersionException(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

def get_latest_mod_files(version_lists, compat_versions):
    """
    Sort through versions of the mod files to find the best possible release.
    
    versions_lists: The version lists to sort through.
    compat_versions: Compatible semantic versions that should be accepted, in descending order of preference.
    stable: If this is false, the latest beta will be used. If true, the latest release is preferred.
    """
    releases = None

    for version in compat_versions:
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

if __name__ == "__main__":
    pack_meta = None
    mods_lock = {}

    with open("modpack.json", "r") as file:
        pack_meta = json.load(file)

    os.makedirs("mods", exist_ok=True)

    for mod_slug in pack_meta["curse_mods"]:
        print("Fetching mod: " + mod_slug)

        response = requests.get(API_BASE_URL + "/" + mod_slug)
        mod_data = response.json()

        print("Found mod: " + mod_data["title"])

        latest = get_latest_mod_files(mod_data["versions"], pack_meta["compat_versions"])

        empty_version = {"name": None}

        latest_release = latest.get("release", empty_version).get("name")
        beta_release = latest.get("beta", empty_version).get("name")
        alpha_release = latest.get("alpha", empty_version).get("name")

        print("Release: {}\nBeta: {}\nAlpha: {}".format(latest_release, beta_release, alpha_release))
