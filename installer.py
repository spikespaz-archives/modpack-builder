import os
import sys
import json

from pathlib import Path
from zipfile import ZipFile
from tempfile import TemporaryDirectory

from mpbldr.tasks import ModpackBuilder


TASK_MAP = {
    # Major tasks
    "clean": lambda instance: ModpackBuilder.clean(instance),
    "install": lambda instance: ModpackBuilder.install(instance),
    "update": lambda instance: ModpackBuilder.update(instance),
    # Sub-tasks
    "load_modlist": lambda instance: ModpackBuilder.load_modlist(instance),
    "create_modlist": lambda instance: ModpackBuilder.create_modlist(instance),
    "clean_mods": lambda instance: ModpackBuilder.clean_mods(instance),
    "clean_configs": lambda instance: ModpackBuilder.clean_configs(instance),
    "install_mods": lambda instance: ModpackBuilder.install_mods(instance),
    "install_configs": lambda instance: ModpackBuilder.install_configs(instance),
    "update_mods": lambda instance: ModpackBuilder.update_mods(instance),
    "update_configs": lambda instance: ModpackBuilder.update_configs(instance),
    "install_runtime": lambda instance: ModpackBuilder.install_runtime(instance),
    "install_forge": lambda instance: ModpackBuilder.install_forge(instance),
    "install_profile": lambda instance: ModpackBuilder.install_profile(instance),
    "update_profile": lambda instance: ModpackBuilder.update_profile(instance),
    "uninstall": lambda instance: ModpackBuilder.uninstall(instance),
}


class ArgumentError(Exception):
    pass


def get_tasks(arguments):
    """
    Get a validated and sorted task list from program arguments.
    """
    if len(arguments) > 2:
        tasks = arguments[1:len(arguments) - 1]

        for task in tasks:
            if task not in TASK_MAP:
                raise ArgumentError("Unrecognized task: " + task)

        return sorted(tasks, key=lambda task: tuple(TASK_MAP.keys()).index(task))
    else:
        return ("install",)


def get_modpack_path(arguments):
    """
    Get a validated path to a modpack zip file from program arguments.
    """
    if not len(arguments) > 1:
        raise ArgumentError("Too few arguments, must include at least modpack path")

    modpack_path = Path(arguments[-1]).resolve()

    if not (modpack_path.exists() and modpack_path.is_file()):
        raise FileNotFoundError("Modpack path does not exist or is not a file")

    return modpack_path


if __name__ == "__main__":
    tasks = get_tasks(sys.argv)
    modpack_path = get_modpack_path(sys.argv)

    print("Performing tasks: " + ", ".join(tasks))
    print("Modpack location: " + str(modpack_path))

    mc_dir = Path(os.getenv("appdata")) / ".minecraft"
    print("Assuming minecraft location: " + str(mc_dir))

    print("Creating temporary directory...")
    with TemporaryDirectory() as temp_dir:
        os.chdir(temp_dir)

        print("Extracting modpack...")
        with ZipFile(modpack_path, "r") as modpack_zip:
            modpack_zip.extractall("modpack")

        print("Loading modpack manifest...")
        modpack_meta = json.load("modpack/manifest.json")
        modpack_builder = ModpackBuilder(modpack_meta, mc_dir)

        for task in tasks:
            TASK_MAP[task](modpack_builder)

    print("Completed all tasks successfully.")
    input()
