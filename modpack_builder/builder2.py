import os
import math
import psutil
import platform

from enum import Enum
from pathlib import Path


PLATFORM = platform.system()


class ReleaseType(Enum):
    release = "release"
    beta = "beta"
    alpha = "alpha"


class ModpackBuilder:
    _max_concurrent_requests = 16
    _max_concurrent_downloads = 16
    _max_recommended_java_runtime_memory = 8

    def __init__(self):
        self.modpack_package = None

        self.profile_name = ""
        self.profile_directory = None
        self.profile_id = ""
        self.profile_icon_base64 = ""

        self.compatible_minecraft_versions = []
        self.preferred_mod_release_type = ReleaseType.release

        self.curseforge_mods = {}
        self.external_mods = {}

        self.mod_loading_priority = []

        self.forge_minecraft_version = ""
        self.forge_version = ""

        self.java_runtime_memory = self._get_recommended_memory()
        self.java_runtime_arguments = []

        self.java_download_urls = {}

        self.external_resource_globs = []

        self.minecraft_directory = None
        self.minecraft_launcher_path = None

        self.concurrent_requests = 8
        self.concurrent_downloads = 8

    def install_modpack(self):
        pass

    def update_modpack(self):
        pass

    def update_profile(self):
        pass

    def launch_minecraft(self):
        pass

    def export_package(self):
        pass

    def install_server(self):
        pass

    def install_forge_client(self):
        pass

    def install_forge_server(self):
        pass

    def download_java_runtime(self):
        pass

    def install_external_resources(self):
        pass

    @staticmethod
    def _get_system_memory():
        return math.ceil(psutil.virtual_memory().total / 1024 / 1024 / 1024)

    @staticmethod
    def _get_max_recommended_memory():
        return ModpackBuilder._get_system_memory() - 1

    @staticmethod
    def _get_recommended_memory():
        system_memory = ModpackBuilder._get_system_memory()

        if system_memory == 4:
            return 3
        elif system_memory < 8:
            return system_memory - 2
        else:
            return min(system_memory / 2, ModpackBuilder._max_recommended_java_runtime_memory)
