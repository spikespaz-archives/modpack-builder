from pathlib import Path

from qtpy.QtWidgets import QFileDialog
from qtpy.QtCore import Slot, Signal, QThread, QObject


class ThreadWorker(QObject):
    finished = Signal()

    def __init__(self, target, *args, **kwargs):
        super().__init__(None)

        self.__target = target
        self.__args = args
        self.__kwargs = kwargs

    @Slot()
    def run(self):
        self.__target(*self.__args, **self.__kwargs)
        self.finished.emit()


# https://wiki.qt.io/QThreads_general_usage
def create_thread(target, *args, dispose=False, parent=None, **kwargs):
    thread = QThread(parent)
    worker = ThreadWorker(target, *args, **kwargs)

    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)

    if dispose:
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

    # Make the worker an attribute of the thread to stop Python from garbage collecting it.
    # https://stackoverflow.com/a/63274024/2512078
    thread.worker = worker

    return thread


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


def connect_slot(signal):
    def wrapper(func):
        signal.connect(func)

        return func

    return wrapper
