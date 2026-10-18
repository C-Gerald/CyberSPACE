# 模拟盘（dry-run）：不花一分钱，模拟成交
# 停止：按 Ctrl+C
#
# 实盘提示（确认模拟盘跑足时间后再做）：
#   1) config.json 的 exchange 里填入 API Key（只开交易权限，禁止提现）
#   2) "dry_run": true 改为 false
#   3) 把 stake_amount 降到极小金额试水

chcp 65001 | Out-Null
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
Set-Location (Join-Path $PSScriptRoot '..')

# 日志同时写入 user_data/logs/trade.log（控制台仪表盘的“运行日志”框读取它）
& './.venv/Scripts/freqtrade.exe' trade --config config.json --strategy EmaCrossStrategy --logfile user_data/logs/trade.log
exit $LASTEXITCODE
