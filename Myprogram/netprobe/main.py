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
    # 将应用目录加入路径
    sys.path.insert(0, BASE_DIR)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, BASE_DIR)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtCore import Qt

from netprobe.ui.main_window import MainWindow


def main():
    # 高DPI支持（PyQt6默认支持）
    app = QApplication(sys.argv)

    # 设置应用信息
    app.setApplicationName("网络拨测工具")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("NetProbe")

    # 全局字体设置 - 优先使用微软雅黑，回退到其他字体
    font = QFont()
    preferred_fonts = ["Microsoft YaHei", "SimHei", "WenQuanYi Micro Hei", "sans-serif"]
    for f in preferred_fonts:
        font.setFamily(f)
        if font.exactMatch() or f == preferred_fonts[-1]:
            break
    font.setPointSize(10)
    app.setFont(font)

    # 全局样式
    app.setStyle("Fusion")

    # 设置数据目录（打包后使用exe所在目录下的data文件夹）
    data_dir = os.path.join(BASE_DIR, 'data')

    # 创建主窗口
    window = MainWindow(data_dir=data_dir)
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
