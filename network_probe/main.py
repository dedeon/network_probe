#!/usr/bin/env python3
"""
网络拨测工具 v1.0
================
Windows 单机网络拨测客户端工具
支持 Ping / DNS / HTTP(S) 三种拨测协议
提供即时拨测和长时间拨测两大核心功能

启动方式:
    python main.py

依赖安装:
    pip install PyQt6 dnspython requests
"""
import sys
import os

# 判断是否为 PyInstaller 打包后运行
if getattr(sys, 'frozen', False):
    # PyInstaller 打包后，_MEIPASS 指向临时资源目录
    BASE_DIR = os.path.dirname(sys.executable)
    # 将临时资源目录也加入路径（用于找到 network_probe 包）
    if hasattr(sys, '_MEIPASS'):
        sys.path.insert(0, sys._MEIPASS)
    sys.path.insert(0, BASE_DIR)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, BASE_DIR)

# 将当前脚本所在目录加入路径，确保子模块可被导入
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont, QIcon, QPalette, QColor
from PyQt6.QtCore import Qt

from ui.main_window import MainWindow


def _force_light_palette(app: QApplication):
    """强制设置浅色调色板，确保在 Windows 暗黑模式下也能正常显示"""
    palette = QPalette()
    # 基础颜色
    palette.setColor(QPalette.ColorRole.Window, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#1a1a1a"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#f5f5f5"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#ffffdc"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#1a1a1a"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#1a1a1a"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#f0f0f0"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#1a1a1a"))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ff0000"))
    palette.setColor(QPalette.ColorRole.Link, QColor("#1a73e8"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#1a73e8"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    # PlaceholderText
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#999999"))
    # Light / Midlight / Mid / Dark / Shadow (用于3D效果)
    palette.setColor(QPalette.ColorRole.Light, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Midlight, QColor("#e8e8e8"))
    palette.setColor(QPalette.ColorRole.Mid, QColor("#c0c0c0"))
    palette.setColor(QPalette.ColorRole.Dark, QColor("#808080"))
    palette.setColor(QPalette.ColorRole.Shadow, QColor("#505050"))

    # Disabled 状态
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor("#aaaaaa"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#aaaaaa"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor("#aaaaaa"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Base, QColor("#f0f0f0"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Button, QColor("#e0e0e0"))

    app.setPalette(palette)


def main():
    # 高DPI支持（PyQt6默认支持）
    app = QApplication(sys.argv)

    # 设置应用信息
    app.setApplicationName("小D网络拨测工具")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("XiaoD")

    # 全局字体设置 - 优先使用微软雅黑，回退到其他字体
    font = QFont()
    preferred_fonts = ["Microsoft YaHei", "SimHei", "WenQuanYi Micro Hei", "sans-serif"]
    for f in preferred_fonts:
        font.setFamily(f)
        if font.exactMatch() or f == preferred_fonts[-1]:
            break
    font.setPointSize(10)
    app.setFont(font)

    # 全局样式 - 使用 Fusion 并强制浅色调色板，防止 Windows 暗黑模式干扰
    app.setStyle("Fusion")
    _force_light_palette(app)

    # 设置数据目录（打包后使用exe所在目录下的data文件夹）
    data_dir = os.path.join(BASE_DIR, 'data')

    # 创建主窗口
    window = MainWindow(data_dir=data_dir)
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
