import arrow
import requests
import itertools

from . import utilities


API_BASE_URL = "https://api.cfwidget.com/minecraft/mc-mods/{}"
CURSE_DOWNLOAD_URL = "https://edge.forgecdn.net/files/{}/{}/{}"


class VersionException(Exception):
    pass


def get_latest_mod_files(mod_files, game_versions):
    """
    Sort through versions of the mod files to find the best possible release.
    
    mod_files: The list of mod files JSON data to sort through.
    game_versions: Compatible semantic versions that should be accepted, in descending order of preference.
    stable: If this is false, the latest beta will be used. If true, the latest release is preferred.
    """
    mod_files = sorted(mod_files, key=lambda release: arrow.get(release["uploaded_at"]), reverse=True)
    releases = {}

    for mod_file, version in itertools.product(mod_files, game_versions):
        if version in mod_file["versions"] and mod_file["type"] not in releases:
            releases[mod_file["type"]] = mod_file

            if len(releases) == 3:
                break

            continue
    
    if not releases:
        raise VersionException("Unable to find a compatible version")

    return tuple(releases.values())


def get_mod_info(mod_slug, game_versions):
    """
    Takes a CurseForge project slug as input and returns original mod data, and only release
    assets compatible with listed game versions.
    """

    response = requests.get(API_BASE_URL.format(mod_slug))
    response.raise_for_status()
    mod_data = response.json()
    mod_data["releases"] = get_latest_mod_files(mod_data["files"], game_versions)

    del mod_data["downloads"]
    del mod_data["download"]
    del mod_data["versions"]

    return mod_data


def get_mod_lock_info(mod_slug, game_versions, release_preference):
    mod_info = get_mod_info(mod_slug, game_versions)
    
    if isinstance(release_preference, int):
        for mod_file in mod_info["files"]:
            if mod_file["id"] == release_preference:
                selected_file = mod_file
                break
        else:
            raise VersionException(f"Mod file '{release_preference}' for '{mod_slug}' not found")
    else:
        selected_file = utilities.get_suitable_release(mod_info["releases"], release_preference)

    file_id_str = str(selected_file["id"])
    
    return {
        "project_id": mod_info["id"],
        "project_url": mod_info["urls"]["curseforge"],
        "project_name": mod_info["title"],
        "file_id": selected_file["id"],
        "file_url": CURSE_DOWNLOAD_URL.format(file_id_str[:4], file_id_str[4:7], selected_file["name"]),
        "file_name": selected_file["name"],
        "release_type": selected_file["type"],
        "timestamp": arrow.get(selected_file["uploaded_at"]).timestamp
    }
