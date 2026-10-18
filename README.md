# CyberSPACE

**个人加密量化系统 · freqtrade + Gate.io · 全免费 / 全开源方案**

在 Windows 上跑通「公共行情数据 → 历史回测 → 模拟盘（dry-run）→ 小资金实盘」全流程。所有工具免费开源：无月费、无订阅、无需服务器（将来也可迁到 VPS / Linux）。

> ⚠️ **免责声明**：本项目仅用于学习与研究，不构成任何投资建议。加密资产波动极大，中国大陆境内相关交易活动不受法律保护、出入金存在风险。实盘请自行评估风险并遵守当地法律法规，只用亏得起的资金，不借贷、不加杠杆。

---

## 当前状态

- [x] freqtrade 2026.9 + Python 3.11 虚拟环境（`.venv/`，不进仓库）
- [x] Gate.io 直连（行情 + 交易），无需代理（本机直连 Binance 被墙，因此选 Gate）
- [x] 历史数据下载就绪：BTC/ETH × 5m / 15m / 1h
- [x] 示例策略 `EmaCrossStrategy` + 一键脚本全流程跑通（下载 → 回测）
- [x] dry-run 模拟盘冒烟测试通过（RUNNING + heartbeat 正常）
- [ ] 策略验证过关 → 小资金实盘

## 目录结构

```
CyberSPACE/
├─ config.example.json      # 配置模板（复制为 config.json 后使用；config.json 不入库）
├─ requirements.txt         # Python 依赖（freqtrade==2026.9、py-spy）
├─ compat/
│  └─ sitecustomize.py      # Windows「回环 socketpair 卡死」兼容补丁（见下文）
├─ scripts/
│  ├─ download-data.ps1     # 一键下载 / 增量更新历史数据
│  ├─ backtest.ps1          # 一键回测（支持 -Timeframe 5m|15m|1h）
│  └─ dry-run.ps1           # 一键启动模拟盘（Ctrl+C 停止）
└─ user_data/
   ├─ strategies/
   │  └─ EmaCrossStrategy.py    # 示例策略：EMA 金叉死叉 + RSI 过滤
   ├─ data/                # 历史数据（不入库，换机重新下载）
   ├─ logs/                # 运行日志（不入库）
   └─ backtest_results/    # 回测结果（不入库）
```

## 快速开始（本机已就绪）

在项目根目录打开 PowerShell：

```powershell
# 首次使用如提示「禁止运行脚本」（Windows 默认策略），先一次性放行
# （原因、撤销方法与替代方案见「故障排查」一节）
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

.\scripts\download-data.ps1   # 下载 / 增量更新数据（可反复运行）
.\scripts\backtest.ps1        # 回测默认 5m（约 25 天数据）
.\scripts\dry-run.ps1         # 启动模拟盘（Ctrl+C 停止）
```

## 从零部署（新机器 / 克隆本仓库后）

1. 安装 **Python 3.11+**（本项目在 3.11.4 上验证）。
2. 克隆、建虚拟环境、装依赖：

```powershell
git clone https://github.com/C-Gerald/CyberSPACE.git
cd CyberSPACE
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

3. 【Windows 建议做】部署兼容补丁（原因见下文「Windows 兼容补丁」一节）：

```powershell
Copy-Item compat\sitecustomize.py .venv\Lib\site-packages\sitecustomize.py -Force
```

4. 生成配置（默认 dry-run 模拟盘，无需 API Key）：

```powershell
Copy-Item config.example.json config.json
```

5. 【首次运行脚本前】如提示「禁止运行脚本」，先一次性放行（原因与撤销方法见「故障排查」）：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

6. 下载数据 → 回测 → 模拟盘：

```powershell
.\scripts\download-data.ps1
.\scripts\backtest.ps1
.\scripts\dry-run.ps1
```

## 示例策略 EmaCrossStrategy

- 周期：5m（回测时可用 `-Timeframe` 覆盖），只做多（现货）
- 入场：EMA12 上穿 EMA48（金叉）且 RSI14 < 70（避免追高）
- 出场：EMA12 下穿 EMA48（死叉）；另有止盈 `+5%` / 止损 `-3%`
- 交易对：BTC/USDT、ETH/USDT；最多同时 3 仓（`config.json` 可调）
- 代码：`user_data/strategies/EmaCrossStrategy.py`——**教学示例，不是盈利策略**

## 回测结果（学费记录）

同一数据区间：2026-09-23 ～ 2026-10-18（约 25 天），BTC/ETH；手续费按交易所最坏情况 **单边 0.2%** 计：

| 周期 | 交易数 | 总收益 | 胜 / 负 | 胜率 | 平均持仓 |
|------|-------|--------|---------|------|----------|
| 5m  | 199 | **-9.53%** | 17 / 182 | 8.5%  | 2 小时 57 分 |
| 15m | 72  | **-4.83%** | 7 / 65   | 9.7%  | 7 小时 14 分 |

（另：15m 在约 90 天的更长区间上回测同样为负：约 -9.6%，230 笔。）

**结论与教训**：

1. **手续费是短线策略的隐形杀手**：现货单边 0.2%，一进一出 0.4%；平均持仓越短，手续费在盈亏里的占比越高。
2. 该示例策略期望为负，**仅用于验证全流程**，不要直接拿去实盘。先把交易频率降下来、信号做得更「挑剔」，并且始终把手续费计入回测。

## 数据与交易所说明

- **为什么选 Gate.io**：本机直连可用（行情 + 交易），公共数据下载无门槛、免费。
- **Gate K 线限制**：单次最多返回 10000 根 → 本项目各周期取数上限：

  | 周期 | 理论最长跨度 | 本项目下载 |
  |------|------------|-----------|
  | 5m  | ≈ 34 天 | 25 天 |
  | 15m | ≈ 104 天 | 90 天 |
  | 1h  | ≈ 416 天 | 180 天 |

- 数据保存在 `user_data/data/gate/`（`.gitignore` 已排除；换机重新下载即可）。
- 配置要点（`config.example.json` 里已处理好）：
  - `entry_pricing` / `exit_pricing`：freqtrade 2026.9 必填项；
  - `fiat_display_currency: ""`：避免免费汇率接口报错刷屏；
  - ccxt 超时 30 秒 + `fetchMarkets` 限定现货，避免连接过期合约市场。

## ⚠️ Windows 兼容补丁（sitecustomize）——重要

**症状**：freqtrade 启动后无规律卡死（尤其 dry-run），CPU 占用很低；偶发 `WinError 10048`。

**原因**：本机安全软件（火绒）会拦截 TCP 回环连接。而 Python 在 Windows 上用「TCP listen + connect + accept」模拟 `socket.socketpair()`（asyncio 事件循环的「自管道」），回环被拦时 `accept()` 会永久卡住。

**修复**：`compat/sitecustomize.py` 把 socketpair 替换成 **UDP 版实现**（UDP 无握手、无 accept，不会被同样方式卡住），复制进 venv 即可：

```powershell
Copy-Item compat\sitecustomize.py .venv\Lib\site-packages\sitecustomize.py -Force
```

> - 重新创建 / 重装 venv 后，必须重新复制一次。
> - 更彻底的解法：把项目目录加入杀软的「信任区」；此补丁作为双保险。

## 实盘步骤（确认策略验证过关后再执行）

1. 在 Gate.io 创建 **现货 API Key**：只勾选现货交易权限，**务必不要勾选提现权限**；建议使用子账户。
2. 将 Key / Secret 填入 `config.json` 的 `exchange.key` / `exchange.secret`。
3. 先保持 `"dry_run": true` 观察 1–2 周；确认无误后改为 `false`，并先把 `stake_amount` 调小（如 10 USDT）试水。
4. 启动：

   ```powershell
   .\.venv\Scripts\freqtrade.exe trade --config config.json --strategy EmaCrossStrategy
   ```

5. 长期挂机可用 Windows 计划任务或 VPS；上线前务必在 dry-run 跑够时间。

## 常用命令速查

```powershell
# 回测（切换周期）
.\scripts\backtest.ps1                  # 默认 5m
.\scripts\backtest.ps1 -Timeframe 15m   # 15m
.\scripts\backtest.ps1 -Timeframe 1h    # 1h

# 数据与结果
.\scripts\download-data.ps1             # 下载 / 增量更新（可反复运行）
.\.venv\Scripts\freqtrade.exe list-data --config config.json
.\.venv\Scripts\freqtrade.exe backtesting-show --config config.json   # 查看上次回测明细

# 模拟盘
.\scripts\dry-run.ps1                   # Ctrl+C 停止
```

> PowerShell 5.1 中文乱码：先执行 `chcp 65001`；`.ps1` 脚本请保持 **UTF-8 带 BOM** 保存。
> 不要给 freqtrade 命令设置 `$ErrorActionPreference='Stop'`——它的日志走 stderr，PowerShell 会误判为致命错误。

## 故障排查

| 现象 | 处理 |
|------|------|
| 运行 `.ps1` 提示「因为在此系统上禁止运行脚本」(PSSecurityException) | Windows 默认策略拦截，一次性放行：`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`（详见下方小节） |
| 启动卡死 / 低 CPU 空转 | 部署 `sitecustomize.py` 补丁 + 杀软信任区（见上文） |
| `Fatal error in launcher: Unable to create process ...` | venv 被移动过，重建启动器：`.\.venv\Scripts\python.exe -m pip install --force-reinstall --no-deps freqtrade py-spy` |
| 控制台中文乱码 | `chcp 65001`；`.ps1` 文件保存为 UTF-8 BOM |
| CoinGecko 汇率接口报错 | `config.json` 中 `fiat_display_currency` 置 `""` |
| 数据缺失 / 下载不全 | 重跑 `.\scripts\download-data.ps1`（增量更新）；想彻底重下先删除 `user_data/data/gate/` 下对应文件 |
| 想换 Binance | 本机直连不通；可改用公共数据站 `data.binance.vision` 直连下载 |

### 脚本被执行策略拦截（报错「因为在此系统上禁止运行脚本」）

Windows PowerShell 的**默认执行策略是 `Restricted`**——默认禁止运行一切 `.ps1` 脚本。这是 Windows 的安全默认值，与项目本身无关。报错特征：`PSSecurityException` / `UnauthorizedAccess` /「因为在此系统上禁止运行脚本」。

**一次性解决（推荐）**：仅对你的用户生效、无需管理员权限、随时可撤销：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

- 含义：本地脚本放行；从网上下载的脚本仍然需要数字签名（保留安全底线）。这是微软官方推荐的常规设置。
- 设置完成后即可直接运行脚本；如果某个**已经打开**的窗口仍报错，关掉它、重新开一个新窗口即可。
- **撤销 / 恢复系统默认**：

```powershell
Set-ExecutionPolicy -Scope CurrentUser Undefined
```

**不想改动任何系统设置的替代方式**：

```powershell
# 方式 1：仅对当前窗口临时放行（关闭窗口即失效）
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\dry-run.ps1

# 方式 2：用启动参数直接运行（不更改任何策略设置）
powershell -ExecutionPolicy Bypass -File .\scripts\dry-run.ps1
```

## 版本管理（git）

大文件与敏感文件（`.venv/`、`config.json`、数据、日志、数据库）均已用 `.gitignore` 排除。提交前先自查：

```powershell
git status          # 确认 config.json、.venv 等没有被加入
git add -A
git commit -m "更新说明"
git push            # 推送到 https://github.com/C-Gerald/CyberSPACE
```

## 路线图（TODO）

- [ ] 策略迭代：降低交易频率、增加趋势 / 波动率过滤，先把回测期望做正（务必计入 0.2% 手续费）
- [ ] hyperopt 参数优化（目标函数同样含手续费）
- [ ] 扩充交易对（Gate 现货中流动性好的标的）
- [ ] dry-run 长跑观察 + 交易复盘
- [ ] （可选）Telegram 通知 / 简易监控面板

---

*基于开源框架 [freqtrade](https://www.freqtrade.io/)（Apache-2.0）；数据与交易接口来自 [Gate.io](https://www.gate.io/)。*
