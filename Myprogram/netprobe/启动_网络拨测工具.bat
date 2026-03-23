@echo off
chcp 65001 >nul 2>&1
title 网络拨测工具 v1.0

:: 获取脚本所在目录
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [提示] 未检测到 Python，尝试使用嵌入式 Python...
    if exist "%SCRIPT_DIR%python\python.exe" (
        set PYTHON_EXE=%SCRIPT_DIR%python\python.exe
        goto :run
    )
    echo [错误] 未找到 Python 环境。
    echo 请安装 Python 3.10+ 或使用 build_windows.bat 构建独立 exe。
    pause
    exit /b 1
)
set PYTHON_EXE=python

:: 检查依赖
:check_deps
%PYTHON_EXE% -c "import PyQt6; import dns; import requests" >nul 2>&1
if errorlevel 1 (
    echo [提示] 首次运行，正在安装依赖...
    %PYTHON_EXE% -m pip install PyQt6 dnspython requests -q
    if errorlevel 1 (
        echo [错误] 依赖安装失败，请检查网络连接。
        pause
        exit /b 1
    )
    echo     依赖安装完成。
)

:run
echo 正在启动网络拨测工具...
%PYTHON_EXE% "%SCRIPT_DIR%main.py"

if errorlevel 1 (
    echo.
    echo [错误] 程序异常退出，请查看上方错误信息。
    pause
)
