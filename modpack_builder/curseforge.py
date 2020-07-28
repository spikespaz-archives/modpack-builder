import itertools
import dataclasses

from enum import Enum

import arrow
import requests

from arrow import Arrow
from orderedset import OrderedSet


CURSEFORGE_API_BASE_URL = "https://api.cfwidget.com/minecraft/mc-mods/{}"
CURSEFORGE_DOWNLOAD_BASE_URL = "https://edge.forgecdn.net/files/{}/{}/{}"
CURSEFORGE_MOD_BASE_URL = "https://www.curseforge.com/minecraft/mc-mods/{}"


class ReleaseType(Enum):
    release = "release"
    beta = "beta"
    alpha = "alpha"


ReleaseType.values = tuple(member.value for member in ReleaseType)


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

        @property
        def download(self):
            return CURSEFORGE_DOWNLOAD_BASE_URL.format((id_ := str(self.id))[:4], id_[4:7], self.name)

        @property
        def dictionary(self):
            data = dataclasses.asdict(self)
            data["type"] = self.type.value

            return data

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

    def latest_files(self, game_versions):
        results = {member: None for member in ReleaseType}
        files = sorted(self.files, key=lambda file_: file_.uploaded_at, reverse=True)

        for file, version in itertools.product(files, game_versions):
            if version in file.versions and results[file.type] is None:
                results[file.type] = file

                if all(results.values()):
                    break

        return results

    def best_file(self, game_versions, release_type):
        files = list(filter(None, self.latest_files(game_versions).values()))

        if not files:
            return None

        files.sort(key=lambda file: ReleaseType.values.index(file.type.value))
        files.sort(key=lambda file: file.uploaded_at, reverse=True)
        files.sort(
            key=lambda file: ReleaseType.values.index(file.type.value) > ReleaseType.values.index(release_type.value)
        )

        return files[0]

    @staticmethod
    def get(identifier):
        response = requests.get(CURSEFORGE_API_BASE_URL.format(identifier))
        response.raise_for_status()

        return CurseForgeMod(identifier, **response.json())

    @property
    def identifier(self):
        return self.__identifier

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
