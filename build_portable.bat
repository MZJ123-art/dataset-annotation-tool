@echo off
rem ============================================================
rem  Dataset Annotation Tool - portable build script
rem
rem  NOTE: this file is intentionally ASCII-only and must keep
rem  CRLF line endings (.gitattributes enforces that). Chinese
rem  literals in a .bat get mangled by the console code page,
rem  so all non-ASCII names (folder / exe / spec) are resolved
rem  at runtime instead of being hard-coded here.
rem
rem  Optional environment variables:
rem    PY       - python interpreter to use
rem    APP_DIR  - deploy folder (default: Desktop\<exe name>)
rem ============================================================
setlocal

set "PROJ=%~dp0"
if "%PROJ:~-1%"=="\" set "PROJ=%PROJ:~0,-1%"

rem ---------- locate python ----------
if not defined PY (
    if exist "%PROJ%\..\..\venv-dataset-tool-cpu\Scripts\python.exe" (
        set "PY=%PROJ%\..\..\venv-dataset-tool-cpu\Scripts\python.exe"
    ) else (
        set "PY=python"
    )
)

rem ---------- locate the .spec file (its name may be non-ASCII) ----------
set "SPEC="
for %%f in ("%PROJ%\*.spec") do if not defined SPEC set "SPEC=%%~ff"
if not defined SPEC (
    echo [ERROR] No .spec file found in: %PROJ%
    goto :fail
)

echo ============================================
echo   Dataset Annotation Tool - portable build
echo ============================================
echo.
echo [1/4] Building with PyInstaller ...
echo       python : %PY%
echo       spec   : %SPEC%
echo.
pushd "%PROJ%"
"%PY%" -m PyInstaller --noconfirm --clean --distpath "%PROJ%\dist" --workpath "%PROJ%\build" "%SPEC%"
if errorlevel 1 (
    popd
    echo.
    echo [ERROR] PyInstaller build failed.
    goto :fail
)
popd

rem ---------- locate the built exe ----------
set "BUILT="
set "EXE_PATH="
set "EXE_NAME="
for /d %%d in ("%PROJ%\dist\*") do (
    for %%f in ("%%~fd\*.exe") do (
        set "BUILT=%%~fd"
        set "EXE_PATH=%%~ff"
        set "EXE_NAME=%%~nxf"
    )
)
if not defined EXE_PATH (
    echo [ERROR] Build output not found under: %PROJ%\dist
    goto :fail
)
for %%f in ("%EXE_PATH%") do set "EXE_BASE=%%~nf"

rem ---------- deploy ----------
if not defined APP_DIR set "APP_DIR=%USERPROFILE%\Desktop\%EXE_BASE%"
echo.
echo [2/4] Deploying to: %APP_DIR%
if not exist "%APP_DIR%" mkdir "%APP_DIR%" >nul 2>&1
taskkill /IM "%EXE_NAME%" /F >nul 2>&1
robocopy "%BUILT%" "%APP_DIR%" /MIR /NFL /NDL /NJH /NJS /R:1 /W:1 >nul
if errorlevel 8 (
    echo [ERROR] Deploy failed - the program may still be running.
    goto :fail
)

rem ---------- shortcuts (desktop + start menu), named after the exe ----------
echo.
echo [3/4] Creating shortcuts ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$app='%APP_DIR%'; $exe=(Get-ChildItem -LiteralPath $app -Filter *.exe)[0]; $name=[IO.Path]::GetFileNameWithoutExtension($exe.Name); $dir=Split-Path $exe.FullName; $ws=New-Object -ComObject WScript.Shell; $d=[Environment]::GetFolderPath('Desktop'); $s=$ws.CreateShortcut((Join-Path $d ($name+'.lnk'))); $s.TargetPath=$exe.FullName; $s.WorkingDirectory=$dir; $s.IconLocation=($exe.FullName+',0'); $s.Save(); $sm=Join-Path $env:APPDATA ('Microsoft\Windows\Start Menu\Programs\'+$name); $null=New-Item -ItemType Directory -Path $sm -Force; $t=$ws.CreateShortcut((Join-Path $sm ($name+'.lnk'))); $t.TargetPath=$exe.FullName; $t.WorkingDirectory=$dir; $t.Save(); Write-Host ('  shortcut: '+(Join-Path $d ($name+'.lnk')))"
if errorlevel 1 echo [WARN] Shortcut creation failed - you can start the exe directly.

rem ---------- self test ----------
echo.
echo [4/4] Self test ...
del "%TEMP%\dataset_tool_selftest.txt" >nul 2>&1
"%APP_DIR%\%EXE_NAME%" --selftest
if errorlevel 1 (
    echo [ERROR] Self test failed - see %TEMP%\dataset_tool_selftest.txt
    goto :fail
)
if exist "%TEMP%\dataset_tool_selftest.txt" type "%TEMP%\dataset_tool_selftest.txt"

echo.
echo ============================================
echo   Done. App folder: %APP_DIR%
echo ============================================
pause
exit /b 0

:fail
echo.
pause
exit /b 1
