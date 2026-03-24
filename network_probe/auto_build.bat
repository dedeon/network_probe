@echo off
chcp 65001 >nul 2>&1
title 网络拨测工具 - 自动构建 exe（免安装版）

echo ============================================================
echo   网络拨测工具 - 全自动构建脚本
echo   自动下载 Python + 安装依赖 + PyInstaller 打包
echo   目标: 生成 Windows 免安装单文件 exe
echo ============================================================
echo.

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

:: ========== 配置 ==========
set PYTHON_VER=3.11.9
set PYTHON_ZIP=python-%PYTHON_VER%-embed-amd64.zip
set PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VER%/%PYTHON_ZIP%
set BUILD_PYTHON_DIR=%SCRIPT_DIR%_build_python
set PYTHON_EXE=%BUILD_PYTHON_DIR%\python.exe
set APP_NAME=网络拨测工具

:: ========== 第1步: 检查/下载 Python 嵌入式版 ==========
echo [1/5] 准备 Python 环境...

:: 先检查系统是否已安装 Python
python --version >nul 2>&1
if not errorlevel 1 (
    echo     检测到系统已安装 Python:
    python --version
    set PYTHON_EXE=python
    goto :install_deps
)

:: 检查是否已有构建用的 Python
if exist "%PYTHON_EXE%" (
    echo     使用已下载的构建 Python: %BUILD_PYTHON_DIR%
    goto :install_deps
)

echo     系统未安装 Python，正在下载嵌入式 Python %PYTHON_VER% ...
echo     下载地址: %PYTHON_URL%
echo.

:: 创建目录
if not exist "%BUILD_PYTHON_DIR%" mkdir "%BUILD_PYTHON_DIR%"

:: 下载
if not exist "%SCRIPT_DIR%%PYTHON_ZIP%" (
    powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%SCRIPT_DIR%%PYTHON_ZIP%' -UseBasicParsing"
    if errorlevel 1 (
        echo [错误] Python 下载失败！请检查网络连接。
        echo 你也可以手动下载 %PYTHON_URL% 到 %SCRIPT_DIR%
        pause
        exit /b 1
    )
)

echo     解压中...
powershell -Command "Expand-Archive -Path '%SCRIPT_DIR%%PYTHON_ZIP%' -DestinationPath '%BUILD_PYTHON_DIR%' -Force"
if errorlevel 1 (
    echo [错误] 解压失败！
    pause
    exit /b 1
)

:: 修改 ._pth 文件以启用 import site
echo     配置 Python 环境...
for %%f in ("%BUILD_PYTHON_DIR%\python*._pth") do (
    powershell -Command "(Get-Content '%%f') -replace '#import site','import site' | Set-Content '%%f'"
)

:: 安装 pip
echo     安装 pip...
powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%BUILD_PYTHON_DIR%\get-pip.py' -UseBasicParsing"
"%PYTHON_EXE%" "%BUILD_PYTHON_DIR%\get-pip.py" --no-warn-script-location -q
if errorlevel 1 (
    echo [错误] pip 安装失败！
    pause
    exit /b 1
)
echo     Python %PYTHON_VER% 环境准备完成。
echo.

:: ========== 第2步: 安装依赖 ==========
:install_deps
echo [2/5] 安装项目依赖...
"%PYTHON_EXE%" -m pip install PyQt6>=6.5.0 dnspython>=2.4.0 requests>=2.31.0 pyinstaller>=6.0.0 --no-warn-script-location -q
if errorlevel 1 (
    echo [错误] 依赖安装失败，请检查网络连接。
    pause
    exit /b 1
)
echo     依赖安装完成。
echo.

:: ========== 第3步: 清理旧的构建 ==========
echo [3/5] 清理旧构建...
if exist "%SCRIPT_DIR%dist" rmdir /s /q "%SCRIPT_DIR%dist"
if exist "%SCRIPT_DIR%build" rmdir /s /q "%SCRIPT_DIR%build"
echo     完成。
echo.

:: ========== 第4步: PyInstaller 打包 ==========
echo [4/5] PyInstaller 打包中（单文件 exe）...
echo     这可能需要 3-8 分钟，请耐心等待...
echo.

"%PYTHON_EXE%" -m PyInstaller --noconfirm --clean "%SCRIPT_DIR%netprobe_build.spec"

if errorlevel 1 (
    echo.
    echo [错误] PyInstaller 打包失败！请查看上方错误信息。
    pause
    exit /b 1
)

:: 重命名为中文名称（避免 PyInstaller 直接使用中文名导致乱码）
if exist "%SCRIPT_DIR%dist\NetProbe.exe" (
    if exist "%SCRIPT_DIR%dist\%APP_NAME%.exe" del "%SCRIPT_DIR%dist\%APP_NAME%.exe"
    ren "%SCRIPT_DIR%dist\NetProbe.exe" "%APP_NAME%.exe"
)
echo.
echo     打包完成！
echo.

:: ========== 第5步: 清理并展示结果 ==========
echo [5/5] 清理临时文件...
if exist "%SCRIPT_DIR%build" rmdir /s /q "%SCRIPT_DIR%build"
echo     完成。
echo.

:: 显示结果
set EXE_PATH=%SCRIPT_DIR%dist\%APP_NAME%.exe
if exist "%EXE_PATH%" (
    for %%A in ("%EXE_PATH%") do set EXE_SIZE=%%~zA
    setlocal EnableDelayedExpansion
    set /a SIZE_MB=!EXE_SIZE! / 1048576
    echo ============================================================
    echo.
    echo   ✅ 构建成功！
    echo.
    echo   输出文件:  %EXE_PATH%
    echo   文件大小:  约 !SIZE_MB! MB
    echo.
    echo   使用方式:
    echo     直接双击 "%APP_NAME%.exe" 即可运行
    echo     无需安装 Python 或任何依赖！
    echo.
    echo   分发方式:
    echo     将 exe 文件发送给其他用户即可
    echo     （或压缩为 zip 文件再分发）
    echo.
    echo ============================================================
    endlocal

    :: 打开输出目录
    explorer "%SCRIPT_DIR%dist"
) else (
    echo [错误] 未找到输出文件，构建可能失败。
)

echo.
pause
