from orderedset import OrderedSet

from qtpy.QtCore import Qt, QAbstractTableModel, QModelIndex

from .. import utilities

from ..curseforge import ReleaseType, CurseForgeMod


class LoadingPriorityTableModel(QAbstractTableModel):
    def __init__(self, builder, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.builder = builder

        self.column_names = ("Identifier", "Name", "File")

        self.dataChanged.connect(self.parent().verticalHeader().reset)

    def refresh(self):
        self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount(), self.columnCount()))

    def rowCount(self, _=None):
        return len(self.builder.manifest.load_priority)

    def columnCount(self, _=None):
        return len(self.column_names)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None

        if orientation == Qt.Horizontal:
            return self.column_names[section]

        return section

    def data(self, index, role=Qt.DisplayRole):
        if (
            role != Qt.DisplayRole or
            not index.isValid() or
            index.row() > self.rowCount() or
            index.column() > self.columnCount()
        ):
            return None

        identifier = self.builder.manifest.load_priority[index.row()]

        if index.column() == 0:  # Identifier
            return identifier

        elif index.column() == 1:  # Name
            if identifier in self.builder.curseforge_mods:
                return self.builder.curseforge_mods[identifier].title

            if identifier in self.builder.manifest.external_mods:
                return self.builder.manifest.external_mods[identifier].name

            assert None

        elif index.column() == 2:  # File
            if identifier in self.builder.curseforge_files:
                return self.builder.curseforge_files[identifier].name

            if identifier in self.builder.manifest.external_mods:
                return self.builder.manifest.external_mods[identifier].file

            assert None

    def setData(self, index, value, role=Qt.DisplayRole):
        if (
            role != Qt.DisplayRole or
            value in self.builder.manifest.load_priority or
            not index.isValid() or
            index.row() > self.rowCount() or
            index.column() > 0  # Only row is important, the other columns besides identifier are not assignable
        ):
            return False

        load_priority = list(self.builder.manifest.load_priority)

        load_priority[index.row()] = value

        self.builder.manifest.load_priority = OrderedSet(load_priority)

        self.dataChanged.emit(
            self.index(index.row(), 0),
            self.index(index.row(), self.columnCount()),
            (Qt.DisplayRole,)
        )

        return True

    def insertRows(self, row, count, _=None):
        self.beginInsertRows(QModelIndex(), row, row + count - 1)

        load_priority_list = list(self.builder.manifest.load_priority)

        for offset in range(count):
            load_priority_list.insert(row + offset, utilities.generate_id(8))

        self.builder.manifest.load_priority = OrderedSet(load_priority_list)

        self.endInsertRows()

        return True

    def removeRows(self, row, count, _=None):
        self.beginRemoveRows(QModelIndex(), row, row + count - 1)

        load_priority_list = list(self.builder.manifest.load_priority)

        for _ in range(count):
            load_priority_list.pop(row)

        self.builder.manifest.load_priority = OrderedSet(load_priority_list)

        self.endRemoveRows()

    def moveRows(self, source_parent, source_row, count, destination_parent, destination_row):
        if source_parent != destination_parent or source_row == destination_row:
            return False

        if (
            destination_row < 0 or
            destination_row > self.rowCount() or
            source_row <= destination_row <= source_row + count
        ):
            return False

        self.beginMoveRows(source_parent, source_row, source_row + count - 1, destination_parent, destination_row)

        load_priority_list = list(self.builder.manifest.load_priority)

        if source_row > destination_row:
            for offset in range(count):
                load_priority_list.insert(destination_row + offset, load_priority_list.pop(source_row + offset))
        else:
            for _ in range(count):
                load_priority_list.insert(destination_row - 1, load_priority_list.pop(source_row))

        self.builder.manifest.load_priority = OrderedSet(load_priority_list)

        self.endMoveRows()

        return True


class CurseForgeModsTableModel(QAbstractTableModel):
    def __init__(self, builder, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.builder = builder

        self.column_names = ("Identifier", "Name", "Version", "File")
        self.inserted_rows = 0

        self.dataChanged.connect(self.parent().verticalHeader().reset)

    def refresh(self):
        self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount(), self.columnCount()))

    def rowCount(self, _=None):
        return len(self.builder.curseforge_files) + self.inserted_rows

    def columnCount(self, _=None):
        return len(self.column_names)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None

        if orientation == Qt.Horizontal:
            return self.column_names[section]

        return section

    def data(self, index, role=Qt.DisplayRole):
        if (
            role != Qt.DisplayRole or
            not index.isValid() or
            index.row() > self.rowCount() or
            index.column() > self.columnCount()
        ):
            return None

        if index.row() > len(self.builder.curseforge_files):
            return None

        identifier = tuple(self.builder.curseforge_files.keys())[index.row()]

        if index.column() == 0:  # Identifier
            return identifier

        elif index.column() == 1:  # Name
            return self.builder.curseforge_mods[identifier].title

        elif index.column() == 2:  # Version
            curseforge_mod = self.builder.manifest.curseforge_mods[identifier]

            if not curseforge_mod.version:
                return None
            elif isinstance(curseforge_mod.version, ReleaseType):
                return curseforge_mod.version.value.title()
            else:  # Must be an actual file ID from CurseForge
                return str(curseforge_mod.version)

        elif index.column() == 3:  # File
            return self.builder.curseforge_files[identifier].name

    def setData(self, index, value, role=Qt.DisplayRole):
        if (
            role != Qt.DisplayRole or
            not index.isValid() or
            index.row() > self.rowCount() or
            index.column() > self.columnCount()
        ):
            return False

        if index.row() > len(self.builder.curseforge_files):
            if index.column() != 0:
                raise IndexError()
            else:
                identifier = value
                self.inserted_rows -= 1
        else:
            identifier = tuple(self.builder.curseforge_files.keys())[index.row()]

        if index.column() == 0:  # Identifier
            if identifier in self.identifiers:
                return False

            curseforge_mod = CurseForgeMod.get(identifier)

            self.builder.curseforge_mods[identifier] = curseforge_mod
            self.builder.curseforge_files[identifier] = curseforge_mod.best_file(
                self.builder.manifest.game_versions,
                self.builder.manifest.release_preference
            )

            self.identifiers[index] = identifier

        elif index.column() == 1:  # Name
            return False

        elif index.column() == 2:  # Version
            self.builder.manifest.curseforge_files[identifier].version = value

        elif index.column() == 3:  # File
            return False

        self.dataChanged.emit(
            self.index(index.row(), 0),
            self.index(index.row(), self.columnCount()),
            (Qt.DisplayRole,)
        )

        return True

    def insertRows(self, row, count, _=None):
        self.beginInsertRows(QModelIndex(), row, row + count - 1)

        self.inserted_rows += count

        self.endInsertRows()

        return True

    def removeRows(self, row, count, _=None):
        self.beginRemoveRows(QModelIndex(), row, row + count - 1)

        for _ in range(count):
            identifier = tuple(self.builder.curseforge_files.keys())[row]

            self.builder.curseforge_mods.pop(identifier)
            self.builder.curseforge_files.pop(identifier)

        self.endRemoveRows()
