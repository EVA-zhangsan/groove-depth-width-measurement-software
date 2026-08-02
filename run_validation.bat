@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" validate_stage5.py
) else (
  python validate_stage5.py
)
pause
