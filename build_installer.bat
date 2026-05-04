@echo off
chcp 65001 >nul
echo ========================================
echo   数据集标注工具 - 安装包构建脚本
echo ========================================
echo.

:: 查找 Inno Setup 编译器
set "ISCC="
if exist "D:\Tool\Inno Setup 6\ISCC.exe" (
    set "ISCC=D:\Tool\Inno Setup 6\ISCC.exe"
)
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
)
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
)

if "%ISCC%"=="" (
    echo [错误] 未找到 Inno Setup 6
    echo.
    echo 请先下载安装 Inno Setup 6:
    echo   https://jrsoftware.org/isinfo.php
    echo.
    echo 安装完成后重新运行此脚本
    pause
    exit /b 1
)

echo [1/2] 正在编译安装包...
"%ISCC%" "D:\desktop\数据集标注\installer.iss"

if errorlevel 1 (
    echo.
    echo [错误] 编译失败
    pause
    exit /b 1
)

echo.
echo [2/2] 编译完成！
echo.
echo 安装包位置:
echo   D:\desktop\数据集标注\installer_output\数据集标注工具_安装包.exe
echo.
pause
