import secrets

import requests

from pathlib import Path


class DownloadException(Exception):
    pass


class ProgressTracker:
    def __init__(self, total=0):
        self.total = total
        self.value = 0

    def update(self, amount):
        self.value += amount

    def close(self):
        pass


def download_as_stream(file_url, file_path, tracker=ProgressTracker(), block_size=1024, **kwargs):
    response = requests.get(file_url, stream=True, allow_redirects=True, **kwargs)
    response.raise_for_status()

    tracker.total = int(response.headers.get("content-length", 0))

    with open(file_path, "wb") as file:
        for data in response.iter_content(block_size):
            tracker.update(len(data))
            file.write(data)

    tracker.close()

    if tracker.total != 0 and tracker.value != tracker.total:
        raise DownloadException("Downloaded bytes did not match 'content-length' header")


def get_profile_id(id_file):
    """
    Create a 32 character hexadecimal token, and write it to the file. Fetch if the file exists.
    """
    if not isinstance(id_file, Path):
        id_file = Path(id_file)

    if id_file.exists():
        with open(id_file, "r") as file:
            profile_id = file.read()
    else:
        profile_id = secrets.token_hex(16)

        with open(id_file, "w") as file:
            file.write(profile_id)

    return profile_id


def print_curseforge_mod_lock_info(project_slug, **kwargs):
    print((
        f"CurseForge mod information for: {project_slug}\n" +
        "  Project ID: {project_id}\n" +
        "  Project URL: {project_url}\n" + 
        "  Project Name: {project_name}\n" +
        "  File ID: {file_id}\n" +
        "  File URL: {file_url}\n" +
        "  File Name: {file_name}\n" +
        "  Release Type: {release_type}\n"
        "  Timestamp: {timestamp}"
    ).format(**kwargs))


def print_external_mod_lock_info(project_slug, **kwargs):
    print((
        f"External mod information for: {project_slug}\n" +
        "  File URL: {file_url}\n" +
        "  File Name: {file_name}\n" +
        "  Timestamp: {timestamp}\n" +
        "  External: {external}"
    ).format(**kwargs))
