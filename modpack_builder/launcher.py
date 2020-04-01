import os
import sys
import json

from pathlib import Path
from zipfile import ZipFile
from argparse import ArgumentParser
from tempfile import TemporaryDirectory

from modpack_builder.builder import ModpackBuilder

MODE_MAP = {
    "update": lambda instance: ModpackBuilder.update(instance),
    "install": lambda instance: ModpackBuilder.install(instance),
    "uninstall": lambda instance: ModpackBuilder.uninstall(instance)
}
TASK_MAP = {
    # Sub-tasks
    "create_modlist": lambda instance: ModpackBuilder.create_modlist(instance),
    "clean_mods": lambda instance: ModpackBuilder.clean_mods(instance),
    "install_mods": lambda instance: ModpackBuilder.install_mods(instance),
    "install_externals": lambda instance: ModpackBuilder.install_externals(instance),
    "update_mods": lambda instance: ModpackBuilder.update_mods(instance),
    "update_externals": lambda instance: ModpackBuilder.update_externals(instance),
    "install_runtime": lambda instance: ModpackBuilder.install_runtime(instance),
    "install_forge": lambda instance: ModpackBuilder.install_forge(instance),
    "install_profile": lambda instance: ModpackBuilder.install_profile(instance),
    "update_profile": lambda instance: ModpackBuilder.update_profile(instance),
    "remove_profile": lambda instance: ModpackBuilder.remove_profile(instance)
}

PARSER = ArgumentParser(description="Minecraft Modpack Builder and Installer by Jacob Birkett")
ARGUMENTS = {
    "mode": {
        "flags": ("-m", "--mode"),
        "action": "store",
        "choices": tuple(MODE_MAP.keys()),
        "default": "install"
    },
    "tasks": {
        "flags": ("-t", "--tasks"),
        "action": "append",
        "choices": tuple(TASK_MAP.keys()),
        "default": []
    },
    "server": {
        "flags": ("-s", "--server"),
        "action": "store_true"
    },
    "destination": {
        "flags": ("-d", "--dest", "--destination"),
        "action": "store",
        "type": Path
    },
    "zipfile": {
        "flags": ("-z", "--zip", "--zipfile"),
        "action": "store",
        "type": Path
    },
    "concurrent_requests": {
        "flags": "--concurrent-requests",
        "action": "store",
        "type": int,
        "default": 8
    },
    "concurrent_downloads": {
        "flags": "--concurrent-downloads",
        "action": "store",
        "type": int,
        "default": 8
    }
}


class ArgumentError(Exception):
    pass


def assemble_args(parser, arguments):
    for dest, kwargs in arguments.items():
        flags = kwargs.pop("flags")

        if isinstance(flags, str):
            parser.add_argument(flags, **kwargs)
        else:
            parser.add_argument(*flags, dest=dest, **kwargs)


def main(argv):
    assemble_args(PARSER, ARGUMENTS)
    args = PARSER.parse_args(argv[1:])

    if not args.destination:
        if args.server:
            raise ArgumentError("If server mode is specified the destination must also be specified")
        else:
            args.destination = Path(os.getenv("appdata")) / ".minecraft"

    args.destination = args.destination.resolve()
    args.zipfile = args.zipfile.resolve()

    args.tasks = sorted(args.tasks, key=lambda task: tuple(TASK_MAP.keys()).index(task))

    print(f"Performing tasks: {' '.join(args.tasks) if args.tasks else args.mode}")
    print(f"Minecraft location: {args.destination}")
    print(f"Server only: {args.server}")

    print("Creating temporary directory...")

    with TemporaryDirectory() as temp_dir:
        orig_dir = os.getcwd()
        os.chdir(temp_dir)

        print("Extracting modpack...")

        if args.zipfile.is_dir():
            import shutil

            for path in args.zipfile.glob("**/*"):
                dest = temp_dir / path.relative_to(args.zipfile)

                if path.is_dir():
                    dest.mkdir(parents=True, exist_ok=True)
                    continue

                shutil.copyfile(path, dest)
        else:
            with ZipFile(args.zipfile, "r") as modpack_zip:
                modpack_zip.extractall()

        print("Loading modpack manifest...")

        with open("manifest.json", "r") as file:
            modpack_meta = json.load(file)

        modpack_builder = ModpackBuilder(
            meta=modpack_meta,
            mc_dir=args.destination,
            client=not args.server,
            concurrent_requests=args.concurrent_requests,
            concurrent_downloads=args.concurrent_downloads
        )

        try:
            if args.tasks:
                for task in args.tasks:
                    TASK_MAP[task](modpack_builder)
            else:
                MODE_MAP[args.mode](modpack_builder)
        except KeyboardInterrupt:
            os.chdir(orig_dir)
            
            print("Recieved keyboard interrupt, exiting...", file=sys.stderr)
            return

    os.chdir(orig_dir)

    print("Completed all tasks successfully!")
