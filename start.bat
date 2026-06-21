@echo off
chcp 65001 >nul
title IEA 本地版 - IstinaEndfieldAssistant Sight

cd /d "%~dp0"

echo ========================================
echo IEA 本地版启动脚本
echo ========================================
echo.

:: 检查 Python 环境
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

echo [信息] Python 环境检测通过
echo.

:: 检查配置文件
if not exist "config\client_config.json" (
    echo [警告] 配置文件不存在，使用默认配置
)

:: 启动 GUI
echo [启动] 启动 IEA 本地版 GUI...
echo.

python src/gui/pyqt6/main.py

if errorlevel 1 (
    echo.
    echo [错误] GUI 启动失败
    pause
    exit /b 1
)
