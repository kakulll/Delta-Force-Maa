@echo off
chcp 65001 >nul
title 三角洲行动 Maa - 官方图形界面 (MFAAvalonia)

set "APP_DIR=%~dp0"
set "MFA_EXE=%APP_DIR%.create-maa-project\runtime\mfaa\win-x64\MFAAvalonia.exe"

if not exist "%MFA_EXE%" (
    echo [错误] 未找到 MFAAvalonia.exe
    pause
    exit /b 1
)

echo 正在启动 三角洲行动 Maa 桌面图形客户端...
start "" "%MFA_EXE%"
exit /b 0

