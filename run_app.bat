@echo off
echo ================================================
echo   Indian Company Financial Comparator
echo ================================================
echo.

REM ── Step 1: Confirm Python is available ─────────────────────────────────────
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python was not found.
    echo Please install Python from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo Python found:
python --version
echo.

REM ── Step 2: Install required packages ───────────────────────────────────────
REM Using "python -m pip" is more reliable than calling "pip" directly on Windows.
echo Installing / verifying dependencies...
python -m pip install streamlit pandas openpyxl matplotlib pdfplumber --quiet
REM pdfplumber is needed for reading PDF files

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Failed to install one or more packages.
    echo Try running this command manually:
    echo   python -m pip install streamlit pandas openpyxl matplotlib
    pause
    exit /b 1
)

echo Dependencies are ready.
echo.

REM ── Step 3: Launch the Streamlit app ────────────────────────────────────────
REM Using "python -m streamlit" is more reliable than calling "streamlit" directly.
echo Starting the app — your browser will open automatically...
echo (Press Ctrl+C in this window to stop the app)
echo.

python -m streamlit run app.py

REM ── If we reach here, the app has stopped ────────────────────────────────────
echo.
echo App stopped.
pause
