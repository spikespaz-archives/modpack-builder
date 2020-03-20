import os
import sys
import json
import secrets
import subprocess

import tqdm
import arrow
import requests

from pathlib import Path
from tempfile import TemporaryDirectory

API_BASE_URL = "https://api.cfwidget.com/minecraft/mc-mods/{}"
CURSE_DOWNLOAD_URL = "https://edge.forgecdn.net/files/{}/{}/{}"
TQDM_OPTIONS = {
    "unit": "b",
    "unit_scale": True,
    "dynamic_ncols": True
}

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

    response = requests.get(API_BASE_URL.format(mod_slug))
    response.raise_for_status()
    mod_data = response.json()
    releases = get_mod_files(mod_data["versions"], game_versions)

    del mod_data["downloads"]
    del mod_data["files"]
    del mod_data["versions"]
    del mod_data["download"]

    mod_data["releases"] = releases

    return mod_data


def get_mod_lock_info(mod_slug, game_versions):
    mod_info = get_mod_info(mod_slug, game_versions)
    mod_release = None

    for version_type in pack_meta["release_preference"]:
        if not mod_release and version_type in mod_info["releases"]:
            mod_release = mod_info["releases"][version_type]

    file_id = str(mod_release["id"])
    
    return {
        "project_id": str(mod_info["id"]),
        "project_url": mod_info["urls"]["curseforge"],
        "project_name": mod_info["title"],
        "file_id": file_id,
        "file_url": CURSE_DOWNLOAD_URL.format(file_id[:4], file_id[4:7], mod_release["name"]),
        "file_name": mod_release["name"],
        "release_type": mod_release["type"]
    }


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


def add_launcher_profile(minecraft_dir, profile_dir, profile_name, profile_icon, java_args, java_path, version_id):
    minecraft_dir = Path(minecraft_dir)
    profiles = None
    profiles_file = minecraft_dir / "launcher_profiles.json"
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


def download_as_stream(file_url, file_path, tracker=ProgressTracker(), block_size=1024, **kwargs):
    response = requests.get(file_url, stream=True, allow_redirects=True, **kwargs)
    response.raise_for_status()

    tracker.total = int(response.headers.get("content-length", 0))

    with open(file_path, "wb") as file:
        for data in response.iter_content(block_size):
            tracker.update(len(data))
            file.write(data)

    tracker.close()

    if tracker.total != 0 and tracker.value != tracker.total:
        raise DownloadException("Downloaded bytes did not match 'content-length' header")


def install_mc_forge(minecraft_dir, forge_download, java_path, tracker=ProgressTracker()):
    """
    Downloads and executes the Forge installer.
    """
    versions_dir = Path(minecraft_dir) / "versions"

    with TemporaryDirectory() as temp_dir:
        installer_path = Path(temp_dir) / "forge_installer.jar"

        download_as_stream(forge_download, installer_path, tracker=tracker)

        start_directory = os.getcwd()
        os.chdir(temp_dir)
        
        subprocess.run([java_path, "-jar", str(installer_path)], stdout=subprocess.DEVNULL)
        os.chdir(start_directory)


if __name__ == "__main__":
    pack_meta = None
    mods_lock = {}

    with open("modpack/modpack.json", "r") as file:
        pack_meta = json.load(file)

    for mod_slug in pack_meta["curse_mods"]:
        print("Looking up CurseForge project: " + mod_slug)
        mods_lock[mod_slug] = get_mod_lock_info(mod_slug, pack_meta["game_versions"])

        print("Project ID: {project_id}\nProject Name: {project_name}\nProject URL: {project_url}\nRelease Type: {release_type}\nDownload URL: {file_url}\n".format(**mods_lock[mod_slug]))

    with open("modlist.lock.json", "w") as file:
        json.dump(mods_lock, file, indent=True)

    # minecraft_dir = Path(os.getenv("appdata")) / ".minecraft"

    # mods_dir = Path("./mods")
    # os.makedirs(mods_dir, exist_ok=True)

    # install_mc_forge(minecraft_dir, pack_meta["forge_download"], "java", tracker=TqdmTracker(**TQDM_OPTIONS))
