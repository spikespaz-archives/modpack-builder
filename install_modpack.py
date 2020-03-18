import json
import os
import glob
import secrets
import subprocess
from tempfile import TemporaryDirectory
from datetime import datetime
from zipfile import ZipFile
from pathlib import Path

PROFILE_NAME = "The Alex Pack"
JAVA_ARGS = "-Xmx8G -Xms8G -Xaggressive -Xdisableexplicitgc -Xgc:concurrentScavenge -Xgcthreads6"
JAVA_RUNTIME = "jdk8u242-b08-jre"
FORGE_VERSION_ID = "1.12.2-forge1.12.2-14.23.5.2847"
FORGE_INSTALLER_NAME = "forge-1.12.2-14.23.5.2847-installer.jar"

MINECRAFT_DIR = Path(os.getenv("appdata")) / ".minecraft"
LAUNCHER_PROFILES_FILE = MINECRAFT_DIR / "launcher_profiles.json"
PROFILE_DIR = MINECRAFT_DIR / "profiles/the-alex-pack"
PROFILE_ID_FILE = MINECRAFT_DIR / "profile_id"
PROFILE_ID = None


print("Creating profile directory...")

PROFILE_DIR.mkdir(parents=True, exist_ok=True)

if PROFILE_ID_FILE.exists():
    print("Reading profile ID...")

    with open(PROFILE_ID_FILE, "r") as file:
        PROFILE_ID = file.read(32)
else:
    print("Creating profile ID...")
    
    PROFILE_ID = secrets.token_hex(16)

    with open(PROFILE_ID_FILE, "w") as file:
        file.write(PROFILE_ID)

print("Removing existing mods from profile...")

for file in (PROFILE_DIR / "mods").glob("*.jar"):
    print("Removing '{}'".format(file))

    os.remove(file)

print("Extracting zip file members...")

with ZipFile("modpack.zip", "r") as zip_file:
    mod_files = []
    config_files = []
    resource_files = []
    runtime_files = []

    print("Creating file lists...")
    for file in zip_file.namelist():
        if zip_file.getinfo(file).is_dir():
            continue

        if file.startswith("mods/"):
            mod_files.append(file)

        if file.startswith("config/"):
            config_files.append(file)

        if file.startswith("resources/"):
            resource_files.append(file)

        if file.startswith("runtime/"):
            runtime_files.append(file)

    print("Copying mod files...")
    for file in mod_files:
        file_dest = PROFILE_DIR / file

        print("Copying mod: '{}'".format(file_dest))

        zip_file.extract(file, PROFILE_DIR)

    print("Copying config files...")
    for file in config_files:
        file_dest = PROFILE_DIR / file

        if file_dest.exists():
            print("Replacing config: '{}'".format(file_dest))

            file_dest.unlink()
        else:
            print("Copying config: '{}'".format(file_dest))

            zip_file.extract(file, PROFILE_DIR)

    print("Copying resource files...")
    for file in resource_files:
        file_dest = PROFILE_DIR / file

        if file_dest.exists():
            print("Replacing resource: '{}'".format(file_dest))

            file_dest.unlink()
        else:
            print("Copying resource: '{}'".format(file_dest))

        zip_file.extract(file, PROFILE_DIR)

    print("Copying runtime files...")
    for file in runtime_files:
        file_dest = PROFILE_DIR / file

        if file_dest.exists():
            continue

        print("Copying runtime file: '{}'".format(file_dest))

        zip_file.extract(file, PROFILE_DIR)

    if not Path(MINECRAFT_DIR / "versions" / FORGE_VERSION_ID).exists():
        print("Copying forge installer...")

        with TemporaryDirectory() as temp_dir:
            zip_file.extract(FORGE_INSTALLER_NAME, temp_dir)

            print("Waiting for user to install Forge...")

            subprocess.run([
                str(PROFILE_DIR / "runtime" / JAVA_RUNTIME / "bin/java.exe"),
                "-jar", str(Path(temp_dir) / FORGE_INSTALLER_NAME)
            ])

print("Adding new entry to launcher profiles...")

launcher_profiles = None

with open(LAUNCHER_PROFILES_FILE, "r") as file:
    launcher_profiles = json.load(file)

if PROFILE_ID in launcher_profiles["profiles"]:
    print("Profile already present: '{}'".format(PROFILE_ID))
else:
    print("Creating new launcher profile: '{}'\nProfile ID: '{}'".format(PROFILE_NAME, PROFILE_ID))

    utc_now = datetime.utcnow().isoformat() + "Z"

    launcher_profiles["profiles"][PROFILE_ID] = {
        "created": utc_now,
        "gameDir": str(PROFILE_DIR.resolve()),
        "icon": "Bookshelf",
        "javaArgs": JAVA_ARGS,
        "javaDir": str((PROFILE_DIR / "runtime" / JAVA_RUNTIME / "bin/javaw.exe").resolve()),
        "lastUsed": utc_now,
        "lastVersionId": FORGE_VERSION_ID,
        "name": PROFILE_NAME,
        "type": "custom"
    }

    launcher_profiles["selectedUser"]["profile"] = PROFILE_ID

    with open(LAUNCHER_PROFILES_FILE, "w") as file:
        json.dump(launcher_profiles, file, indent=2)

print("Done! You can close this now.")
input()
