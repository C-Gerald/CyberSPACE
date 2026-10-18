# 下载三个周期的历史数据（含 Gate.io 限制的适配）
#
# Gate.io 蜡烛图限制：每周期最多取最近 10000 根 K 线
#   5m  ≈ 34 天  -> 取 25 天
#   15m ≈ 104 天 -> 取 90 天
#   1h  ≈ 416 天 -> 取 180 天
#
# 注意：已存在的数据文件默认只补最新一段；
#       想全量重下请先删除 user_data/data/gate 下的对应文件。
#
# 说明：不设 ErrorActionPreference=Stop —— freqtrade 日志写 stderr，
#       PowerShell 5.1 会把它当成错误记录导致脚本被误杀；这里改为检查退出码。

chcp 65001 | Out-Null
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
Set-Location (Join-Path $PSScriptRoot '..')

$ft = './.venv/Scripts/freqtrade.exe'
$pairs = @('BTC/USDT', 'ETH/USDT')

& $ft download-data --config config.json --pairs @pairs --timeframes 5m  --days 25
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $ft download-data --config config.json --pairs @pairs --timeframes 15m --days 90
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $ft download-data --config config.json --pairs @pairs --timeframes 1h  --days 180
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Output ""
Write-Output "数据文件："
Get-ChildItem user_data/data/gate -File | Select-Object Name, Length | Format-Table -AutoSize
exit 0
