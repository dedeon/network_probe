# -*- mode: python ; coding: utf-8 -*-
import os
import sys

SCRIPT_DIR = SPECPATH
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
UPX_DIR = os.path.join(SCRIPT_DIR, '_upx')

a = Analysis(
    [os.path.join(SCRIPT_DIR, 'main.py')],
    pathex=[SCRIPT_DIR, PARENT_DIR],
    binaries=[],
    datas=[
        (os.path.join(SCRIPT_DIR, 'ui'), 'ui'),
        (os.path.join(SCRIPT_DIR, 'engines'), 'engines'),
        (os.path.join(SCRIPT_DIR, 'utils'), 'utils'),
        (os.path.join(SCRIPT_DIR, 'storage'), 'storage'),
    ],
    hiddenimports=[
        'ui', 'ui.main_window', 'ui.instant_panel', 'ui.longterm_panel',
        'engines', 'engines.ping_engine', 'engines.dns_engine',
        'engines.curl_engine', 'engines.tcp_keepalive_engine',
        'utils', 'utils.validators', 'utils.statistics',
        'storage', 'storage.manager',
        'dns.resolver', 'dns.rdatatype', 'dns.name', 'dns.rdata',
        'dns.rdataclass', 'dns.message', 'dns.query', 'dns.exception',
        'dns.zone', 'dns.rcode', 'dns.opcode', 'dns.entropy',
        'dns.wire', 'dns.tokenizer', 'dns.namedict', 'dns.set',
        'dns.transaction', 'dns.versioned', 'dns.node', 'dns.rrset',
        'dns.immutable', 'dns.edns', 'dns.flags', 'dns.inet',
        'dns.ipv4', 'dns.ipv6',
        'requests', 'requests.adapters', 'requests.auth',
        'requests.cookies', 'requests.models', 'requests.sessions',
        'requests.structures', 'requests.utils',
        'urllib3', 'charset_normalizer', 'certifi', 'idna',
        'ssl', '_ssl',
        'PyQt6.sip', 'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # ── 不需要的标准库 ──
        'matplotlib', 'numpy', 'scipy', 'pandas', 'PIL', 'tkinter',
        'test', 'unittest', 'doctest', 'pydoc', 'pdb', 'lib2to3',
        'multiprocessing', 'asyncio', 'concurrent', 'xmlrpc',
        'distutils', 'setuptools', 'pkg_resources', 'ensurepip', 'pip',
        # ── 不需要的 PyQt6 模块 ──
        'PyQt6.QtQml', 'PyQt6.QtQuick', 'PyQt6.QtQuickWidgets',
        'PyQt6.QtNetwork', 'PyQt6.QtSvg', 'PyQt6.QtSvgWidgets',
        'PyQt6.QtMultimedia', 'PyQt6.QtMultimediaWidgets',
        'PyQt6.QtBluetooth', 'PyQt6.QtDBus', 'PyQt6.QtDesigner',
        'PyQt6.QtHelp', 'PyQt6.QtOpenGL', 'PyQt6.QtOpenGLWidgets',
        'PyQt6.QtPositioning', 'PyQt6.QtPrintSupport',
        'PyQt6.QtSensors', 'PyQt6.QtSerialPort', 'PyQt6.QtSql',
        'PyQt6.QtTest', 'PyQt6.QtWebChannel', 'PyQt6.QtWebEngine',
        'PyQt6.QtWebEngineCore', 'PyQt6.QtWebEngineWidgets',
        'PyQt6.QtWebSockets', 'PyQt6.QtXml',
        'PyQt6.QtPdf', 'PyQt6.QtPdfWidgets',
        'PyQt6.Qt3DCore', 'PyQt6.Qt3DRender', 'PyQt6.Qt3DInput',
        'PyQt6.Qt3DLogic', 'PyQt6.Qt3DExtras', 'PyQt6.Qt3DAnimation',
        'PyQt6.QtCharts', 'PyQt6.QtDataVisualization',
        'PyQt6.QtRemoteObjects', 'PyQt6.QtTextToSpeech',
        'PyQt6.QtNfc', 'PyQt6.QtQuick3D',
    ],
    noarchive=False,
)

# ── 过滤掉不需要的大型二进制文件 ──
# 这些 DLL 占用巨大空间但本工具完全不需要
_EXCLUDE_BINARIES = {
    # 软件 OpenGL 模拟器 (~20 MB) — 不需要 3D 渲染
    'opengl32sw.dll',
    # FFmpeg 音视频编解码 (~16 MB) — 不需要多媒体
    'avcodec-61.dll', 'avformat-61.dll', 'avutil-59.dll',
    'swresample-5.dll', 'swscale-8.dll',
    # D3D 着色器编译器 (~4 MB) — 不需要 3D
    'd3dcompiler_47.dll',
    # Qt Quick / QML 引擎 (~11 MB) — 只用 Widgets
    'Qt6Quick.dll', 'Qt6Qml.dll', 'Qt6QmlModels.dll',
    'Qt6QmlWorkerScript.dll', 'Qt6QmlCore.dll', 'Qt6QmlLocalStorage.dll',
    'Qt6QuickTemplates2.dll', 'Qt6QuickControls2.dll',
    'Qt6QuickControls2Impl.dll', 'Qt6QuickControls2Basic.dll',
    'Qt6QuickControls2BasicStyleImpl.dll',
    'Qt6QuickControls2Material.dll', 'Qt6QuickControls2MaterialStyleImpl.dll',
    'Qt6QuickControls2Universal.dll', 'Qt6QuickControls2Imagine.dll',
    'Qt6QuickDialogs2.dll', 'Qt6QuickDialogs2QuickImpl.dll',
    'Qt6QuickDialogs2Utils.dll', 'Qt6QuickEffects.dll',
    'Qt6QuickLayouts.dll', 'Qt6QuickParticles.dll',
    'Qt6QuickShapes.dll', 'Qt6QuickTest.dll',
    # Qt 3D / ShaderTools (~8 MB) — 不需要 3D
    'Qt6ShaderTools.dll', 'Qt6Quick3DRuntimeRender.dll',
    'Qt6Quick3DPhysics.dll', 'Qt6Quick3D.dll', 'Qt6Quick3DUtils.dll',
    'Qt63DCore.dll', 'Qt63DRender.dll', 'Qt63DInput.dll',
    'Qt63DLogic.dll', 'Qt63DExtras.dll', 'Qt63DAnimation.dll',
    # Qt 其他不需要的模块
    'Qt6Designer.dll', 'Qt6Network.dll', 'Qt6OpenGL.dll',
    'Qt6Pdf.dll', 'Qt6Svg.dll', 'Qt6Multimedia.dll',
    'Qt6MultimediaQuick.dll', 'Qt6WebChannel.dll',
    'Qt6WebSockets.dll', 'Qt6Bluetooth.dll', 'Qt6Nfc.dll',
    'Qt6Sensors.dll', 'Qt6SerialPort.dll', 'Qt6Sql.dll',
    'Qt6Test.dll', 'Qt6Xml.dll', 'Qt6Charts.dll',
    'Qt6DataVisualization.dll', 'Qt6RemoteObjects.dll',
    'Qt6TextToSpeech.dll', 'Qt6Positioning.dll',
    'Qt6PrintSupport.dll', 'Qt6Help.dll',
    'Qt6LabsAnimation.dll', 'Qt6LabsFolderListModel.dll',
    'Qt6LabsQmlModels.dll', 'Qt6LabsSettings.dll',
    'Qt6LabsSharedImage.dll', 'Qt6LabsWavefrontMesh.dll',
    'Qt6StateMachine.dll', 'Qt6StateMachineQml.dll',
}

# 按文件名过滤 binaries
a.binaries = [b for b in a.binaries if os.path.basename(b[1]).lower() not in
               {x.lower() for x in _EXCLUDE_BINARIES}]

# 排除 Qt plugins/qml 中不需要的目录
_EXCLUDE_DIRS = {'qml', 'QtQuick', 'QtQml', 'QtMultimedia', 'Qt3D',
                 'QtWebEngine', 'QtDesigner', 'sceneparsers', 'assetimporters',
                 'sqldrivers', 'multimedia', 'position', 'networkinformation',
                 'designer', 'quick3d'}
a.binaries = [b for b in a.binaries
               if not any(d in b[0].replace('\\', '/').lower() for d in
                          {x.lower() for x in _EXCLUDE_DIRS})]
a.datas = [d for d in a.datas
            if not any(x in d[0].replace('\\', '/').lower() for x in
                       {y.lower() for y in _EXCLUDE_DIRS})]

# ── 强制追加 OpenSSL DLL（在所有过滤之后，确保不会被误删）──
# _ssl.pyd 依赖 libssl-3.dll + libcrypto-3.dll，缺失会导致 import _ssl 失败
_build_python = os.path.join(SCRIPT_DIR, '_build_python')
_ssl_search_dirs = [_build_python, sys.base_prefix, sys.prefix,
                    os.path.join(sys.base_prefix, 'DLLs'),
                    os.path.join(sys.prefix, 'DLLs'),
                    os.path.join(sys.prefix, 'Library', 'bin')]
_ssl_dll_patterns = ['libssl-3.dll', 'libcrypto-3.dll',
                     'libssl-3-x64.dll', 'libcrypto-3-x64.dll',
                     'libssl-1_1-x64.dll', 'libcrypto-1_1-x64.dll']
_ssl_already = {os.path.basename(b[1]).lower() for b in a.binaries}
for _pat in _ssl_dll_patterns:
    if _pat.lower() in _ssl_already:
        continue
    for _sd in _ssl_search_dirs:
        _fp = os.path.join(_sd, _pat)
        if os.path.isfile(_fp):
            a.binaries.append((_pat, _fp, 'BINARY'))
            _ssl_already.add(_pat.lower())
            print(f'  [SSL-FIX] Force added: {_fp}')
            break

# 同样确保 _ssl.pyd 被包含
_ssl_pyd_names = ['_ssl.pyd']
for _pyd in _ssl_pyd_names:
    if _pyd.lower() in _ssl_already:
        continue
    for _sd in _ssl_search_dirs:
        _fp = os.path.join(_sd, _pyd)
        if os.path.isfile(_fp):
            a.binaries.append((_pyd, _fp, 'BINARY'))
            print(f'  [SSL-FIX] Force added: {_fp}')
            break

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='小D网络拨测工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    upx_dir=UPX_DIR,
)
