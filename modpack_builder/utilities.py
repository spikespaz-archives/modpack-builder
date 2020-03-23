import secrets

import tqdm
import requests


class DownloadException(Exception):
    pass


class ProfileExistsException(Exception):
    pass


class ProgressTracker:
    def __init__(self, total=0):
        self.total = total
        self.value = 0

    def update(self, amount):
        self.value += amount

    def close(self):
        pass


class TqdmTracker(ProgressTracker):
    def __init__(self, **kwargs):
        self._tqdm = None
        self._kwargs = kwargs

        if "total" in kwargs:
            self.total(kwargs["total"])

    @property
    def total(self):
        return self._tqdm.total

    @total.setter
    def total(self, size):
        self._tqdm = tqdm.tqdm(total=size, **self._kwargs)

    @property
    def value(self):
        return self._tqdm.n

    def update(self, amount):
        self._tqdm.update(amount)

    def close(self):
        self._tqdm.close()


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
    if id_file.exists():
        with open(id_file, "r") as file:
            profile_id = file.read()
    else:
        profile_id = secrets.token_hex(16)

        with open(id_file, "w") as file:
            file.write(profile_id)

    return profile_id


def print_mod_lock_info(**kwargs):
    print((
        "  Project ID: {project_id}\n" +
        "  Project URL: {project_url}\n" + 
        "  Project Name: {project_name}\n" +
        "  File ID: {file_id}\n" +
        "  File URL: {file_url}\n" +
        "  File Name: {file_name}\n" +
        "  Release Type: {release_type}\n"
        "  Timestamp: {timestamp}"
    ).format(**kwargs))


def print_external_mod_lock_info(**kwargs):
    print((
        "  File URL: {file_url}\n" +
        "  File Name: {file_name}\n" +
        "  Timestamp: {timestamp}\n" +
        "  External: {external}"
    ).format(**kwargs))
