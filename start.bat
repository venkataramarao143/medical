@echo off
echo ============================================
echo   MedAnnotate - Medical Annotation Platform
echo ============================================
echo.

REM Try finding Python in common locations
set PYTHON_CMD=

where python >nul 2>&1
if %ERRORLEVEL% == 0 (
    set PYTHON_CMD=python
    goto :found
)

where python3 >nul 2>&1
if %ERRORLEVEL% == 0 (
    set PYTHON_CMD=python3
    goto :found
)

if exist "C:\Python313\python.exe" (
    set PYTHON_CMD=C:\Python313\python.exe
    goto :found
)

if exist "C:\Python312\python.exe" (
    set PYTHON_CMD=C:\Python312\python.exe
    goto :found
)

if exist "C:\Python311\python.exe" (
    set PYTHON_CMD=C:\Python311\python.exe
    goto :found
)

echo ERROR: Python not found!
echo Please install Python 3.11+ from https://www.python.org/downloads/
echo Make sure to check "Add Python to PATH" during installation.
pause
exit /b 1

:found
echo Found Python: %PYTHON_CMD%
%PYTHON_CMD% --version
echo.

echo Installing dependencies...
%PYTHON_CMD% -m pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)
echo.

echo Make sure MongoDB is running on localhost:27017
echo.

echo Creating admin account...
timeout /t 2 /nobreak >nul
start /b %PYTHON_CMD% app.py
timeout /t 3 /nobreak >nul

echo Seeding admin user...
curl -s -X POST http://localhost:5000/api/admin/seed > nul 2>&1
echo.

echo ============================================
echo   Platform is running at:
echo   http://localhost:5000
echo.
echo   Admin login:
echo   Email:    admin@medannotate.com
echo   Password: Admin@1234
echo ============================================
echo.
echo Press Ctrl+C to stop the server.
pause
