@echo off
REM Builds dist\MaaS-GUI.exe, a single file that runs without Python installed.
setlocal
cd /d "%~dp0"

if exist venv\Scripts\python.exe (
    set PY=venv\Scripts\python.exe
) else (
    set PY=python
)

%PY% -m pip install -r requirements.txt -r requirements-build.txt || exit /b 1
%PY% -m PyInstaller --noconfirm --clean maas_gui.spec || exit /b 1

echo.
echo Built: %CD%\dist\MaaS-GUI.exe
