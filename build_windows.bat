@echo off
rem Builds "dist\Euan Paint.exe". Run this once on a Windows PC that has Python 3
rem installed (https://www.python.org/downloads/, tick "Add python.exe to PATH").
setlocal
cd /d "%~dp0"

set "PY=python"
where py >nul 2>nul && set "PY=py -3"
%PY% --version >nul 2>nul || (
    echo Python 3 is not installed. Get it from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Setting up a private build environment...
if not exist build-env (%PY% -m venv build-env || goto :fail)
call build-env\Scripts\activate.bat || goto :fail
python -m pip install --upgrade pip >nul
python -m pip install pygame-ce numpy pyinstaller pillow || goto :fail

echo Making the icon...
python euan_paint.py --make-icon euan-paint-icon.png || goto :fail

echo Building the exe (this takes a minute or two)...
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name "Euan Paint" --icon euan-paint-icon.png euan_paint.py || goto :fail

echo.
echo Done! Your app is in: dist\Euan Paint.exe
echo Copy it anywhere, then right-click it to pin it to Start or the taskbar.
pause
exit /b 0

:fail
echo.
echo Build failed - see the messages above.
pause
exit /b 1
