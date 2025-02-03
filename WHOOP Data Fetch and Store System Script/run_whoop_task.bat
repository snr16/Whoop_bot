@echo off
echo ======================================================
echo              🚀 WHOOP Data Fetch Script 🚀           
echo ======================================================
echo.

REM Activate the virtual environment
echo 🌐 Activating virtual environment...
call "D:\Gen AI Project\Whoop data store script\whoop_env\Scripts\activate"

REM Cool Starting Message
echo ✅ Environment activated successfully!
echo.

REM Start the script
echo 📊 Fetching and processing WHOOP data...
python "D:\Gen AI Project\Whoop data store script\whoop_fetch_and_store(local run).py"

REM Check Exit Code
IF %ERRORLEVEL% EQU 0 (
    echo 🎉 Process completed successfully!
) ELSE (
    echo ❌ An error occurred. Check logs for details.
)

REM Deactivate environment
echo 🔄 Deactivating environment...
deactivate

REM Completion Message
echo ======================================================
echo              🎯 All tasks have been completed!       
echo ======================================================
pause
