@echo off
cd /d "%~dp0"

echo.
echo ========================================
echo   Autonomous Coding Agent
echo ========================================
echo.

REM Check if Claude CLI is installed
where claude >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Claude CLI not found
    echo.
    echo Please install Claude CLI first:
    echo   https://claude.ai/download
    echo.
    echo Then run this script again.
    echo.
    pause
    exit /b 1
)

echo [OK] Claude CLI found

REM Check if user has credentials (check for ~/.claude/.credentials.json)
set "CLAUDE_CREDS=%USERPROFILE%\.claude\.credentials.json"
if exist "%CLAUDE_CREDS%" (
    echo [OK] Claude credentials found
    goto :setup_venv
)

REM No credentials - prompt user to login
echo [!] Not authenticated with Claude
echo.
echo You need to run 'claude login' to authenticate.
echo This will open a browser window to sign in.
echo.
set /p "LOGIN_CHOICE=Would you like to run 'claude login' now? (y/n): "

if /i "%LOGIN_CHOICE%"=="y" (
    echo.
    echo Running 'claude login'...
    echo Complete the login in your browser, then return here.
    echo.
    call claude login

    REM Check if login succeeded
    if exist "%CLAUDE_CREDS%" (
        echo.
        echo [OK] Login successful!
        goto :setup_venv
    ) else (
        echo.
        echo [ERROR] Login failed or was cancelled.
        echo Please try again.
        pause
        exit /b 1
    )
) else (
    echo.
    echo Please run 'claude login' manually, then try again.
    pause
    exit /b 1
)

:setup_venv
echo.

REM Check if venv exists, create if not
if not exist "venv\Scripts\activate.bat" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate the virtual environment
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt --quiet

REM Run the app
python start.py
