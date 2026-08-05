@echo off
setlocal

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\windows\Start-LiveClip.ps1"
set "LIVECLIP_EXIT_CODE=%ERRORLEVEL%"

if not "%LIVECLIP_EXIT_CODE%"=="0" (
    echo.
    echo LiveClip failed. Review the message above, then press any key to close.
    pause >nul
)

exit /b %LIVECLIP_EXIT_CODE%
