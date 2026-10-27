@echo off
rem Ready or Not PvP: removes the mod (and the UE4SS it installed, unless other mods use it).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer\uninstall.ps1" %*
echo.
pause
