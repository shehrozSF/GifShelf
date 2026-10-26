@echo off
rem Builds dist\GifShelf\ (the app) and dist\GifShelf-<version>-setup.exe (the installer).
rem build.bat              both
rem build.bat app          only the app (CI signs it before building the installer)
rem build.bat installer    only the installer, from whatever is in dist\GifShelf\
rem Needs: .venv and, for the installer, Inno Setup 6
rem winget install JRSoftware.InnoSetup
setlocal
cd /d "%~dp0"

set "STAGE=%~1"
if "%STAGE%"=="" set "STAGE=all"

set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" (
    echo No .venv found. Run venv.bat first. 1>&2
    exit /b 1
)

echo Installing build dependencies...
"%PY%" -m pip install -q -r requirements.txt -r requirements-build.txt || exit /b 1

rem PY is relative (no spaces), so it's left unquoted: for /f mangles nested quotes.
for /f "delims=" %%v in ('%PY% -c "import app; print(app.__version__)"') do set "VERSION=%%v"
for /f "delims=" %%v in ('%PY% -c "import app; print(app.__copyright__)"') do set "COPYRIGHT=%%v"

if /i "%STAGE%"=="installer" goto installer

echo Building GifShelf %VERSION%...
"%PY%" installer\version_info.py >nul || exit /b 1
"%PY%" -m PyInstaller --noconfirm --clean --windowed ^
    --name GifShelf ^
    --icon assets\icon.ico ^
    --version-file build\version_info.txt ^
    --add-data "assets\icon.ico;assets" ^
    main.py || exit /b 1

rem Qt files a widgets-only, English-only app never loads (~27 MB):
rem software OpenGL fallback and Qt's UI translations.
del /q "dist\GifShelf\_internal\PySide6\opengl32sw.dll" 2>nul
rmdir /s /q "dist\GifShelf\_internal\PySide6\translations" 2>nul

if /i "%STAGE%"=="app" (
    echo Done: dist\GifShelf\
    exit /b 0
)

:installer
if not exist "dist\GifShelf\GifShelf.exe" (
    echo dist\GifShelf\GifShelf.exe not found. Build the app first. 1>&2
    exit /b 1
)

set "ISCC="
for %%p in (
    "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
    "%ProgramFiles%\Inno Setup 6\ISCC.exe"
    "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
) do if exist %%p set "ISCC=%%~p"

if not defined ISCC (
    echo.
    echo App built in dist\GifShelf\, but Inno Setup 6 wasn't found, so no installer.
    echo Install it with:  winget install JRSoftware.InnoSetup
    exit /b 0
)

"%ISCC%" /Q "/DAppVersion=%VERSION%" "/DAppCopyright=%COPYRIGHT%" installer\GifShelf.iss || exit /b 1
echo.
echo Done: dist\GifShelf-%VERSION%-setup.exe
