import secrets

import tqdm
import arrow
import requests
import email.utils

from pathlib import Path


RELEASE_TYPES = ("release", "beta", "alpha")


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


def get_external_mod_lock_info(external_url):
    response = requests.head(external_url)
    response.raise_for_status()

    return {
        "file_url": external_url,
        "file_name": external_url.rsplit("/", 1)[1],
        "timestamp": int(email.utils.parsedate_to_datetime(response.headers.get("last-modified", None)).timestamp()),
        "external": True
    }


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


def get_suitable_release(releases, preference):
    """
    Returns the best possible release according to upload date and release type.
    If the preference is "beta" and there is a newer "release", the newer will be returned.

    preference: The preferred release type, either "release", "beta", or "alpha".
    """
    if not isinstance(releases, list):
        releases = list(releases)

    releases.sort(key=lambda release: RELEASE_TYPES.index(release["type"]))
    releases.sort(key=lambda release: arrow.get(release["uploaded_at"]), reverse=True)
    releases.sort(key=lambda release: RELEASE_TYPES.index(release["type"]) > RELEASE_TYPES.index(preference))

    return releases[0]


# Gratefully borrowed from https://stackoverflow.com/a/13940780
def set_cmd_font(face_name, font_size, font_weight=400):
    import ctypes

    LF_FACESIZE = 32
    STD_OUTPUT_HANDLE = -11
    TMPF_TRUETYPE = 4

    class COORD(ctypes.Structure):
        _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]

    class CONSOLE_FONT_INFOEX(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_ulong),
                    ("nFont", ctypes.c_ulong),
                    ("dwFontSize", COORD),
                    ("FontFamily", ctypes.c_uint),
                    ("FontWeight", ctypes.c_uint),
                    ("FaceName", ctypes.c_wchar * LF_FACESIZE)]

    font = CONSOLE_FONT_INFOEX()
    font.cbSize = ctypes.sizeof(CONSOLE_FONT_INFOEX)
    font.nFont = 0
    font.dwFontSize.X = 0
    font.dwFontSize.Y = font_size
    font.FontFamily = TMPF_TRUETYPE
    font.FontWeight = font_weight
    font.FaceName = face_name

    handle = ctypes.windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
    ctypes.windll.kernel32.SetCurrentConsoleFontEx(handle, ctypes.c_long(False), ctypes.pointer(font))
