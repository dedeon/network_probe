@echo off
chcp 65001 >nul 2>&1
title 网络拨测工具 - 构建完全免安装绿色版

echo ============================================
echo   网络拨测工具 - 构建完全免安装绿色版
echo   (无需目标机器安装Python)
echo ============================================
echo.

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

:: ========== 方式一：使用 PyInstaller ==========
echo 请选择构建方式:
echo   1. PyInstaller 打包（推荐，体积较小）
echo   2. 嵌入式 Python 打包（备选，兼容性好）
echo.
set /p BUILD_MODE="请输入选择 (1 或 2，默认1): "
if "%BUILD_MODE%"=="" set BUILD_MODE=1

if "%BUILD_MODE%"=="2" goto :embedded_build

:: ========== PyInstaller 构建 ==========
:pyinstaller_build
echo.
echo [1/3] 安装构建依赖...
pip install PyQt6>=6.5.0 dnspython>=2.4.0 requests>=2.31.0 pyinstaller>=6.0.0 -q
if errorlevel 1 (
    echo [错误] 依赖安装失败
    pause
    exit /b 1
)
echo     完成。

echo.
echo [2/3] PyInstaller 打包中（约需3-5分钟）...
echo.

:: 选择单文件或单目录
echo   a. 单文件版（一个 exe，启动稍慢 ~3秒）
echo   b. 单目录版（文件夹，启动更快）
echo.
set /p EXE_MODE="请输入选择 (a 或 b，默认a): "
if "%EXE_MODE%"=="" set EXE_MODE=a

if "%EXE_MODE%"=="b" (
    pyinstaller netprobe.spec --noconfirm --clean
) else (
    pyinstaller netprobe_onefile.spec --noconfirm --clean
)

if errorlevel 1 (
    echo [错误] 打包失败
    pause
    exit /b 1
)

echo.
echo [3/3] 整理输出...
if "%EXE_MODE%"=="b" (
    if not exist "dist\网络拨测工具\data\history\instant" mkdir "dist\网络拨测工具\data\history\instant"
    if not exist "dist\网络拨测工具\data\history\longterm" mkdir "dist\网络拨测工具\data\history\longterm"
    echo.
    echo ============================================
    echo   ✅ 构建成功！（单目录版）
    echo   输出: %SCRIPT_DIR%dist\网络拨测工具\
    echo   运行: 双击 网络拨测工具.exe
    echo ============================================
    explorer "dist\网络拨测工具"
) else (
    if not exist "dist" mkdir "dist"
    echo.
    echo ============================================
    echo   ✅ 构建成功！（单文件版）
    echo   输出: %SCRIPT_DIR%dist\网络拨测工具.exe
    echo   运行: 双击 网络拨测工具.exe 即可
    echo ============================================
    explorer "dist"
)
pause
exit /b 0

:: ========== 嵌入式 Python 构建 ==========
:embedded_build
echo.
echo [1/4] 下载 Python 嵌入式包...
set PYTHON_VER=3.11.7
set PYTHON_ZIP=python-%PYTHON_VER%-embed-amd64.zip
set PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VER%/%PYTHON_ZIP%

if not exist "%PYTHON_ZIP%" (
    echo     下载 %PYTHON_URL% ...
    powershell -Command "Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%PYTHON_ZIP%'"
    if errorlevel 1 (
        echo [错误] 下载失败，请检查网络连接
        pause
        exit /b 1
    )
)
echo     完成。

echo.
echo [2/4] 解压嵌入式 Python...
set OUTPUT_DIR=dist\NetProbe_Portable
if exist "%OUTPUT_DIR%" rmdir /s /q "%OUTPUT_DIR%"
mkdir "%OUTPUT_DIR%\python"
powershell -Command "Expand-Archive -Path '%PYTHON_ZIP%' -DestinationPath '%OUTPUT_DIR%\python' -Force"
echo     完成。

echo.
echo [3/4] 安装 pip 并安装依赖到嵌入式 Python...
:: 启用 import site
powershell -Command "(Get-Content '%OUTPUT_DIR%\python\python311._pth') -replace '#import site','import site' | Set-Content '%OUTPUT_DIR%\python\python311._pth'"

:: 下载并安装 pip
powershell -Command "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%OUTPUT_DIR%\python\get-pip.py'"
"%OUTPUT_DIR%\python\python.exe" "%OUTPUT_DIR%\python\get-pip.py" --no-warn-script-location -q

:: 安装依赖
"%OUTPUT_DIR%\python\python.exe" -m pip install PyQt6 dnspython requests --no-warn-script-location -q --target "%OUTPUT_DIR%\python\Lib\site-packages"
echo     完成。

echo.
echo [4/4] 复制程序文件...
:: 复制项目文件
xcopy /E /I /Q "engines" "%OUTPUT_DIR%\netprobe\engines\"
xcopy /E /I /Q "ui" "%OUTPUT_DIR%\netprobe\ui\"
xcopy /E /I /Q "storage" "%OUTPUT_DIR%\netprobe\storage\"
xcopy /E /I /Q "utils" "%OUTPUT_DIR%\netprobe\utils\"
copy "__init__.py" "%OUTPUT_DIR%\netprobe\"
copy "main.py" "%OUTPUT_DIR%\netprobe\"

:: 创建数据目录
mkdir "%OUTPUT_DIR%\data\history\instant"
mkdir "%OUTPUT_DIR%\data\history\longterm"

:: 创建启动脚本
(
echo @echo off
echo chcp 65001 ^>nul 2^>^&1
echo set SCRIPT_DIR=%%~dp0
echo cd /d "%%SCRIPT_DIR%%"
echo start "" "%%SCRIPT_DIR%%python\python.exe" "%%SCRIPT_DIR%%netprobe\main.py"
) > "%OUTPUT_DIR%\网络拨测工具.bat"

:: 创建 VBS 启动器（无控制台窗口）
(
echo Set WshShell = CreateObject("WScript.Shell"^)
echo WshShell.CurrentDirectory = CreateObject("Scripting.FileSystemObject"^).GetParentFolderName(WScript.ScriptFullName^)
echo WshShell.Run "python\pythonw.exe netprobe\main.py", 0, False
) > "%OUTPUT_DIR%\网络拨测工具.vbs"

echo.
echo ============================================
echo   ✅ 构建成功！（嵌入式 Python 便携版）
echo ============================================
echo.
echo   输出目录: %SCRIPT_DIR%%OUTPUT_DIR%\
echo   启动方式:
echo     - 双击 "网络拨测工具.vbs"（无控制台窗口，推荐）
echo     - 双击 "网络拨测工具.bat"（有控制台窗口）
echo.
echo   分发方式: 将整个文件夹压缩为zip发送给用户即可
echo   无需目标机器安装 Python 或任何依赖！
echo ============================================

explorer "%OUTPUT_DIR%"
pause
