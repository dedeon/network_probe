#!/usr/bin/env python3
"""
网络拨测工具 - 跨平台构建脚本
在 Windows 上运行此脚本即可构建 exe
用法: python build.py [--onefile] [--onedir]
"""
import subprocess
import sys
import os
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
DIST_DIR = os.path.join(SCRIPT_DIR, 'dist')
BUILD_DIR = os.path.join(SCRIPT_DIR, 'build')
APP_NAME = '网络拨测工具'


def install_deps():
    """安装构建依赖"""
    print("[1/4] 安装依赖...")
    subprocess.check_call([
        sys.executable, '-m', 'pip', 'install', '-q',
        'PyQt6>=6.5.0', 'dnspython>=2.4.0', 'requests>=2.31.0', 'pyinstaller>=6.0.0'
    ])
    print("      完成。")


def build_onefile():
    """构建单文件 exe"""
    print("[2/4] 构建单文件版 exe...")
    print("      这可能需要 3-5 分钟，请耐心等待...\n")

    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--noconfirm', '--clean',
        '--name', APP_NAME,
        '--windowed',  # 无控制台
        '--onefile',
        '--paths', PARENT_DIR,
        # 隐式导入
        '--hidden-import', 'dns.resolver',
        '--hidden-import', 'dns.rdatatype',
        '--hidden-import', 'dns.name',
        '--hidden-import', 'dns.rdata',
        '--hidden-import', 'dns.rdataclass',
        '--hidden-import', 'dns.message',
        '--hidden-import', 'dns.query',
        '--hidden-import', 'dns.exception',
        '--hidden-import', 'dns.zone',
        '--hidden-import', 'dns.rcode',
        '--hidden-import', 'dns.opcode',
        '--hidden-import', 'requests',
        '--hidden-import', 'urllib3',
        '--hidden-import', 'charset_normalizer',
        '--hidden-import', 'certifi',
        '--hidden-import', 'idna',
        # 排除不需要的模块
        '--exclude-module', 'matplotlib',
        '--exclude-module', 'numpy',
        '--exclude-module', 'scipy',
        '--exclude-module', 'pandas',
        '--exclude-module', 'PIL',
        '--exclude-module', 'tkinter',
        '--exclude-module', 'test',
        '--exclude-module', 'unittest',
        os.path.join(SCRIPT_DIR, 'main.py')
    ]
    subprocess.check_call(cmd, cwd=SCRIPT_DIR)
    print("\n      单文件构建完成。")


def build_onedir():
    """构建单目录版"""
    print("[2/4] 构建单目录版...")
    print("      这可能需要 3-5 分钟，请耐心等待...\n")

    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--noconfirm', '--clean',
        '--name', APP_NAME,
        '--windowed',
        '--paths', PARENT_DIR,
        '--hidden-import', 'dns.resolver',
        '--hidden-import', 'dns.rdatatype',
        '--hidden-import', 'dns.name',
        '--hidden-import', 'dns.rdata',
        '--hidden-import', 'dns.rdataclass',
        '--hidden-import', 'dns.message',
        '--hidden-import', 'dns.query',
        '--hidden-import', 'dns.exception',
        '--hidden-import', 'dns.zone',
        '--hidden-import', 'dns.rcode',
        '--hidden-import', 'dns.opcode',
        '--hidden-import', 'requests',
        '--hidden-import', 'urllib3',
        '--hidden-import', 'charset_normalizer',
        '--hidden-import', 'certifi',
        '--hidden-import', 'idna',
        '--exclude-module', 'matplotlib',
        '--exclude-module', 'numpy',
        '--exclude-module', 'scipy',
        '--exclude-module', 'pandas',
        '--exclude-module', 'PIL',
        '--exclude-module', 'tkinter',
        '--exclude-module', 'test',
        '--exclude-module', 'unittest',
        os.path.join(SCRIPT_DIR, 'main.py')
    ]
    subprocess.check_call(cmd, cwd=SCRIPT_DIR)
    print("\n      单目录构建完成。")


def create_data_dirs(output_dir):
    """创建数据目录结构"""
    print("[3/4] 创建数据目录...")
    data_dir = os.path.join(output_dir, 'data')
    os.makedirs(os.path.join(data_dir, 'history', 'instant'), exist_ok=True)
    os.makedirs(os.path.join(data_dir, 'history', 'longterm'), exist_ok=True)
    print("      完成。")


def show_result(mode, output_path):
    """显示构建结果"""
    print()
    print("=" * 52)
    print("  ✅ 构建成功！")
    print("=" * 52)
    if mode == 'onefile':
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"  输出文件: {output_path}")
        print(f"  文件大小: {size_mb:.1f} MB")
        print()
        print("  使用方式:")
        print("    直接双击 exe 文件即可运行")
        print("    无需安装 Python 或任何依赖")
    else:
        total_size = sum(
            os.path.getsize(os.path.join(dp, f))
            for dp, dn, filenames in os.walk(output_path)
            for f in filenames
        )
        size_mb = total_size / (1024 * 1024)
        print(f"  输出目录: {output_path}")
        print(f"  总大小:   {size_mb:.1f} MB")
        print()
        print("  使用方式:")
        print(f"    1. 将 \"{APP_NAME}\" 文件夹复制到目标机器")
        print(f"    2. 双击 \"{APP_NAME}.exe\" 即可运行")
        print("    3. 无需安装 Python 或任何依赖")
    print()
    print("  分发方式: 压缩为 zip 文件即可分发")
    print("=" * 52)


def main():
    # 解析参数
    mode = 'onefile'  # 默认单文件
    if '--onedir' in sys.argv:
        mode = 'onedir'
    elif '--onefile' in sys.argv:
        mode = 'onefile'
    elif len(sys.argv) > 1 and sys.argv[1] not in ('--onefile', '--onedir'):
        print(f"用法: python {sys.argv[0]} [--onefile|--onedir]")
        print("  --onefile  构建单个 exe 文件（默认，推荐分发）")
        print("  --onedir   构建单目录版（启动更快）")
        return

    print("=" * 52)
    print(f"  {APP_NAME} - 构建脚本")
    print(f"  模式: {'单文件版' if mode == 'onefile' else '单目录版'}")
    print("=" * 52)
    print()

    try:
        install_deps()

        if mode == 'onefile':
            build_onefile()
            output_path = os.path.join(DIST_DIR, f'{APP_NAME}.exe')
            # 单文件无需 data 目录（会在 exe 同级目录自动创建）
            print("[3/4] 单文件版数据目录将在运行时自动创建。")
            print("[4/4] 清理临时文件...")
            if os.path.exists(BUILD_DIR):
                shutil.rmtree(BUILD_DIR, ignore_errors=True)
            show_result('onefile', output_path)
        else:
            build_onedir()
            output_dir = os.path.join(DIST_DIR, APP_NAME)
            create_data_dirs(output_dir)
            print("[4/4] 清理临时文件...")
            if os.path.exists(BUILD_DIR):
                shutil.rmtree(BUILD_DIR, ignore_errors=True)
            show_result('onedir', output_dir)

    except subprocess.CalledProcessError as e:
        print(f"\n[错误] 构建失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[错误] {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
