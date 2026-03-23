@echo off
chcp 65001 >nul 2>&1
title 网络拨测工具 - 构建脚本

echo ============================================
echo   网络拨测工具 Windows 一键构建脚本
echo ============================================
echo.

:: 检查 Python 是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.10 或以上版本。
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/4] 检测到 Python 环境：
python --version
echo.

:: 安装依赖
echo [2/4] 安装项目依赖...
pip install PyQt6>=6.5.0 dnspython>=2.4.0 requests>=2.31.0 pyinstaller>=6.0.0 -q
if errorlevel 1 (
    echo [错误] 依赖安装失败，请检查网络连接。
    pause
    exit /b 1
)
echo     依赖安装完成。
echo.

:: 获取脚本所在目录
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

:: PyInstaller 打包
echo [3/4] 开始打包（单目录绿色版）...
echo     这可能需要几分钟，请耐心等待...
echo.
pyinstaller netprobe.spec --noconfirm --clean 2>&1
if errorlevel 1 (
    echo.
    echo [错误] 打包失败，请查看上方错误信息。
    pause
    exit /b 1
)
echo.

:: 复制数据目录到输出
echo [4/4] 整理输出文件...
if not exist "dist\网络拨测工具\data" mkdir "dist\网络拨测工具\data"
if not exist "dist\网络拨测工具\data\history\instant" mkdir "dist\网络拨测工具\data\history\instant"
if not exist "dist\网络拨测工具\data\history\longterm" mkdir "dist\网络拨测工具\data\history\longterm"

echo.
echo ============================================
echo   ✅ 构建成功！
echo ============================================
echo.
echo   输出目录: %SCRIPT_DIR%dist\网络拨测工具\
echo   启动文件: dist\网络拨测工具\网络拨测工具.exe
echo.
echo   使用方式:
echo     1. 将 "dist\网络拨测工具" 整个文件夹复制到目标机器
echo     2. 双击 "网络拨测工具.exe" 即可运行
echo     3. 无需安装 Python 或任何依赖
echo.
echo   压缩为便携版:
echo     将 "dist\网络拨测工具" 文件夹压缩为 zip 即可分发
echo ============================================

:: 打开输出目录
explorer "dist\网络拨测工具"

pause
