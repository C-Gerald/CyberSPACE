# CyberSPACE 可视化控制台
# 生成 dashboard.html 并用浏览器打开；默认每 5 秒自动刷新（实时模式）
#
# 用法:
#   .\scripts\dashboard.ps1                实时模式：生成 + 打开浏览器 + 每 5 秒刷新 + 打开操作窗口
#   .\scripts\dashboard.ps1 -Once          只生成并打开一次
#   .\scripts\dashboard.ps1 -Once -NoOpen  只生成（不打开任何窗口，供自动化使用）

param(
    [switch]$Once,
    [switch]$NoOpen
)

chcp 65001 | Out-Null
$env:PYTHONUTF8 = '1'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root

$py   = Join-Path $root '.venv\Scripts\python.exe'
$gen  = Join-Path $root 'tools\dashboard_build.py'
$html = Join-Path $root 'dashboard.html'

if (-not (Test-Path $py))  { Write-Output "找不到 Python：$py（请确认 .venv 目录存在）"; exit 1 }
if (-not (Test-Path $gen)) { Write-Output "找不到生成器：$gen"; exit 1 }

# 第一次生成
& $py $gen
if ($LASTEXITCODE -ne 0) {
    Write-Output ''
    Write-Output '生成失败：请查看上面的错误信息。'
    exit 1
}

if (-not $NoOpen) { Start-Process $html }

if ($Once) { exit 0 }

# 打开“操作窗口”：网页上复制的命令可直接在那里粘贴执行
if (-not $NoOpen) {
    $ops = Join-Path $root 'scripts\ops-window.ps1'
    if (Test-Path $ops) {
        Start-Process powershell.exe -ArgumentList @('-NoExit', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $ops) | Out-Null
    }
}

Write-Output ''
Write-Output '==================== CyberSPACE 控制台 ===================='
Write-Output '  浏览器窗口：dashboard.html（每 5 秒自动刷新）'
Write-Output '  “操作窗口”已打开：网页上点「复制」的命令，'
Write-Output '  直接到那里粘贴 + 回车执行。'
Write-Output ''
Write-Output '  停止控制台刷新：在本窗口按 Ctrl+C'
Write-Output '==========================================================='
Write-Output ''

while ($true) {
    Start-Sleep -Seconds 5
    $out = & $py $gen 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host ("[{0}] 生成失败：" -f (Get-Date -Format 'HH:mm:ss')) -ForegroundColor Red
        $out | Select-Object -Last 6 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkRed }
    }
    else {
        Write-Host ("[{0}] 已刷新" -f (Get-Date -Format 'HH:mm:ss'))
    }
}
