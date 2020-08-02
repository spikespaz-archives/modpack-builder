from orderedset import OrderedSet

from qtpy.QtCore import Qt, QAbstractTableModel, QModelIndex

import modpack_builder.utilities as utilities

from modpack_builder.curseforge import ReleaseType


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

            return None

        elif index.column() == 2:  # File
            if identifier in self.builder.curseforge_files:
                return self.builder.curseforge_files[identifier].name

            if identifier in self.builder.manifest.external_mods:
                return self.builder.manifest.external_mods[identifier].file

            return None

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

        self.column_names = ("Identifier", "Name", "Version", "Server", "File")
        self.identifiers = list()

        self.dataChanged.connect(self.parent().verticalHeader().reset)

    def refresh(self):
        self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount(), self.columnCount()))

    def rowCount(self, _=None):
        return len(self.identifiers)

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

        if self.identifiers[index.row()] is None:
            return None

        if index.column() == 0:  # Identifier
            return self.identifiers[index.row()]

        elif index.column() == 1:  # Name
            return self.builder.curseforge_mods[self.identifiers[index.row()]].title

        elif index.column() == 2:  # Version
            curseforge_mod = self.builder.manifest.curseforge_mods[self.identifiers[index.row()]]

            if curseforge_mod.version is None:
                return None
            elif isinstance(curseforge_mod.version, ReleaseType):
                return curseforge_mod.version.value.title()
            else:  # Must be an actual file ID from CurseForge
                return str(curseforge_mod.version)

        elif index.column() == 3:  # Server
            return str(self.builder.manifest.curseforge_mods[self.identifiers[index.row()]].server)

        elif index.column() == 4:  # File
            return self.builder.curseforge_files[self.identifiers[index.row()]].name

    def setData(self, index, value, role=Qt.DisplayRole):
        if (
            role != Qt.DisplayRole or
            not index.isValid() or
            index.row() > self.rowCount() or
            index.column() > self.columnCount()
        ):
            return False

        if self.identifiers[index.row()] is None and index.column() != 0:
            raise IndexError()

        if index.column() == 0:  # Identifier
            self.identifiers[index.row()] = value

        elif index.column() == 1:  # Name
            return False

        elif index.column() == 2:  # Version
            self.builder.manifest.curseforge_files[self.identifiers[index.row()]].version = value

        elif index.column() == 3:  # Server
            return False

        elif index.column() == 4:  # File
            return False

        self.dataChanged.emit(
            self.index(index.row(), 0),
            self.index(index.row(), self.columnCount()),
            (Qt.DisplayRole,)
        )

        return True

    def insertRows(self, row, count, _=None):
        self.beginInsertRows(QModelIndex(), row, row + count - 1)

        for index in range(row, row + count):
            self.identifiers.insert(index, None)

        self.endInsertRows()

        return True

    def removeRows(self, row, count, _=None):
        self.beginRemoveRows(QModelIndex(), row, row + count - 1)

        for _ in range(row, row + count):
            if (identifier := self.identifiers.pop(row)) is None:
                continue

            self.builder.curseforge_mods.pop(identifier)
            self.builder.curseforge_files.pop(identifier)

        self.endRemoveRows()
