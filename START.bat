@echo off
setlocal
cd /d "%~dp0"
title CleanupTV - Khoi dong
echo.
echo   CleanupTV - Mo trinh huong dan tren may tinh
echo   Lan dau can Internet de tai cong cu portable.
echo.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\bootstrap.ps1"
if errorlevel 1 (
  echo.
  echo Khong khoi dong duoc. Xem loi phia tren va thu lai.
  pause
)
endlocal
