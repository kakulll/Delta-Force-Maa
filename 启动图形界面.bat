@echo off
chcp 65001 >nul
title 三角洲行动 Maa - 官方图形界面 (MFAAvalonia)

set "APP_DIR=%~dp0"
set "MFA_DIR=%APP_DIR%.create-maa-project\runtime\mfaa\win-x64"
set "MFA_EXE=%MFA_DIR%\MFAAvalonia.exe"

if not exist "%MFA_EXE%" (
    echo [错误] 未找到 MFAAvalonia.exe
    pause
    exit /b 1
)

echo 正在检查并清理可能残留的 MFA 后台进程...
taskkill /F /IM MFAAvalonia.exe >nul 2>&1

echo 正在启动 三角洲行动 Maa 桌面图形客户端...
cd /d "%MFA_DIR%"
start "" "%MFA_EXE%"
exit /b 0

