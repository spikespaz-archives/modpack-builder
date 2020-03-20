import json
import secrets

from pathlib import Path

import arrow

from . import utility

from .utility import ProgressTracker


class ProfileExistsException(Exception):
    pass


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
