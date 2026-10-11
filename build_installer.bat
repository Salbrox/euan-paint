@echo off
rem Builds "dist\Euan Paint Setup.exe". Needs Inno Setup 6 (winget install JRSoftware.InnoSetup)
rem and "dist\Euan Paint.exe" from build_windows.bat.
setlocal
cd /d "%~dp0"

if not exist "dist\Euan Paint.exe" (
    echo dist\Euan Paint.exe is missing - run build_windows.bat first.
    pause
    exit /b 1
)
if not exist euan-paint-icon.ico (
    if not exist build-env (echo Run build_windows.bat first. & pause & exit /b 1)
    build-env\Scripts\python -c "from PIL import Image; Image.open('euan-paint-icon.png').save('euan-paint-icon.ico', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])" || goto :fail
)

set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
    echo Inno Setup 6 is not installed. Run: winget install JRSoftware.InnoSetup
    pause
    exit /b 1
)

"%ISCC%" installer.iss || goto :fail
echo.
echo Done! Your installer is in: dist\Euan Paint Setup.exe
pause
exit /b 0

:fail
echo.
echo Installer build failed - see the messages above.
pause
exit /b 1
