import re
import string
import random
import secrets
import unicodedata

import requests

from pathlib import Path
from threading import Thread


class DownloadException(Exception):
    pass


class ProgressReporter:
    def __init__(self, callback=None):
        self._maximum = 100
        self._value = 0
        self._done = False
        self.__callback = callback

    @property
    def maximum(self):
        return self._maximum

    @maximum.setter
    def maximum(self, value):
        self._maximum = value

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self._value = value

    def done(self):
        self._done = True

        if self.__callback:
            self.__callback(self)

    def is_done(self):
        return self._done


def download_as_stream(url, path, reporter=ProgressReporter(), block_size=1024, **kwargs):
    response = requests.get(url, stream=True, allow_redirects=True, **kwargs)
    response.raise_for_status()

    reporter.maximum = int(response.headers.get("content-length", 0))
    reporter.value = 0

    with open(path, "wb") as file:
        for data in response.iter_content(block_size):
            reporter.value += len(data)
            file.write(data)

    reporter.done()

    if reporter.maximum != 0 and reporter.value != reporter.maximum:
        raise DownloadException("Downloaded bytes did not match 'content-length' header")

    return path


def make_thread(*args, **kwargs):
    def wrapper(func):
        return Thread(target=func, *args, **kwargs)

    return wrapper


def sequence_groups(iterable):
    iterable = tuple(iterable)
    sequences = [[iterable[0]]]

    for index in range(1, len(iterable)):
        if iterable[index] == iterable[index - 1] + 1:
            sequences[-1].append(iterable[index])
        else:
            sequences.append([iterable[index]])

    return sequences


def generate_id(size=6, chars=string.ascii_lowercase + string.digits):
    return "".join(random.choice(chars) for _ in range(size))


def slugify(text, size=None, prefix=None, allow_unicode=False, allow_underscores=False, lstrip=True, rstrip=True):
    """
    Adapted from the Django Project to provide some extra options.
    https://docs.djangoproject.com/en/3.0/_modules/django/utils/text/#slugify

    :param text:
    :param size:
    :param prefix:
    :param allow_unicode:
    :param allow_underscores:
    :param lstrip:
    :param rstrip:
    :return:
    """

    # Slightly un-pythonic, but accept any string-representable object
    text = str(text)

    # Slugify the prefix independently so that we can get the length of it later
    if prefix:
        prefix = slugify(str(prefix), allow_unicode=allow_unicode, allow_underscores=allow_underscores)

    # Simplify accented characters and such to their basic forms
    text = unicodedata.normalize("NFKD", text)

    # Encode and decode the string as ASCII ignoring errors to remove problematic characters
    if not allow_unicode:
        text = text.encode("ascii", "ignore").decode("ascii")

    # Strip whitespace from ends and lowercase the string, whitespace may be dangling after characters removed above
    if lstrip:
        text = text.lstrip()

    if rstrip:
        text = text.rstrip()

    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)

    # Replace any consecutive hyphens and whitespace with a single hyphen, underscores too if disallowed
    if allow_underscores:
        text = re.sub(r"[-\s]+", "-", text)
    else:
        text = re.sub(r"[-_\s]+", "-", text)

    # Truncate to the size
    if size:
        text = text[:size]

    if prefix:
        text = prefix + text

    return text


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
