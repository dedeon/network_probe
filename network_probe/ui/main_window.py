"""主窗口"""
from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QWidget, QVBoxLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon

from .instant_panel import InstantProbePanel
from .longterm_panel import LongtermProbePanel
from ..storage.manager import StorageManager


class MainWindow(QMainWindow):
    """网络拨测工具主窗口"""

    def __init__(self, data_dir: str = None):
        super().__init__()
        self.storage = StorageManager(base_dir=data_dir)
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("🔵 网络拨测工具 v1.0")
        self.setMinimumSize(900, 650)
        self.resize(1100, 780)

        # 设置全局样式
        self.setStyleSheet("""
            QMainWindow {
                background: #ffffff;
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
        self.status_bar.showMessage("就绪 | 网络拨测工具 v1.0")

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
