# CyberSPACE 操作窗口
# 把控制台网页（dashboard.html）上复制的命令粘贴到这里执行

chcp 65001 | Out-Null
$env:PYTHONUTF8 = '1'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root

Write-Host ''
Write-Host '  ⚡ CyberSPACE 操作窗口' -ForegroundColor Cyan
Write-Host '  --------------------------------------------------------------'
Write-Host ''
Write-Host '  说明：控制台默认已开启「一键运行」（点网页按钮自动执行）；' -ForegroundColor Gray
Write-Host '  本窗口是备用入口：点网页「复制」后回到这里粘贴（Ctrl+V），回车执行。' -ForegroundColor Gray
Write-Host ''
Write-Host '    启动模拟盘   .\scripts\dry-run.ps1                 （停止：Ctrl+C）' -ForegroundColor White
Write-Host '    运行回测     .\scripts\backtest.ps1                （15 分钟周期：加 -Timeframe 15m）' -ForegroundColor White
Write-Host '    更新数据     .\scripts\download-data.ps1' -ForegroundColor White
Write-Host ''
Write-Host '  当前目录：' -NoNewline -ForegroundColor Gray
Write-Host $root -ForegroundColor DarkGray
Write-Host ''
