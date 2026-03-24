"""主窗口"""
from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QWidget, QVBoxLayout,
    QMessageBox, QMenuBar
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon, QAction

APP_NAME = "小D网络拨测工具"
APP_VERSION = "1.0.0"
APP_DEVELOPER_EMAIL = "xudong.cn@gmail.com"

from ui.instant_panel import InstantProbePanel
from ui.longterm_panel import LongtermProbePanel
from storage.manager import StorageManager


class MainWindow(QMainWindow):
    """网络拨测工具主窗口"""

    def __init__(self, data_dir: str = None):
        super().__init__()
        self.storage = StorageManager(base_dir=data_dir)
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle(f"🔵 {APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(900, 650)
        self.resize(1100, 780)

        # ── 菜单栏 ──
        self._init_menu()

        # 设置全局样式
        self.setStyleSheet("""
            QMainWindow {
                background: #ffffff;
            }
            QMenuBar {
                background: #f8f9fa;
                border-bottom: 1px solid #e0e0e0;
                font-family: "Microsoft YaHei", "SimHei", sans-serif;
                font-size: 12px;
                padding: 2px 0;
            }
            QMenuBar::item {
                padding: 4px 12px;
                background: transparent;
                border-radius: 4px;
            }
            QMenuBar::item:selected {
                background: #e8f0fe;
                color: #1a73e8;
            }
            QMenu {
                background: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 4px 0;
                font-family: "Microsoft YaHei", "SimHei", sans-serif;
                font-size: 12px;
            }
            QMenu::item {
                padding: 6px 24px;
            }
            QMenu::item:selected {
                background: #e8f0fe;
                color: #1a73e8;
            }
            QTabWidget::pane {
                border: none;
                background: white;
            }
            QTabBar::tab {
                font-family: "Microsoft YaHei", "SimHei", sans-serif;
                font-size: 13px;
                font-weight: bold;
                padding: 10px 30px;
                margin: 2px 4px;
                border: none;
                border-bottom: 3px solid transparent;
                background: #f0f0f0;
                border-radius: 6px 6px 0 0;
                min-width: 140px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                border-bottom: 3px solid #1a73e8;
                color: #1a73e8;
            }
            QTabBar::tab:hover {
                background: #e8f0fe;
            }
            QStatusBar {
                font-family: "Microsoft YaHei", "SimHei", sans-serif;
                font-size: 11px;
                color: #555;
                background: #f8f9fa;
                border-top: 1px solid #e0e0e0;
                padding: 2px 8px;
            }
        """)

        # 中心部件
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Tab 控件
        self.tab_widget = QTabWidget()
        self.tab_widget.setFont(QFont("Microsoft YaHei", 11))

        # 即时拨测面板
        self.instant_panel = InstantProbePanel(
            self.storage,
            status_callback=self._update_status
        )
        self.tab_widget.addTab(self.instant_panel, "📡 即时拨测")

        # 长时间拨测面板
        self.longterm_panel = LongtermProbePanel(
            self.storage,
            status_callback=self._update_status
        )
        self.tab_widget.addTab(self.longterm_panel, "⏱ 长时间拨测")

        layout.addWidget(self.tab_widget)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(f"就绪 | {APP_NAME} v{APP_VERSION}")

    def _init_menu(self):
        """初始化菜单栏"""
        menu_bar = self.menuBar()

        # ── 帮助菜单 ──
        help_menu = menu_bar.addMenu("帮助(&H)")

        # 关于
        about_action = QAction("关于(&A)", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _show_about(self):
        """显示关于对话框"""
        about_html = (
            f'<div style="text-align:center;">'
            f'<h2 style="color:#1a73e8; margin-bottom:4px;">🔵 {APP_NAME}</h2>'
            f'<p style="color:#555; font-size:13px; margin:4px 0;">版本：v{APP_VERSION}</p>'
            f'<hr style="border:none; border-top:1px solid #e0e0e0; margin:12px 0;"/>'
            f'<p style="font-size:13px; margin:4px 0;">开发人邮箱：'
            f'<a href="mailto:{APP_DEVELOPER_EMAIL}" style="color:#1a73e8; text-decoration:none;">'
            f'{APP_DEVELOPER_EMAIL}</a></p>'
            f'</div>'
        )
        msg = QMessageBox(self)
        msg.setWindowTitle(f"关于 {APP_NAME}")
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(about_html)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

    def _update_status(self, text: str):
        """更新状态栏文本"""
        self.status_bar.showMessage(text)

    def closeEvent(self, event):
        """关闭窗口时停止所有运行中的拨测"""
        if self.instant_panel.engine and self.instant_panel.engine.isRunning():
            self.instant_panel.engine.stop()
            self.instant_panel.engine.wait(2000)
        if self.longterm_panel.engine and self.longterm_panel.engine.isRunning():
            self.longterm_panel.engine.stop()
            self.longterm_panel.engine.wait(2000)
        event.accept()
