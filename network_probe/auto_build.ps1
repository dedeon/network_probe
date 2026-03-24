# 网络拨测工具 - 全自动构建 PowerShell 脚本
# 自动下载 Python + 安装依赖 + PyInstaller 打包成单文件 exe

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $SCRIPT_DIR

$PYTHON_VER = "3.11.9"
$PYTHON_ZIP = "python-$PYTHON_VER-embed-amd64.zip"
$PYTHON_URL = "https://www.python.org/ftp/python/$PYTHON_VER/$PYTHON_ZIP"
$BUILD_PYTHON_DIR = Join-Path $SCRIPT_DIR "_build_python"
$PYTHON_EXE = Join-Path $BUILD_PYTHON_DIR "python.exe"
$APP_NAME = "网络拨测工具"
$PARENT_DIR = Split-Path -Parent $SCRIPT_DIR

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  网络拨测工具 - 全自动构建脚本 (PowerShell)" -ForegroundColor Cyan
Write-Host "  目标: 生成 Windows 免安装单文件 exe" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ========== 第1步: 准备 Python 环境 ==========
Write-Host "[1/5] 准备 Python 环境..." -ForegroundColor Yellow

# 先检查系统是否已安装 Python
$systemPython = $null
try {
    $ver = & python --version 2>&1
    if ($LASTEXITCODE -eq 0 -and $ver -match "Python \d") {
        $systemPython = "python"
        Write-Host "     检测到系统 Python: $ver" -ForegroundColor Green
    }
} catch {}

if (-not $systemPython) {
    # 检查已下载的构建 Python
    if (Test-Path $PYTHON_EXE) {
        Write-Host "     使用已下载的构建 Python: $BUILD_PYTHON_DIR" -ForegroundColor Green
    } else {
        Write-Host "     系统未安装 Python，正在下载嵌入式 Python $PYTHON_VER ..." -ForegroundColor White

        if (-not (Test-Path $BUILD_PYTHON_DIR)) {
            New-Item -ItemType Directory -Path $BUILD_PYTHON_DIR -Force | Out-Null
        }

        $zipPath = Join-Path $SCRIPT_DIR $PYTHON_ZIP
        if (-not (Test-Path $zipPath)) {
            Write-Host "     下载中: $PYTHON_URL" -ForegroundColor White
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            try {
                Invoke-WebRequest -Uri $PYTHON_URL -OutFile $zipPath -UseBasicParsing
            } catch {
                Write-Host "[错误] Python 下载失败: $_" -ForegroundColor Red
                exit 1
            }
        }

        Write-Host "     解压中..." -ForegroundColor White
        Expand-Archive -Path $zipPath -DestinationPath $BUILD_PYTHON_DIR -Force

        # 修改 ._pth 文件以启用 import site
        Write-Host "     配置 Python 环境..." -ForegroundColor White
        Get-ChildItem -Path $BUILD_PYTHON_DIR -Filter "python*._pth" | ForEach-Object {
            $content = Get-Content $_.FullName
            $content = $content -replace '#import site', 'import site'
            Set-Content -Path $_.FullName -Value $content
        }

        # 安装 pip
        Write-Host "     安装 pip..." -ForegroundColor White
        $getPipUrl = "https://bootstrap.pypa.io/get-pip.py"
        $getPipPath = Join-Path $BUILD_PYTHON_DIR "get-pip.py"
        Invoke-WebRequest -Uri $getPipUrl -OutFile $getPipPath -UseBasicParsing
        & $PYTHON_EXE $getPipPath --no-warn-script-location -q 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[错误] pip 安装失败！" -ForegroundColor Red
            exit 1
        }

        Write-Host "     Python $PYTHON_VER 环境准备完成。" -ForegroundColor Green
    }
    $USE_PYTHON = $PYTHON_EXE
} else {
    $USE_PYTHON = $systemPython
}

Write-Host ""

# ========== 第2步: 安装依赖 ==========
Write-Host "[2/5] 安装项目依赖..." -ForegroundColor Yellow
& $USE_PYTHON -m pip install "PyQt6>=6.5.0" "dnspython>=2.4.0" "requests>=2.31.0" "pyinstaller>=6.0.0" --no-warn-script-location -q 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[错误] 依赖安装失败！" -ForegroundColor Red
    exit 1
}
Write-Host "     依赖安装完成。" -ForegroundColor Green
Write-Host ""

# ========== 第3步: 清理旧构建 ==========
Write-Host "[3/5] 清理旧构建..." -ForegroundColor Yellow
$distDir = Join-Path $SCRIPT_DIR "dist"
$buildDir = Join-Path $SCRIPT_DIR "build"
if (Test-Path $distDir) { Remove-Item $distDir -Recurse -Force }
if (Test-Path $buildDir) { Remove-Item $buildDir -Recurse -Force }
Write-Host "     完成。" -ForegroundColor Green
Write-Host ""

# ========== 第4步: PyInstaller 打包 ==========
Write-Host "[4/5] PyInstaller 打包中（单文件 exe）..." -ForegroundColor Yellow
Write-Host "     这可能需要 3-8 分钟，请耐心等待..." -ForegroundColor White
Write-Host ""

$specFile = Join-Path $SCRIPT_DIR "netprobe_build.spec"

& $USE_PYTHON -m PyInstaller --noconfirm --clean $specFile 2>&1 | ForEach-Object { Write-Host $_ }

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[错误] PyInstaller 打包失败！" -ForegroundColor Red
    exit 1
}

# 重命名为中文名称（避免 PyInstaller 直接使用中文名导致乱码）
$engExe = Join-Path $distDir "NetProbe.exe"
$chnExe = Join-Path $distDir "$APP_NAME.exe"
if (Test-Path $engExe) {
    if (Test-Path $chnExe) { Remove-Item $chnExe -Force }
    Rename-Item $engExe -NewName "$APP_NAME.exe"
}

Write-Host ""
Write-Host "     打包完成！" -ForegroundColor Green
Write-Host ""

# ========== 第5步: 清理并展示结果 ==========
Write-Host "[5/5] 清理临时文件..." -ForegroundColor Yellow
if (Test-Path $buildDir) { Remove-Item $buildDir -Recurse -Force -ErrorAction SilentlyContinue }
Write-Host "     完成。" -ForegroundColor Green
Write-Host ""

# 展示结果
$exePath = Join-Path $distDir "$APP_NAME.exe"
if (Test-Path $exePath) {
    $fileInfo = Get-Item $exePath
    $sizeMB = [math]::Round($fileInfo.Length / 1MB, 1)

    Write-Host "============================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  ✅ 构建成功！" -ForegroundColor Green
    Write-Host ""
    Write-Host "  输出文件:  $exePath" -ForegroundColor White
    Write-Host "  文件大小:  $sizeMB MB" -ForegroundColor White
    Write-Host ""
    Write-Host "  使用方式:" -ForegroundColor White
    Write-Host "    直接双击 '$APP_NAME.exe' 即可运行" -ForegroundColor White
    Write-Host "    无需安装 Python 或任何依赖！" -ForegroundColor White
    Write-Host ""
    Write-Host "  分发方式:" -ForegroundColor White
    Write-Host "    将 exe 文件发送给其他用户即可" -ForegroundColor White
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
} else {
    Write-Host "[错误] 未找到输出文件，构建可能失败。" -ForegroundColor Red
    exit 1
}
