@echo off
rem Ready or Not PvP: installs UE4SS and the mod into the game (host only).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer\install.ps1" %*
echo.
pause
