import os
import sys
import json
import secrets

import tqdm
import arrow
import requests

from pathlib import Path
from tempfile import TemporaryDirectory

API_BASE_URL = "https://api.cfwidget.com/minecraft/mc-mods"


class VersionException(Exception):
    pass


class ProfileExistsException(Exception):
    pass


class DownloadException(Exception):
    pass


class ProgressTracker:
    def __init__(self, total=0):
        self.total = total
        self.value = 0

    def update(self, amount):
        self.value += amount

    def close(self):
        pass


class TqdmTracker(ProgressTracker):
    def __init__(self, **kwargs):
        self._tqdm = None
        self._kwargs = kwargs

        if "total" in kwargs:
            self.total(kwargs["total"])

    @property
    def total(self):
        return self._tqdm.total

    @total.setter
    def total(self, size):
        self._tqdm = tqdm.tqdm(total=size, **self._kwargs)

    @property
    def value(self):
        return self._tqdm.n

    def update(self, amount):
        self._tqdm.update(amount)

    def close(self):
        self._tqdm.close()


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


def get_profile_id(id_file):
    """
    Create a 32 character hexadecimal token, and write it to the file. Fetch if the file exists.
    """
    if id_file.exists():
        with open(id_file, "r") as file:
            profile_id = file.read()
    else:
        profile_id = secrets.token_hex(16)

        with open(id_file, "w") as file:
            file.write(profile_id)


def add_launcher_profile(minecraft, profile_dir, profile_name, profile_icon, java_args, java_path, version_id):
    minecraft = Path(minecraft)
    profiles = None
    profiles_file = minecraft / "launcher_profiles.json"
    profile_id_file = profile_dir / "profile_id"
    profile_id = get_profile_id(profile_id_file)

    with open(profiles_file, "r") as file:
        profiles = json.load(file)

    if profile_id in profiles["profiles"]:
        raise ProfileExistsException("Profile already in launcher profiles: " + profile_id)
    else:
        utc_now = arrow.utcnow().replace("+00:00", "Z")

        profiles["profiles"][profile_id] = {
            "created": utc_now,
            "gameDir": str(profile_dir.resolve()),
            "icon": profile_icon,
            "javaArgs": java_args,
            "javaDir": str(java_path.resolve()),
            "lastUsed": utc_now,
            "lastVersionId": version_id,
            "name": profile_name,
            "type": "custom"
        }

        profiles["selectedUser"]["profile"] = profile_id

        with open(profiles_file, "w") as file:
            json.dump(profiles, file, indent=2)


def install_mc_forge(minecraft, forge_download, java_path):
    response = requests.get(forge_download, allow_redirects=True)
    response.raise_for_status()

    versions_dir = Path(minecraft) / "versions"
    versions_list = set(versions_dir.iterdir())

    with TemporaryDirectory() as temp_dir:
        installer = Path(temp_dir) / "forge_installer.jar"

        with open(installer, "w") as file:
            file.write(response.content)

        subprocess.run([java_path, "-jar", installer])

    return [set(versions_dir.iterdir()) - versions_list][0].stem


if __name__ == "__main__":
    pack_meta = None
    mods_lock = {}

    with open("modpack.json", "r") as file:
        pack_meta = json.load(file)

    os.makedirs("mods", exist_ok=True)

    for mod_slug in pack_meta["curse_mods"]:
        mod_info = get_mod_info(mod_slug, pack_meta["game_versions"])
