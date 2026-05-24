@echo off
chcp 65001 >nul
title 团队共享日程 - 启动服务

echo ============================================
echo       团队共享日程管理 - 一键启动
echo ============================================
echo.

cd /d "%~dp0"

REM 检查 GitHub 配置
if not exist .env (
    echo [提示] 未检测到 .env 文件，GitHub 云端存储未配置。
    echo         如需配置，请运行: python setup_github.py
    echo         未配置时将使用本地文件存储。
    echo.
)

REM 关掉旧进程
taskkill /f /im cloudflared.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo [1/2] 正在启动Flask应用...
start "Flask Server" /min py app.py
timeout /t 4 /nobreak >nul

echo [2/2] 正在创建公网隧道，请稍候约15秒...
echo.

REM 用PowerShell启动cloudflared并捕获URL
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$cf = '%~dp0cloudflared.exe';" ^
  "$logFile = '$env:TEMP\cf_tunnel.log';" ^
  "'' | Out-File $logFile -Encoding utf8;" ^
  "$proc = Start-Process -FilePath $cf -ArgumentList 'tunnel','--url','http://localhost:5000' -WindowStyle Minimized -RedirectStandardError $logFile -PassThru;" ^
  "Write-Host '  等待隧道建立...';" ^
  "$url = '';" ^
  "for($i=0;$i -lt 20;$i++){" ^
  "  Start-Sleep 2;" ^
  "  $content = Get-Content $logFile -Raw -ErrorAction SilentlyContinue;" ^
  "  if($content -match 'https://([a-z0-9\-]+\.trycloudflare\.com)'){" ^
  "    $url = $matches[0]; break" ^
  "  }" ^
  "};" ^
  "if($url){" ^
  "  Write-Host '';" ^
  "  Write-Host '============================================';" ^
  "  Write-Host '  服务已成功启动！' -ForegroundColor Green;" ^
  "  Write-Host '';" ^
  "  Write-Host '  今日公网地址:' -ForegroundColor Yellow;" ^
  "  Write-Host \"  $url\" -ForegroundColor Cyan;" ^
  "  Write-Host '';" ^
  "  Write-Host '  本机访问: http://localhost:5000';" ^
  "  Write-Host '============================================';" ^
  "  Write-Host '';" ^
  "  Write-Host '  地址已复制到剪贴板，直接粘贴发给团队成员即可。';" ^
  "  Set-Clipboard $url" ^
  "} else {" ^
  "  Write-Host '  未能自动获取地址，请打开 cloudflared 窗口查看 URL' -ForegroundColor Red" ^
  "}"

echo.
pause
