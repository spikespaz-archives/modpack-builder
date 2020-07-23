import re
import string
import random

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


def make_slug(title, prefix=None, size=20, allowed_chars=string.ascii_lowercase + string.digits):
    slug = re.sub(r"[^" + allowed_chars + "]", "-", title.lower())
    slug = re.sub(r"-{2,}", "-", slug)
    slug = slug.strip()

    return prefix or "" + (slug[:size] if size and len(slug) > size else slug)
