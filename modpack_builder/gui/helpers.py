from pathlib import Path

from qtpy.QtCore import Slot
from qtpy.QtWidgets import QFileDialog


def pick_directory(parent, title="Select Directory", path=Path("~")):
    path = QFileDialog.getExistingDirectory(parent, title, str(path.resolve()), QFileDialog.ShowDirsOnly)

    if path:
        return Path(path).resolve()

    return None


def pick_file(parent, title="Select File", path=Path("~"), types=("Text Document (*.txt)",)):
    path = QFileDialog.getOpenFileName(parent, title, str(path.resolve()), filter="\n".join(types))[0]

    if path:
        return Path(path).resolve()

    return None


def make_slot(*args, **kwargs):
    def wrapper(func):
        # Convert "snake_case" to "camelCase" for the name of the Qt slot.
        kwargs.setdefault("name", func.__name__.replace("_", " ").title().replace(" ", ""))
        return Slot(*args, **kwargs)(func)

    return wrapper


def connect_slot(signal):
    def wrapper(func):
        signal.connect(func)

        return func

    return wrapper
