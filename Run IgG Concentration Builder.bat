@echo off
REM ===================================================================
REM  IgG Concentration Builder - launcher
REM
REM  Copies the current version from the share to this PC, then runs it
REM  locally.  Colleagues make a desktop shortcut to THIS file, never to
REM  the .exe.  To publish an update, drop a new .exe in %SHARE% - every
REM  PC picks it up the next time someone launches.
REM
REM  Running locally rather than off the share means:
REM    - you can replace the .exe while colleagues have it open
REM    - it starts fast, and keeps working if the share is down
REM ===================================================================

REM ---- EDIT THIS ONE LINE: the folder holding the .exe on the share ----
set "SHARE=\\10.70.119.100\Glikobiologija\Python programs\IgG Concentration Builder"
REM ---------------------------------------------------------------------

set "APP=IgG Concentration Builder.exe"
set "LOCAL=%LOCALAPPDATA%\IgG Concentration Builder"

if not exist "%LOCAL%" mkdir "%LOCAL%" >nul 2>&1

REM robocopy copies only when the share version differs, so this is a
REM no-op on an ordinary launch.  /R:1 /W:1 = fail fast if share is down.
robocopy "%SHARE%" "%LOCAL%" "%APP%" /NJH /NJS /NP /NDL /NFL /R:1 /W:2 >nul 2>&1

REM robocopy exit codes below 8 are success (0 = already current, 1 = copied)
if errorlevel 8 (
  if exist "%LOCAL%\%APP%" (
    echo Could not reach the share - starting the copy already on this PC.
    REM ping, not timeout: timeout fails when input is redirected
    ping -n 3 127.0.0.1 >nul 2>&1
  ) else (
    echo.
    echo Could not reach:
    echo   %SHARE%
    echo.
    echo Check that you are on the network and can open that folder,
    echo then run this again.
    echo.
    pause
    exit /b 1
  )
)

if not exist "%LOCAL%\%APP%" (
  echo.
  echo "%APP%" was not found on the share.
  echo Check the SHARE path near the top of this file.
  echo.
  pause
  exit /b 1
)

start "" "%LOCAL%\%APP%"
exit /b 0
