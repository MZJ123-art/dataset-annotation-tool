@echo off
chcp 65001 >nul
setlocal

echo ========================================
echo   数据集标注工具 - 构建便携版 ^(免安装^)
echo ========================================
echo.

:: 项目目录 = 本脚本所在目录
set "PROJ=%~dp0"
if "%PROJ:~-1%"=="\" set "PROJ=%PROJ:~0,-1%"

:: 输出目录：可用环境变量 APP_DIR 覆盖，默认放桌面下的“数据集标注工具”文件夹
if not defined APP_DIR set "APP_DIR=%USERPROFILE%\Desktop\数据集标注工具"
set "EXE=%APP_DIR%\数据集标注工具.exe"

:: Python 解释器：可用环境变量 PY 覆盖，默认先找项目旁的 CPU venv，再退回 PATH 里的 python
if not defined PY (
    set "PY=%PROJ%\..\..\venv-dataset-tool-cpu\Scripts\python.exe"
    if not exist "%PY%" set "PY=python"
)

echo [1/3] 用 PyInstaller 构建...
echo       解释器:   %PY%
echo       项目目录: %PROJ%
pushd "%PROJ%"
"%PY%" -m PyInstaller --noconfirm --clean --distpath "%PROJ%\dist" --workpath "%PROJ%\build" "数据集标注工具.spec"
if errorlevel 1 (
    echo.
    echo [错误] 构建失败
    popd
    pause
    exit /b 1
)
popd

if not exist "%PROJ%\dist\数据集标注工具\数据集标注工具.exe" (
    echo [错误] 未找到构建产物
    pause
    exit /b 1
)

echo.
echo [2/3] 部署到 %APP_DIR% ...
if exist "%EXE%" (
    taskkill /IM "数据集标注工具.exe" /F >nul 2>&1
    timeout /t 1 >nul
)
robocopy "%PROJ%\dist\数据集标注工具" "%APP_DIR%" /MIR /NFL /NDL /NJH /NJS /R:1 /W:1 >nul
if errorlevel 8 (
    echo [错误] 部署失败（程序可能正在运行）
    pause
    exit /b 1
)

echo.
echo [3/3] 刷新桌面/开始菜单快捷方式...
powershell -NoProfile -Command "$d=[Environment]::GetFolderPath('Desktop'); $ws=New-Object -ComObject WScript.Shell; $s=$ws.CreateShortcut((Join-Path $d '数据集标注工具.lnk')); $s.TargetPath='%EXE%'; $s.WorkingDirectory='%APP_DIR%'; $s.Description='数据集标注工具'; $s.IconLocation='%EXE%,0'; $s.Save(); $sm=Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\数据集标注工具'; New-Item -ItemType Directory -Path $sm -Force | Out-Null; $t=$ws.CreateShortcut((Join-Path $sm '数据集标注工具.lnk')); $t.TargetPath='%EXE%'; $t.WorkingDirectory='%APP_DIR%'; $t.Save()"

echo.
echo [自检] 验证界面能否完整构建...
"%EXE%" --selftest
if errorlevel 1 (
    echo [错误] 自检失败，详情见 %%TEMP%%\dataset_tool_selftest.txt
    pause
    exit /b 1
)
type "%TEMP%\dataset_tool_selftest.txt"

echo.
echo ========================================
echo   完成！
echo   程序目录: %APP_DIR%
echo   直接运行: %EXE%
echo ========================================
pause
