from qtpy.QtCore import QPoint, QRect, Qt
from qtpy.QtWidgets import (
    QStyle,
    QCheckBox,
    QApplication,
    QStyleOptionButton,
    QStyledItemDelegate,
    QStyleOptionFocusRect
)


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
        style = QApplication.style()

        checkbox_style = QStyleOptionButton()
        checkbox_rect = style.subElementRect(QStyle.SE_CheckBoxIndicator, checkbox_style)
        checkbox_point = QPoint(
            option.rect.x() + (option.rect.width() - checkbox_rect.width()) / 2,
            option.rect.y() + (option.rect.height() - checkbox_rect.height()) / 2
        )

        return QRect(checkbox_point, checkbox_rect.size())

    def paint(self, painter, option, index):
        data = self.model.data(index)

        style = QApplication.style()
        palette = QApplication.palette()

        # Draw the selection background
        if option.state & QStyle.State_Selected:
            painter.save()
            painter.setPen(Qt.NoPen)  # Removes border on the top and left
            painter.setBrush(palette.highlight())
            painter.drawRect(option.rect)
            painter.restore()

        # Draw the focus rectangle, there doesn't seem to be a simple way to do this.
        if option.state & QStyle.State_HasFocus:
            focus_style = QStyleOptionFocusRect()

            focus_style.state = option.state | QStyle.State_KeyboardFocusChange | QStyle.State_Item
            focus_style.direction = option.direction
            focus_style.fontMetrics = option.fontMetrics
            focus_style.styleObject = option.styleObject

            if style.objectName() == "windowsvista":
                # The Windows style for Qt seems to remove 1px from each side of the rect.
                # I'm sure that there is a way to do this without hard-coding, but I can't find it.
                focus_style.rect = QRect(
                    option.rect.x() + 1,
                    option.rect.y(),
                    option.rect.width() - 2,
                    option.rect.height()
                )
            else:
                # If the theme is anything else, the normal rectangle of style option should suffice.
                focus_style.rect = option.rect

            focus_style.backgroundColor = option.palette.color(
                palette.Normal if option.state & QStyle.State_Enabled else palette.Disabled,
                palette.Highlight if option.state & QStyle.State_Selected else palette.Window
            )

            painter.save()
            style.drawPrimitive(QStyle.PE_FrameFocusRect, focus_style, painter)
            painter.restore()

        checkbox_style = QStyleOptionButton()
        checkbox_style.state |= QStyle.State_Enabled if option.state & QStyle.State_Enabled else QStyle.State_NoChange
        checkbox_style.state |= QStyle.State_On if data else QStyle.State_Off
        checkbox_style.rect = self.__get_checkbox_rect(option)

        painter.save()
        style.drawControl(QStyle.CE_CheckBox, checkbox_style, painter)
        painter.restore()

    def updateEditorGeometry(self, editor, option, _):
        editor.setGeometry(self.__get_checkbox_rect(option))
