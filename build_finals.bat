@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ========================================
echo 槽型深度宽度测量软件 - 决赛现场版构建
echo ========================================

if not exist ".venv\Scripts\python.exe" (
  echo [1/6] 创建虚拟环境...
  py -3.10 -m venv .venv
)

set PY=.venv\Scripts\python.exe

echo [2/6] 升级 pip...
"%PY%" -m pip install --upgrade pip

echo [3/6] 安装运行依赖与 PyInstaller...
"%PY%" -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :fail

echo [4/6] 运行 Stage5 自检...
"%PY%" validate_stage5.py
if errorlevel 1 goto :fail

echo [5/6] 清理旧构建...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

mkdir finals_assets 2>nul
mkdir finals_assets\demo_backup 2>nul

copy /y "samples\raw_laser_demo\*" "finals_assets\demo_backup\" >nul 2>nul

echo [6/6] 构建无终端 onedir 版本...
"%PY%" -m PyInstaller --clean --noconfirm finals.spec
if errorlevel 1 goto :fail

if exist "dist\槽型深度宽度测量软件" (
  copy /y "README_FINALS.md" "dist\槽型深度宽度测量软件\请先看我.txt" >nul 2>nul
  if exist "docs" xcopy /e /i /y "docs" "dist\槽型深度宽度测量软件\docs" >nul
  if exist "samples" xcopy /e /i /y "samples" "dist\槽型深度宽度测量软件\samples" >nul
  if exist "finals_assets" xcopy /e /i /y "finals_assets" "dist\槽型深度宽度测量软件\finals_assets" >nul
)

echo.
echo 构建完成：dist\槽型深度宽度测量软件\槽型深度宽度测量软件.exe
echo 请复制整个“槽型深度宽度测量软件”文件夹，不要只复制 exe。
pause
exit /b 0

:fail
echo.
echo 构建失败，请查看上方错误信息。
pause
exit /b 1
