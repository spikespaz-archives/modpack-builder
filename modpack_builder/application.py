import os
import sys

from pathlib import Path

os.environ["QT_API"] = "pyqt5"

import markdown2

from qtpy.QtWidgets import QApplication, QMainWindow
from qtpy.QtWebEngineWidgets import QWebEnginePage
from qtpy.QtGui import QDesktopServices
from qtpy import QtCore
from qtpy import uic


class QLockedWebEnginePage(QWebEnginePage):
    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        if nav_type == QWebEnginePage.NavigationTypeTyped:
            return super().acceptNavigationRequest(url, nav_type, is_main_frame)

        QDesktopServices.openUrl(url)
        return False


class ModpackBuilderWindow(QMainWindow):
    __should_reset_profile_icon_path = False
    
    def __init__(self, builder, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.builder = builder

        uic.loadUi(str((Path(__file__).parent / "interface.ui").resolve()), self)

        # Fix for PyQt5
        if os.environ["QT_API"] == "pyqt5":
            self.setContentsMargins(9, 9, 9, 9)

        # Set up the QWebEngineView for the markdown information view
        self.information_tab_frame.layout().setContentsMargins(0, 0, 0, 0)
        self.information_web_engine_page = QLockedWebEnginePage()
        self.information_web_engine_view.setPage(self.information_web_engine_page)
        self.information_web_engine_view.setContextMenuPolicy(QtCore.Qt.PreventContextMenu)
        self.information_web_engine_view.setZoomFactor(0.75)

    def show_information_markdown(self, readme_path):
        with open((Path(__file__).parent / "markdown.css").resolve(), "r", encoding="utf-8") as markdown_css_file:
            markdown_css = markdown_css_file.read()

        with open(readme_path, "r", encoding="utf-8") as readme_file:
            readme_markdown = readme_file.read()

        readme_html = markdown2.markdown(
            readme_markdown,
            extras="cuddled-lists fenced-code-blocks smartypants spoiler strike tables tag-friendly task_list".split()
        )
        readme_html = f"""
        <html>
            <head>
                <style>
                    body {{
                        margin: 20px 30px;
                        user-select: none;
                    }}

                    {markdown_css}
                </style>
            </head>
            <body class='markdown-body'>
                {readme_html}
            </body>
        </html>
        """

        self.information_web_engine_page.setHtml(readme_html)


if __name__ == "__main__":
    app = QApplication([])
    window = ModpackBuilderWindow(None)
    window.show_information_markdown((Path(__file__).parent.parent / "modpack/README.md").resolve())

    window.show()
    sys.exit(app.exec_())
