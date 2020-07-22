from pathlib import Path

from qtpy import QtCore
from qtpy.QtWidgets import QFileDialog


class ProgressReporter:
    def __init__(self, callback):
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