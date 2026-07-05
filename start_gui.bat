@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

set "ROOT_DIR=%~dp0"
set "PYTHON=%ROOT_DIR%3rd-part\python\python.exe"
set "MAIN=%ROOT_DIR%src\gui\pyqt6\main.py"
set "PYTHONPATH=%ROOT_DIR%src;%PYTHONPATH%"

if not exist "%PYTHON%" (
    echo [ERROR] Bundled Python not found: %PYTHON%
    pause
    exit /b 1
)

if not exist "%MAIN%" (
    echo [ERROR] Entry script not found: %MAIN%
    pause
    exit /b 1
)

echo Starting IstinaEndfieldAssistant GUI...
"%PYTHON%" "%MAIN%"
set "EXITCODE=%ERRORLEVEL%"

if not "%EXITCODE%"=="0" (
    echo.
    echo [ERROR] Exited with code: %EXITCODE%
    pause
)

exit /b %EXITCODE%