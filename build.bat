@echo off
REM ===================================================================
REM  Build the standalone .exe.
REM
REM  Needs:  pip install openpyxl pyinstaller
REM  Output: dist\IgG Concentration Builder.exe   (about 16 MB)
REM
REM  To publish:  copy that .exe over the one in the share folder that
REM  "Run IgG Concentration Builder.bat" points at.  Every PC picks the
REM  new version up on the next launch.
REM
REM  Bump __version__ in igg_conc_gui.py FIRST - it shows in the title
REM  bar and in the report, and it is how anyone tells which build they
REM  are running.
REM ===================================================================

cd /d "%~dp0"

python -m PyInstaller ^
  --onefile ^
  --windowed ^
  --name "IgG Concentration Builder" ^
  --exclude-module numpy ^
  --exclude-module pandas ^
  --exclude-module matplotlib ^
  --exclude-module PyQt5 ^
  --exclude-module scipy ^
  --hidden-import plate_run ^
  --hidden-import store ^
  --hidden-import layout_colours ^
  --noconfirm --clean ^
  igg_conc_gui.py

if errorlevel 1 (
  echo.
  echo BUILD FAILED.
  pause
  exit /b 1
)

echo.
echo Built: dist\IgG Concentration Builder.exe
echo.
pause
