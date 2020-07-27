import itertools
import dataclasses

from enum import Enum

import arrow
import requests

from arrow import Arrow
from orderedset import OrderedSet


API_BASE_URL = "https://api.cfwidget.com/minecraft/mc-mods/{}"
CURSE_DOWNLOAD_URL = "https://edge.forgecdn.net/files/{}/{}/{}"


class ReleaseType(Enum):
    release = "release"
    beta = "beta"
    alpha = "alpha"


ReleaseType.values = [member.value for member in ReleaseType]


class CurseForgeMod:
    @dataclasses.dataclass
    class UrlsEntry:
        curseforge: str = None
        project: str = None

    @dataclasses.dataclass
    class DownloadsEntry:
        monthly: int = None
        total: int = None

    @dataclasses.dataclass(frozen=True)
    class MemberEntry:
        title: str = None
        username: str = None

    @dataclasses.dataclass(frozen=True)
    class FileEntry:
        id: int = None
        url: str = None
        display: str = None
        name: str = None
        type: ReleaseType = None
        version: str = None
        filesize: int = None
        versions: frozenset = None
        downloads: int = None
        uploaded_at: Arrow = None

    def __init__(self, identifier, **kwargs):
        self.__identifier = identifier

        self.__id = kwargs.get("id")
        self.__title = kwargs.get("title")
        self.__summary = kwargs.get("summary")
        self.__game = kwargs.get("game")
        self.__type = kwargs.get("type")
        self.__urls = CurseForgeMod.UrlsEntry(**kwargs.get("urls", dict()))
        self.__thumbnail = kwargs.get("thumbnail")
        self.__created_at = arrow.get(kwargs["created_at"]) if kwargs.get("created_at") else None
        self.__downloads = CurseForgeMod.DownloadsEntry(**kwargs.get("downloads", dict()))
        self.__license = kwargs.get("license")
        self.__donate = kwargs.get("donate")
        self.__categories = OrderedSet(kwargs.get("categories", tuple()))
        self.__members = OrderedSet(CurseForgeMod.MemberEntry(**member) for member in kwargs.get("members", tuple()))
        self.__links = set(kwargs.get("links"))

        self.__files = set()

        for file in kwargs.get("files", tuple()):
            file["type"] = ReleaseType(file["type"]) if file.get("type") else None
            file["versions"] = frozenset(file.get("versions", tuple()))
            file["uploaded_at"] = arrow.get(file["uploaded_at"]) if file.get("uploaded_at") else None

            self.__files.add(CurseForgeMod.FileEntry(**file))

        self.__versions = dict()

        for version, files in kwargs.get("versions", dict()).items():
            self.__versions[version] = set()

            for file in files:
                file["type"] = ReleaseType(file["type"]) if file.get("type") else None
                file["versions"] = frozenset(file.get("versions", tuple()))
                file["uploaded_at"] = arrow.get(file["uploaded_at"]) if file.get("uploaded_at") else None

                self.__versions[version].add(CurseForgeMod.FileEntry(**file))

        self.__description = kwargs.get("description")
        self.__last_fetch = arrow.get(kwargs["last_fetch"]) if kwargs.get("last_fetch") else None
        self.__download = kwargs.get("download")

    @staticmethod
    def get(identifier):
        response = requests.get(API_BASE_URL.format(identifier))
        response.raise_for_status()

        return CurseForgeMod(identifier, **response.json())

    @property
    def id(self):
        return self.__id

    @property
    def title(self):
        return self.__title

    @property
    def summary(self):
        return self.__summary

    @property
    def game(self):
        return self.__game

    @property
    def type(self):
        return self.__type

    @property
    def urls(self):
        return self.__urls

    @property
    def thumbnail(self):
        return self.__thumbnail

    @property
    def created_at(self):
        return self.__created_at

    @property
    def downloads(self):
        return self.__downloads

    @property
    def license(self):
        return self.__license

    @property
    def donate(self):
        return self.__donate

    @property
    def categories(self):
        return self.__categories

    @property
    def members(self):
        return self.__members

    @property
    def links(self):
        return self.__links

    @property
    def files(self):
        return self.__files

    @property
    def versions(self):
        return self.__versions

    @property
    def description(self):
        return self.__description

    @property
    def last_fetch(self):
        return self.__last_fetch

    @property
    def download(self):
        return self.__download


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
