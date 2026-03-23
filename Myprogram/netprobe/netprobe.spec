# -*- mode: python ; coding: utf-8 -*-
"""
网络拨测工具 PyInstaller 打包配置
生成单目录（免安装绿色版）Windows exe
"""

import sys
import os

block_cipher = None

# 项目根目录
PROJ_DIR = os.path.dirname(os.path.abspath(SPECPATH))

a = Analysis(
    [os.path.join(PROJ_DIR, 'main.py')],
    pathex=[os.path.dirname(PROJ_DIR)],  # 父目录，确保 netprobe 包可导入
    binaries=[],
    datas=[],
    hiddenimports=[
        'dns.resolver',
        'dns.rdatatype',
        'dns.name',
        'dns.rdata',
        'dns.rdataclass',
        'dns.message',
        'dns.query',
        'dns.exception',
        'dns.zone',
        'dns.rcode',
        'dns.opcode',
        'requests',
        'requests.adapters',
        'requests.auth',
        'requests.cookies',
        'requests.models',
        'requests.sessions',
        'requests.structures',
        'requests.utils',
        'urllib3',
        'charset_normalizer',
        'certifi',
        'idna',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'numpy', 'scipy', 'pandas', 'PIL',
        'tkinter', 'test', 'unittest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='网络拨测工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 无控制台窗口（GUI程序）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='icon.ico',  # 如有图标可取消注释
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='网络拨测工具',
)
