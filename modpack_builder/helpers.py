import re
import string
import random
import unicodedata

from pathlib import Path
from threading import Thread

from qtpy import QtCore
from qtpy.QtWidgets import QFileDialog


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


def pick_directory(parent, title="Select Directory", path=Path("~")):
    path = QFileDialog.getExistingDirectory(
        parent, title, str(path.resolve()), QFileDialog.ShowDirsOnly
    )

    if path:
        return Path(path)

    return path


def pick_file(parent, title="Select File", path=Path("~"), types=("Text Document (*.txt)",)):
    if path.is_file():
        start = path.parent.resolve()
    else:
        start = path.resolve()

    file = QFileDialog.getOpenFileName(parent, title, str(start), filter="\n".join(types))[0]

    if file:
        return Path(file)

    return path


def make_slot(*args, **kwargs):
    def wrapper(func):
        # Convert "snake_case" to "camelCase" for the name of the Qt slot.
        kwargs.setdefault("name", func.__name__.replace("_", " ").title().replace(" ", ""))

        return QtCore.Slot(*args, **kwargs)(func)

    return wrapper


def connect_slot(signal, *args, **kwargs):
    del args, kwargs

    def wrapper(func):
        signal.connect(func)

        return func

    return wrapper


def make_thread(*args, **kwargs):
    def wrapper(func):
        return Thread(target=func, *args, **kwargs)

    return wrapper


def generate_id(size=6, chars=string.ascii_lowercase + string.digits):
    return "".join(random.choice(chars) for _ in range(size))


def slugify(text, size=None, prefix=None, allow_unicode=False, allow_underscores=False):
    """
    Adapted from the Django Project to provide some extra options.
    https://docs.djangoproject.com/en/3.0/_modules/django/utils/text/#slugify

    :param text:
    :param size:
    :param prefix:
    :param allow_unicode:
    :param allow_underscores:
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
    text = text.strip().lower()
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
