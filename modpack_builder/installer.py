import os
import json

from pathlib import Path
from zipfile import ZipFile
from tempfile import TemporaryDirectory

from modpack_builder.tasks import ModpackBuilder


TASK_MAP = {
    # Major tasks
    "clean": lambda instance: ModpackBuilder.clean(instance),
    "install": lambda instance: ModpackBuilder.install(instance),
    "update": lambda instance: ModpackBuilder.update(instance),
    # Sub-tasks
    "create_modlist": lambda instance: ModpackBuilder.create_modlist(instance),
    "clean_mods": lambda instance: ModpackBuilder.clean_mods(instance),
    "clean_externals": lambda instance: ModpackBuilder.clean_externals(instance),
    "install_mods": lambda instance: ModpackBuilder.install_mods(instance),
    "install_externals": lambda instance: ModpackBuilder.install_externals(instance),
    "update_mods": lambda instance: ModpackBuilder.update_mods(instance),
    "update_externals": lambda instance: ModpackBuilder.update_externals(instance),
    "install_runtime": lambda instance: ModpackBuilder.install_runtime(instance),
    "install_forge": lambda instance: ModpackBuilder.install_forge(instance),
    "install_profile": lambda instance: ModpackBuilder.install_profile(instance),
    "update_profile": lambda instance: ModpackBuilder.update_profile(instance),
    "uninstall": lambda instance: ModpackBuilder.uninstalclean_externals
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


def main(argv):
    tasks = get_tasks(argv)
    modpack_path = get_modpack_path(argv)

    print("Performing tasks: " + ", ".join(tasks))
    print("Modpack location: " + str(modpack_path))

    mc_dir = Path(os.getenv("appdata")) / ".minecraft"

    print("Assuming minecraft location: " + str(mc_dir))
    print("Creating temporary directory...")

    with TemporaryDirectory() as temp_dir:
        orig_dir = os.getcwd()
        os.chdir(temp_dir)

        print("Extracting modpack...")

        with ZipFile(modpack_path, "r") as modpack_zip:
            modpack_zip.extractall()

        print("Loading modpack manifest...")

        with open("manifest.json", "r") as file:
            modpack_meta = json.load(file)

        modpack_builder = ModpackBuilder(modpack_meta, mc_dir)

        for task in tasks:
            TASK_MAP[task](modpack_builder)

        os.chdir(orig_dir)

    print("Completed all tasks successfully!")
