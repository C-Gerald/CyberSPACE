# 回测脚本
# 用法：
#   ./scripts/backtest.ps1                  # 默认策略周期 5m（约 25 天数据）
#   ./scripts/backtest.ps1 -Timeframe 15m   # 15m（约 90 天数据）
#   ./scripts/backtest.ps1 -Timeframe 1h    # 1h（约 180 天数据）
#
# 说明：不设 ErrorActionPreference=Stop —— freqtrade 日志写 stderr，
#       PowerShell 5.1 会把它当成错误记录导致脚本被误杀；这里改为检查退出码。
param(
    [string]$Strategy = 'EmaCrossStrategy',
    [string]$Timeframe = ''
)

chcp 65001 | Out-Null
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
Set-Location (Join-Path $PSScriptRoot '..')

$ftArgs = @('backtesting', '--config', 'config.json', '--strategy', $Strategy)
if ($Timeframe) { $ftArgs += @('--timeframe', $Timeframe) }

& './.venv/Scripts/freqtrade.exe' @ftArgs
exit $LASTEXITCODE
