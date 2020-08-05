import random

from qtpy.QtCore import QAbstractTableModel, Qt
from qtpy.QtWidgets import QApplication, QMainWindow, QTableView, QVBoxLayout, QAbstractItemView, QWidget, QHeaderView

from modpack_builder.gui.delegates import CheckBoxItemDelegate


class ExampleTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.table = list()

        for row in range(10):
            self.table.append([f"Row {row}", bool(random.getrandbits(1))])

    def rowCount(self, _=None):
        return len(self.table)

    def columnCount(self, _=None):
        return 2

    def data(self, index, role=Qt.DisplayRole):
        if (
            role != Qt.DisplayRole or
            not index.isValid() or
            index.row() > self.rowCount() - 1 or
            index.column() > self.columnCount() - 1
        ):
            return None

        return self.table[index.row()][index.column()]

    def setData(self, index, value, role=Qt.DisplayRole):
        if (
            role != Qt.DisplayRole or
            not index.isValid() or
            index.row() > self.rowCount() - 1 or
            index.column() > self.columnCount() - 1
        ):
            return False

        self.table[index.row()][index.column()] = value

        self.dataChanged.emit(index, index, (Qt.DisplayRole,))

        return True

    def flags(self, index):
        base_flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemNeverHasChildren

        if index.column() == 1:
            return base_flags | Qt.ItemIsEditable

        return base_flags


class ExampleCheckBoxItemDelegateWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.resize(300, 300)

        self.example_table_view = QTableView(self)
        self.example_table_model = ExampleTableModel(self.example_table_view)
        self.checkbox_item_delegate = CheckBoxItemDelegate(self.example_table_view, self.example_table_model)

        self.example_table_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.example_table_view.setSelectionBehavior(QAbstractItemView.SelectRows)

        self.example_table_view.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.example_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        self.example_table_view.setItemDelegateForColumn(1, self.checkbox_item_delegate)
        self.example_table_view.setModel(self.example_table_model)

        self.setCentralWidget(QWidget(self))
        self.centralWidget().setLayout(QVBoxLayout(self))
        self.centralWidget().layout().addWidget(self.example_table_view)


if __name__ == "__main__":
    import sys

    app = QApplication(list())
    window = ExampleCheckBoxItemDelegateWindow()

    window.show()
    sys.exit(app.exec_())
