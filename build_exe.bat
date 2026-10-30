@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run install.bat first.
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements-build.txt
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -c "import shutil; from pathlib import Path; shutil.rmtree(Path('dist') / 'NexusClicker', ignore_errors=True)"
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --name NexusClicker --add-data "extension;extension" --hidden-import pywinauto --hidden-import comtypes --hidden-import win32com.client --hidden-import win32timezone app.py
if errorlevel 1 exit /b 1
echo.
echo Build complete: dist\NexusClicker.exe
echo For a release, see the files described in README.md.
