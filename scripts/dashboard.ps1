# CyberSPACE 可视化控制台
# 生成 dashboard.html 并用浏览器打开；默认每 5 秒自动刷新（实时模式）
# 支持「一键运行」：本窗口监听剪贴板 —— 网页上点「▶ 运行」按钮，自动执行对应脚本
#
# 用法:
#   .\scripts\dashboard.ps1                实时模式（推荐）：刷新 + 一键运行 + 操作窗口
#   .\scripts\dashboard.ps1 -NoAutoRun     实时模式，但关闭一键运行（按钮只复制命令，去操作窗口手动粘贴）
#   .\scripts\dashboard.ps1 -Once          只生成并打开一次（不刷新、不监听）
#   .\scripts\dashboard.ps1 -Once -NoOpen  只生成（不打开任何窗口，供自动化使用）

param(
    [switch]$Once,
    [switch]$NoOpen,
    [switch]$NoAutoRun
)

chcp 65001 | Out-Null
$env:PYTHONUTF8 = '1'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root

$py      = Join-Path $root '.venv\Scripts\python.exe'
$gen     = Join-Path $root 'tools\dashboard_build.py'
$html    = Join-Path $root 'dashboard.html'
$jobFile = Join-Path $root 'user_data\logs\dashboard_job.json'

if (-not (Test-Path $py))  { Write-Output "找不到 Python：$py（请确认 .venv 目录存在）"; exit 1 }
if (-not (Test-Path $gen)) { Write-Output "找不到生成器：$gen"; exit 1 }

$autoRun = -not ($NoAutoRun -or $Once)
$autorunArg = if ($autoRun) { '1' } else { '0' }

function Rebuild-Dashboard {
    $out = & $py $gen '--autorun' $autorunArg 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host ("[{0}] 生成失败：" -f (Get-Date -Format 'HH:mm:ss')) -ForegroundColor Red
        $out | Select-Object -Last 6 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkRed }
        return $false
    }
    return $true
}

function Write-JobState([string]$label) {
    $json = @{ label = $label; started = (Get-Date -Format 'HH:mm:ss') } | ConvertTo-Json -Compress
    [System.IO.File]::WriteAllText($jobFile, $json, (New-Object System.Text.UTF8Encoding($true)))
}
function Clear-JobState {
    Remove-Item $jobFile -Force -ErrorAction SilentlyContinue
}

function Test-BotRunning {
    $r = tasklist /FI "IMAGENAME eq freqtrade.exe" /FO CSV /NH 2>$null
    return [bool]($r | Select-String -SimpleMatch 'freqtrade.exe')
}

function Get-ClipText {
    try { $t = Get-Clipboard -Raw -ErrorAction Stop }
    catch { return '' }
    if ($null -eq $t) { return '' }
    return ((($t -replace '\s+', ' ')).Trim())
}

# 只认识下面这几条内置命令，其它剪贴板内容一律忽略
function Resolve-CyberCommand([string]$t) {
    if (-not $t) { return $null }
    if ($t -match '^(?:\.\\)?scripts\\dry-run\.ps1$') {
        return @{ Key = 'dryrun'; Label = '启动模拟盘'; Kind = 'spawn' }
    }
    if ($t -match '^(?:\.\\)?scripts\\backtest\.ps1(?: -timeframe (5m|15m|1h))?$') {
        $tf = $Matches[1]
        if (-not $tf) { $tf = '5m' }
        return @{ Key = "backtest-$tf"; Label = "回测 $tf"; Kind = 'script'; ScriptName = 'backtest.ps1'; Timeframe = $tf }
    }
    if ($t -match '^(?:\.\\)?scripts\\download-data\.ps1$') {
        return @{ Key = 'download'; Label = '更新数据'; Kind = 'script'; ScriptName = 'download-data.ps1' }
    }
    if ($t -match '^(?:\.\\)?scripts\\dashboard\.ps1 -once$') {
        return @{ Key = 'regen'; Label = '刷新面板'; Kind = 'regen' }
    }
    if ($t -match '^taskkill /im freqtrade\.exe /f$') {
        return @{ Key = 'kill'; Label = '强制停止机器人'; Kind = 'kill' }
    }
    return $null
}

function Invoke-CyberCommand($cmd) {
    switch ($cmd.Kind) {
        'spawn' {
            if (Test-BotRunning) {
                Write-Host '⚠ 已有 freqtrade 在运行，已忽略「启动模拟盘」（避免双开同一个数据库）' -ForegroundColor Yellow
                try { [Console]::Beep(600, 250) } catch { }
                return
            }
            Write-Host '▶ 启动模拟盘：正在打开新窗口……（停止：在机器人窗口按 Ctrl+C）' -ForegroundColor Green
            Start-Process powershell.exe -ArgumentList @('-NoExit', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $root 'scripts\dry-run.ps1')) | Out-Null
        }
        'script' {
            Write-JobState $cmd.Label
            Write-Host ("▶ 开始执行：{0}（{1}）" -f $cmd.Label, (Get-Date -Format 'HH:mm:ss')) -ForegroundColor Green
            Rebuild-Dashboard | Out-Null
            try {
                if ($cmd.ScriptName -eq 'backtest.ps1') {
                    & (Join-Path $root 'scripts\backtest.ps1') -Timeframe $cmd.Timeframe
                }
                else {
                    & (Join-Path $root ('scripts\' + $cmd.ScriptName))
                }
            }
            finally {
                Clear-JobState
            }
            Write-Host ("■ 执行结束（退出码 {0}），页面马上刷新" -f $LASTEXITCODE) -ForegroundColor Green
        }
        'kill' {
            Write-Host '▶ 强制停止机器人……' -ForegroundColor Green
            & taskkill /IM freqtrade.exe /F
        }
        'regen' {
            Write-Host '▶ 立即重新生成面板' -ForegroundColor Green
        }
    }
    Rebuild-Dashboard | Out-Null
}

# 第一次生成
$first = & $py $gen '--autorun' $autorunArg 2>&1
if ($LASTEXITCODE -ne 0) {
    $first | ForEach-Object { Write-Output $_ }
    Write-Output ''
    Write-Output '生成失败：请查看上面的错误信息。'
    exit 1
}
$first | ForEach-Object { Write-Output $_ }

if (-not $NoOpen) { Start-Process $html }

if ($Once) { exit 0 }

# 打开「操作窗口」（手动执行的备用入口）
if (-not $NoOpen) {
    $ops = Join-Path $root 'scripts\ops-window.ps1'
    if (Test-Path $ops) {
        Start-Process powershell.exe -ArgumentList @('-NoExit', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $ops) | Out-Null
    }
}

Write-Output ''
Write-Output '==================== CyberSPACE 控制台 ===================='
Write-Output '  浏览器窗口：dashboard.html（每 5 秒自动刷新）'
if ($autoRun) {
    Write-Output '  一键运行：已开启 —— 网页上点「▶ 运行」，本窗口自动执行'
    Write-Output '  （原理：按钮把命令复制到剪贴板，本窗口监听并执行；只认内置的几条命令）'
}
else {
    Write-Output '  一键运行：已关闭（-NoAutoRun）—— 网页按钮只复制命令，'
    Write-Output '  请到“操作窗口”粘贴 + 回车执行'
}
Write-Output ''
Write-Output '  停止控制台：在本窗口按 Ctrl+C'
Write-Output '==========================================================='
Write-Output ''

$lastSeen  = Get-ClipText
$lastRunKey = ''
$lastRunAt = [datetime]::MinValue
$lastBuild = [datetime]::Now

while ($true) {
    Start-Sleep -Milliseconds 1200

    # 1) 一键运行：监听剪贴板
    if ($autoRun) {
        $cur = Get-ClipText
        if ($cur -ne $lastSeen) {
            $lastSeen = $cur
            $cmd = Resolve-CyberCommand $cur
            if ($cmd) {
                $cooldownOk = ($cmd.Key -ne $lastRunKey) -or ((([datetime]::Now) - $lastRunAt).TotalSeconds -ge 120)
                if ($cooldownOk) {
                    $lastRunKey = $cmd.Key
                    $lastRunAt = [datetime]::Now
                    Set-Clipboard ' ' -ErrorAction SilentlyContinue
                    Invoke-CyberCommand $cmd
                    $lastSeen = Get-ClipText
                    $lastBuild = [datetime]::Now
                }
                else {
                    Write-Host ('（已忽略：120 秒内重复的相同指令 ——「{0}」，如需再跑请稍后再点一次）' -f $cmd.Label) -ForegroundColor DarkYellow
                    Set-Clipboard ' ' -ErrorAction SilentlyContinue
                    $lastSeen = Get-ClipText
                }
            }
        }
    }

    # 2) 定时刷新（每 5 秒）
    if ((([datetime]::Now) - $lastBuild).TotalSeconds -ge 5) {
        if (Rebuild-Dashboard) {
            Write-Host ("[{0}] 已刷新" -f (Get-Date -Format 'HH:mm:ss'))
        }
        $lastBuild = [datetime]::Now
    }
}
