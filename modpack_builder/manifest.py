import shlex
import dataclasses

from orderedset import OrderedSet

from . import curseforge

from .curseforge import ReleaseType


class ModpackManifest:
    @dataclasses.dataclass
    class JavaDownloads:
        windows: str = None
        darwin: str = None
        linux: str = None

    @dataclasses.dataclass(frozen=True)
    class ExternalFile:
        pattern: str = None
        immutable: bool = None
        server: bool = None

    @dataclasses.dataclass(frozen=True)
    class ExternalMod:
        identifier: str = None
        name: str = None
        version: str = None
        url: str = None
        server: bool = None

    @dataclasses.dataclass(frozen=True)
    class CurseForgeMod:
        identifier: str = None
        version: str = None
        url: str = None
        server: bool = None

    def __init__(self, data):
        self.profile_name = data.get("profile_name")
        self.profile_id = data.get("profile_id")
        self.profile_icon = data.get("profile_icon")
        self.game_versions = OrderedSet(data.get("game_versions", tuple()))

        java_downloads = data.get("java_downloads", dict())

        self.java_downloads = ModpackManifest.JavaDownloads(
            windows=java_downloads.get("windows"),
            darwin=java_downloads.get("darwin"),
            linux=java_downloads.get("linux")
        )

        self.forge_download = data.get("forge_download")
        self.version_label = data.get("version_label")
        self.release_preference = ReleaseType(data.get("release_preference", ReleaseType.release))
        self.load_priority = OrderedSet(data.get("load_priority", tuple()))

        client_data = data.get("client", dict())
        server_data = data.get("server", dict())

        # These don't need to be sets because for some strange reasons the arguments might
        # actually need to occur multiple times. For example, if an argument such as '--include <path>' is
        # split with 'shlex.split', the argument flag may be included multiple times for multiple paths.
        self.client_java_args = shlex.split(client_data.get("java_args", str()))
        self.server_java_args = shlex.split(server_data.get("java_args", str()))

        self.external_files = set()

        for pattern in client_data.get("external_files", dict()).get("overwrite", tuple()):
            self.external_files.add(ModpackManifest.ExternalFile(pattern=pattern, immutable=False, server=False))

        for pattern in client_data.get("external_files", dict()).get("immutable", tuple()):
            self.external_files.add(ModpackManifest.ExternalFile(pattern=pattern, immutable=True, server=False))

        for pattern in server_data.get("external_files", dict()).get("overwrite", tuple()):
            self.external_files.add(ModpackManifest.ExternalFile(pattern=pattern, immutable=False, server=True))

        for pattern in server_data.get("external_files", dict()).get("immutable", tuple()):
            self.external_files.add(ModpackManifest.ExternalFile(pattern=pattern, immutable=True, server=True))

        self.external_mods = set()

        for identifier, entry in client_data.get("external_mods", dict()).items():
            self.external_mods.add(ModpackManifest.ExternalMod(identifier=identifier, **entry, server=False))

        for identifier, entry in server_data.get("external_mods", dict()).items():
            self.external_mods.add(ModpackManifest.ExternalMod(identifier=identifier, **entry, server=True))

        self.curseforge_mods = set()

        for identifier in client_data.get("curseforge_mods", tuple()):
            identifier, _, version = identifier.lower().partition(":")

            if version in (member.value for member in ReleaseType):
                version = ReleaseType(version)

            self.curseforge_mods.add(ModpackManifest.CurseForgeMod(
                identifier=identifier,
                version=version if version else None,
                url=curseforge.CURSEFORGE_MOD_BASE_URL.format(identifier),
                server=False
            ))

        for identifier in server_data.get("curseforge_mods", tuple()):
            identifier, _, version = identifier.lower().partition(":")

            if version in (member.value for member in ReleaseType):
                version = ReleaseType(version)

            self.curseforge_mods.add(ModpackManifest.CurseForgeMod(
                identifier=identifier,
                version=version if version else None,
                url=curseforge.CURSEFORGE_MOD_BASE_URL.format(identifier),
                server=True
            ))

    @property
    def dictionary(self):
        dictionary = dict()

        dictionary["profile_name"] = self.profile_name
        dictionary["profile_id"] = self.profile_id
        dictionary["profile_icon"] = self.profile_icon
        dictionary["game_versions"] = list(self.game_versions)
        dictionary["java_downloads"] = self.java_downloads._asdict()
        dictionary["forge_download"] = self.forge_download
        dictionary["version_label"] = self.version_label
        dictionary["release_preference"] = self.release_preference.value
        dictionary["load_priority"] = list(self.load_priority)

        client_data = dict()
        server_data = dict()

        client_data["java_args"] = " ".join(self.client_java_args)
        server_data["java_args"] = " ".join(self.server_java_args)

        client_external_files = {
            "immutable": [],
            "overwrite": []
        }
        server_external_files = {
            "immutable": [],
            "overwrite": []
        }

        for entry in self.external_files:
            if entry.server and entry.immutable:
                server_external_files["immutable"].append(entry.pattern)
            elif entry.server:  # entry.server and not entry.immutable
                server_external_files["overwrite"].append(entry.pattern)
            elif entry.immutable:  # not entry.server and entry.immutable
                client_external_files["immutable"].append(entry.pattern)
            else:  # not entry.server and not entry.immutable
                client_external_files["overwrite"].append(entry.pattern)

        client_data["external_files"] = client_external_files
        server_data["external_files"] = server_external_files

        client_external_mods = dict()
        server_external_mods = dict()

        for entry in self.external_mods:
            entry_dict = entry._asdict()

            del entry_dict["identifier"]
            del entry_dict["server"]

            if entry.server:
                server_external_mods[entry.identifier] = entry_dict
            else:
                client_external_mods[entry.identifier] = entry_dict

        client_data["external_mods"] = client_external_mods
        server_data["external_mods"] = server_external_mods

        client_curseforge_mods = list()
        server_curseforge_mods = list()

        for entry in self.curseforge_mods:
            if entry.server:
                server_curseforge_mods.append(
                    f"{entry.identifier}:{entry.version}" if entry.version else entry.identifier
                )
            else:
                client_curseforge_mods.append(
                    f"{entry.identifier}:{entry.version}" if entry.version else entry.identifier
                )

        client_curseforge_mods.sort()
        server_curseforge_mods.sort()

        client_data["curseforge_mods"] = client_curseforge_mods
        server_data["curseforge_mods"] = server_curseforge_mods

        dictionary["client"] = client_data
        dictionary["server"] = server_data

        return dictionary