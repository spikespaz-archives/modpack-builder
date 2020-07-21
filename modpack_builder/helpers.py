from pathlib import Path

from qtpy import QtCore
from qtpy.QtWidgets import QFileDialog


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