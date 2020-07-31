from pathlib import Path

from qtpy.QtGui import QValidator

from .. import utilities


class SlugValidator(QValidator):
    def __init__(self, parent=None, **kwargs):
        super().__init__(parent)

        self.__kwargs = kwargs

        # Allow the user to input whitespace at the end by default
        if "rstrip" not in self.__kwargs:
            self.__kwargs["rstrip"] = False

    def validate(self, text, cursor_pos):
        return (
            QValidator.Acceptable,
            utilities.slugify(text, **self.__kwargs),
            min(cursor_pos, len(text))
        )


class PathValidator(QValidator):
    def __init__(self, parent=None, file=False, extensions=None):
        super().__init__(parent)

        self.__file = file
        self.__extensions = extensions

    def validate(self, text, cursor_pos):
        path = Path(text)
        validity = None

        if not path.exists():
            if path.parent.exists() and path.parent.is_dir():
                # If the parent directory exists the path has been valid until the last part was added.
                # The state should be intermediate because it could be a typo or in-between changes.
                validity = QValidator.Intermediate
            else:
                # The parent either doesn't exist or is a file.
                # Return an invalid state to prevent the user from typing and not realizing the mistake.
                validity = QValidator.Invalid
        elif self.__file and path.is_file():
            if self.__extensions and (path.suffix in self.__extensions or "".join(path.suffixes) in self.__extensions):
                validity = QValidator.Acceptable
            elif self.__extensions:
                # The user probably hasn't typed the extension yet, so an intermediate state is returned.
                # This branch won't be run if `self.__extensions` contains an empty string,
                # so that the user can match any filename without an extension.
                validity = QValidator.Intermediate
            else:
                # No extensions provided to match, any file is acceptable.
                validity = QValidator.Acceptable
        elif self.__file and path.is_dir():
            # The current text is probably a parent of the final file path.
            validity = QValidator.Intermediate
        elif path.is_dir():
            # The validator is not expected to match a file and a directory is acceptable.
            validity = QValidator.Acceptable

        # If the below assertion fails I have made a mistake and did not predict some form of input.
        assert validity is not None

        return validity, text, cursor_pos
