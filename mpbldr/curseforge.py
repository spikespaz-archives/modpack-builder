import arrow
import requests


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

    for mod_file in mod_files:
        if len(releases) == 3:
            break

        for version in game_versions:
            if len(releases) == 3:
                break

            if version in mod_file["versions"] and mod_file["type"] not in releases:
                releases[mod_file["type"]] = mod_file
                continue
    
    if not releases:
        raise VersionException("Unable to find a compatible version")

    return releases


def get_mod_info(mod_slug, game_versions):
    """
    Takes a CurseForge project slug as input and returns original mod data, and only release
    assets compatible with listed game versions.
    """

    response = requests.get(API_BASE_URL.format(mod_slug))
    response.raise_for_status()
    mod_data = response.json()
    releases = get_latest_mod_files(mod_data["files"], game_versions)

    del mod_data["downloads"]
    del mod_data["files"]
    del mod_data["versions"]
    del mod_data["download"]

    mod_data["releases"] = releases

    return mod_data


def get_mod_lock_info(mod_slug, game_versions, release_preference):
    mod_info = get_mod_info(mod_slug, game_versions)
    mod_release = None

    for version_type in release_preference:
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
