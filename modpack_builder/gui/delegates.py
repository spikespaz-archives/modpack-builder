from qtpy.QtCore import QPoint, QRect
from qtpy.QtWidgets import QStyledItemDelegate, QCheckBox, QApplication, QStyle, QStyleOptionButton


class CheckBoxItemDelegate(QStyledItemDelegate):
    def __init__(self, parent=None, model=None):
        super().__init__(parent)

        self.model = model

    def createEditor(self, parent, option, index):
        checkbox = QCheckBox(parent)

        checkbox.stateChanged.connect(lambda state: self.model.setData(index, bool(state)))

        return checkbox

    def setEditorData(self, editor, index):
        editor.setChecked(self.model.data(index))

    @staticmethod
    def __get_checkbox_rect(option):
        checkbox_style = QStyleOptionButton()
        checkbox_rect = QApplication.style().subElementRect(QStyle.SE_CheckBoxIndicator, checkbox_style)
        checkbox_point = QPoint(
            option.rect.x() + (option.rect.width() - checkbox_rect.width()) / 2,
            option.rect.y() + (option.rect.height() - checkbox_rect.height()) / 2
        )

        return QRect(checkbox_point, checkbox_rect.size())

    def paint(self, painter, option, index):
        data = self.model.data(index)

        if option.state & QStyle.State_Selected:
            painter.save()
            painter.setBrush(QApplication.palette().highlight())
            painter.drawRect(option.rect)
            painter.restore()

        checkbox_style = QStyleOptionButton()
        checkbox_style.state |= QStyle.State_Enabled
        checkbox_style.state |= QStyle.State_On if data else QStyle.State_Off
        checkbox_style.rect = self.__get_checkbox_rect(option)

        QApplication.style().drawControl(QStyle.CE_CheckBox, checkbox_style, painter)

    def updateEditorGeometry(self, editor, option, _):
        editor.setGeometry(self.__get_checkbox_rect(option))
