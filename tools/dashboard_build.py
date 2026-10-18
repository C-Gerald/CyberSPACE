#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CyberSPACE 本地可视化控制台生成器

读取项目数据（配置 / 模拟盘数据库 / 回测结果 / K线数据 / 日志），
生成一个自包含的 dashboard.html —— 无外部依赖、无需本地服务器，
直接用浏览器打开即可（图表为原生 Canvas 绘制，不依赖任何 CDN）。

用法（项目根目录下）:
    .\\.venv\\Scripts\\python.exe .\\tools\\dashboard_build.py
或直接运行:
    .\\scripts\\dashboard.ps1
"""
import json
import re
import sqlite3
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dashboard.html"
DATA_DIR = ROOT / "user_data" / "data" / "gate"
BT_DIR = ROOT / "user_data" / "backtest_results"
DB = ROOT / "tradesv3.dryrun.sqlite"
LOG = ROOT / "user_data" / "logs" / "trade.log"
JOB = ROOT / "user_data" / "logs" / "dashboard_job.json"

ANSI = re.compile(r"\x1b\[[0-9;]*m")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


# ---------------------------------------------------------------- 数据采集 --
def read_json(p, default=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def loc(s):
    """ISO 时间字符串 → 本地时间 'MM-DD HH:MM'（对用户友好）"""
    if s is None:
        return None
    try:
        dt = datetime.fromisoformat(str(s))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone().strftime("%m-%d %H:%M")
    except Exception:
        return str(s)[:16]


def bot_status():
    """通过 tasklist 判断 freqtrade 是否在运行"""
    try:
        r = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq freqtrade.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, errors="ignore", timeout=20,
            creationflags=NO_WINDOW,
        )
        for line in r.stdout.splitlines():
            if "freqtrade.exe" in line.lower():
                parts = [p.strip('" ') for p in line.split(",")]
                pid = parts[1] if len(parts) > 1 else None
                mem = None
                if len(parts) > 4:
                    digits = re.sub(r"\D", "", parts[4])
                    mem = round(int(digits) / 1024, 1) if digits else None
                return {"running": True, "pid": pid, "mem_mb": mem}
    except Exception:
        pass
    return {"running": False, "pid": None, "mem_mb": None}


def data_files():
    out = []
    if not DATA_DIR.is_dir():
        return out
    for f in sorted(DATA_DIR.glob("*.feather")):
        m = re.match(r"(.+?)-(\w+)\.feather$", f.name)
        pair = m.group(1).replace("_", "/") if m else f.stem
        tf = m.group(2) if m else "?"
        rows, first, last = None, None, None
        try:
            import pyarrow.feather as feather
            t = feather.read_table(str(f))
            rows = t.num_rows
            if rows and "date" in t.column_names:
                d = t.column("date").to_pylist()
                first, last = loc(d[0]), loc(d[-1])
        except Exception:
            pass
        out.append({
            "pair": pair, "tf": tf, "rows": rows,
            "first": first, "last": last,
            "mb": round(f.stat().st_size / 1048576, 2),
            "mtime": datetime.fromtimestamp(f.stat().st_mtime).strftime("%m-%d %H:%M"),
        })
    return out


def backtests(limit=10):
    out = []
    if not BT_DIR.is_dir():
        return out
    zips = sorted(BT_DIR.glob("*.zip"),
                  key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    for zp in zips:
        item = {
            "id": zp.name,
            "mtime": datetime.fromtimestamp(zp.stat().st_mtime).strftime("%m-%d %H:%M"),
            "strategy": "?", "timeframe": None,
            "n": 0, "trades": [],
            "profit_pct": None, "profit_abs": None,
            "final_balance": None, "start_balance": None,
            "winrate": None, "max_dd": None,
            "best": None, "worst": None, "avg_pnl": None, "avg_dur": None,
            "span": None, "error": None,
        }
        try:
            z = zipfile.ZipFile(zp)
            jn = next(n for n in z.namelist()
                      if n.endswith(".json") and "_config" not in n)
            data = json.loads(z.read(jn))
            strat = data.get("strategy") or {}
            sname = next(iter(strat), "?")
            sd = strat.get(sname) or {}
            trades = []
            for t in sd.get("trades") or []:
                trades.append({
                    "pair": t.get("pair"),
                    "short": bool(t.get("is_short")),
                    "od": loc(t.get("open_date")), "cd": loc(t.get("close_date")),
                    "or": t.get("open_rate"), "cr": t.get("close_rate"),
                    "stake": t.get("stake_amount"),
                    "pnl": t.get("profit_abs"), "pnlr": t.get("profit_ratio"),
                    "reason": t.get("exit_reason"), "tag": t.get("enter_tag"),
                    "dur": t.get("trade_duration"),
                    "cts": t.get("close_timestamp") or 0,
                })
            trades.sort(key=lambda t: t["cts"] or 0)
            n = len(trades)
            pnls = [float(t["pnl"] or 0) for t in trades]
            durs = [t["dur"] for t in trades if t["dur"] is not None]
            ws = sd.get("wallet_stats") or {}
            item.update({
                "strategy": sname,
                "timeframe": sd.get("timeframe"),
                "n": n, "trades": trades,
                "profit_pct": sd.get("profit_total"),
                "profit_abs": sd.get("profit_total_abs"),
                "final_balance": sd.get("final_balance"),
                "start_balance": sd.get("starting_balance") or sd.get("dry_run_wallet"),
                "winrate": (sum(1 for v in pnls if v > 0) / n) if n else None,
                "max_dd": ws.get("max_drawdown_account"),
                "best": max(pnls) if pnls else None,
                "worst": min(pnls) if pnls else None,
                "avg_pnl": (sum(pnls) / n) if n else None,
                "avg_dur": (sum(durs) / len(durs)) if durs else None,
                "span": (loc(sd.get("backtest_start")) + " ~ " + str(loc(sd.get("backtest_end"))))
                        if sd.get("backtest_start") else None,
            })
        except Exception as e:
            item["error"] = str(e)
        out.append(item)
    return out


def dryrun(wallet_start=1000.0):
    res = {"exists": DB.exists(), "rows": [], "open": 0, "closed": 0,
           "realized": 0.0, "balance": None, "error": None}
    if not DB.exists():
        return res
    try:
        con = sqlite3.connect(str(DB))
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        for r in cur.execute("SELECT * FROM trades ORDER BY id DESC LIMIT 50"):
            d = dict(r)
            res["rows"].append({
                "pair": d.get("pair"),
                "short": bool(d.get("is_short")),
                "od": loc(d.get("open_date")), "cd": loc(d.get("close_date")),
                "or": d.get("open_rate"), "cr": d.get("close_rate"),
                "stake": d.get("stake_amount"),
                "pnl": d.get("close_profit_abs"),
                "reason": d.get("exit_reason"),
                "open": bool(d.get("is_open")),
            })
        res["open"] = cur.execute("SELECT COUNT(*) FROM trades WHERE is_open=1").fetchone()[0]
        res["closed"] = cur.execute("SELECT COUNT(*) FROM trades WHERE is_open=0").fetchone()[0]
        try:
            v = cur.execute("SELECT COALESCE(SUM(close_profit_abs),0) FROM trades WHERE is_open=0").fetchone()[0]
        except Exception:
            v = 0
        res["realized"] = float(v or 0)
        con.close()
    except Exception as e:
        res["error"] = str(e)
    res["balance"] = float(wallet_start) + res["realized"]
    return res


def log_tail(n=40):
    p = LOG
    if not p.exists():
        p = ROOT / "user_data" / "logs" / "freqtrade.log"
    if not p.exists():
        return ""
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        return ANSI.sub("", "\n".join(lines[-n:]))
    except Exception:
        return ""


# ------------------------------------------------------------------- 模板 --
TMPL = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>⚡ CyberSPACE 控制台</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>⚡</text></svg>">
<style>
:root{--bg:#0b0f14;--card:#12181f;--border:#232c37;--text:#e6edf3;--muted:#8b949e;--green:#3fb950;--red:#f85149;--blue:#58a6ff;--amber:#d29922}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:14px/1.55 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
.wrap{max-width:1280px;margin:0 auto;padding:16px 20px 60px}
header{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin:4px 0 14px}
h1{font-size:20px;margin:0;font-weight:700}
.pill{border:1px solid var(--border);border-radius:999px;padding:3px 12px;font-size:13px;display:inline-flex;align-items:center;gap:7px;background:var(--card)}
.dot{width:9px;height:9px;border-radius:50%;display:inline-block;background:#5a6b7d}
.dot.on{background:var(--green);box-shadow:0 0 9px var(--green);animation:pulse 1.6s infinite}
@keyframes pulse{50%{opacity:.35}}
.muted{color:var(--muted)}
.mono,.num{font-family:Consolas,ui-monospace,monospace}
.green{color:var(--green)}.red{color:var(--red)}.amber{color:var(--amber)}.blue{color:var(--blue)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;margin:12px 0}
.mini{display:grid;grid-template-columns:repeat(auto-fit,minmax(118px,1fr));gap:10px;margin:12px 0}
.card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:13px 16px}
.card h3{margin:0 0 8px;font-size:13px;color:var(--muted);font-weight:600;letter-spacing:.3px}
.kv{display:flex;justify-content:space-between;gap:10px;font-size:13px;padding:2px 0}
.kv .k{color:var(--muted)}
.kv .v{font-family:Consolas,ui-monospace,monospace;text-align:right}
.big{font-size:22px;font-weight:700;font-family:Consolas,monospace;margin:2px 0}
section{margin:12px 0}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px;align-items:start}
@media (max-width:900px){.grid2{grid-template-columns:1fr}}
canvas{width:100%;height:240px;display:block}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th{color:var(--muted);font-weight:600;text-align:left;padding:6px 8px;border-bottom:1px solid var(--border);white-space:nowrap}
td{padding:5px 8px;border-bottom:1px solid #1a2129;font-family:Consolas,ui-monospace,monospace;white-space:nowrap}
td:first-child{font-family:inherit}
tr:hover td{background:#151c25}
.num{text-align:right}
.btn{background:#1b2430;color:var(--text);border:1px solid var(--border);border-radius:7px;padding:4px 11px;font-size:12.5px;cursor:pointer}
.btn:hover{border-color:#3d4a5a;background:#222d3b}
.ops{display:flex;align-items:center;gap:10px;padding:5px 0;flex-wrap:wrap}
.ops .lbl{min-width:210px;color:var(--muted)}
code{background:#0a0e13;border:1px solid var(--border);border-radius:6px;padding:3px 9px;font:12px Consolas,monospace;color:#9ecbff}
pre.logs{background:#0a0e13;border:1px solid var(--border);border-radius:8px;padding:10px 12px;max-height:280px;overflow:auto;font:12px/1.55 Consolas,monospace;color:#9fb0c3;white-space:pre-wrap;margin:0}
.tblwrap{overflow:auto;max-height:420px}
select{background:#1b2430;color:var(--text);border:1px solid var(--border);border-radius:7px;padding:4px 8px;font-size:13px}
footer{margin-top:22px;font-size:12px}
.hint{font-size:12.5px;color:var(--muted);margin:4px 0 2px}
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>⚡ CyberSPACE 量化控制台</h1>
  <span class="pill" id="botPill"></span>
  <span class="muted" style="font-size:12.5px">生成于 <span id="builtAt"></span> · 每 5 秒自动刷新</span>
  <span class="pill" id="jobPill" style="display:none;border-color:#6a5320"></span>
  <span style="flex:1"></span>
  <button class="btn" id="pauseBtn">⏸ 暂停刷新</button>
</header>

<div class="cards" id="cards"></div>

<section class="card">
  <h3>🎛️ 操作台 <span class="muted" style="font-weight:400" id="opsHint"></span></h3>
  <div id="ops"></div>
</section>

<section class="card">
  <h3 style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">📈 回测可视化
    <select id="btSel"></select>
    <span class="muted" id="btMeta" style="font-weight:400"></span>
  </h3>
  <div class="grid2">
    <div>
      <div class="hint">权益曲线（累计盈亏 / USDT，按平仓顺序 · 本地时间）</div>
      <canvas id="equity"></canvas>
    </div>
    <div>
      <div class="hint">每笔交易盈亏（USDT）</div>
      <canvas id="bars"></canvas>
    </div>
  </div>
  <div class="mini" id="btStats"></div>
  <div class="hint">交易明细（最近 20 笔）</div>
  <div class="tblwrap"><table id="btTable"></table></div>
</section>

<div class="grid2">
  <section class="card">
    <h3>🤖 模拟盘交易（本地数据库）</h3>
    <div class="tblwrap"><table id="dryTable"></table></div>
  </section>
  <section class="card">
    <h3>🗂️ 行情数据文件</h3>
    <div class="tblwrap"><table id="dataTable"></table></div>
  </section>
</div>

<section class="card">
  <h3>📜 运行日志（trade.log 末尾 40 行）</h3>
  <pre class="logs" id="logs"></pre>
</section>

<footer class="muted">本页由 tools/dashboard_build.py 自动生成 · 数据来自本地文件，仅供研究学习，不构成投资建议</footer>
</div>

<script>
const DATA = __DATA_JSON__;
const $ = s => document.querySelector(s);
const nf = (v, d) => (v==null || isNaN(v)) ? "—" : Number(v).toFixed(d==null?2:d);
const nfs = (v, d) => (v==null || isNaN(v)) ? "—" : (v>=0?"+":"")+Number(v).toFixed(d==null?2:d);
const pfs = (v, d) => (v==null || isNaN(v)) ? "—" : (v>=0?"+":"")+(Number(v)*100).toFixed(d==null?2:d)+"%";
const ccls = v => v>0 ? "green" : (v<0 ? "red" : "muted");
const esc = s => String(s==null?"":s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function fdur(m){ if(m==null) return "—"; m=Math.round(m); if(m<60) return m+" 分钟"; return Math.floor(m/60)+" 小时 "+(m%60)+" 分"; }
const LS = { get(k){ try{ return localStorage.getItem(k) }catch(e){ return null } },
             set(k,v){ try{ localStorage.setItem(k,v) }catch(e){} } };
function copyText(txt, btn, doneLabel){
  const done = () => { const o=btn.textContent; btn.textContent=doneLabel||"已复制 ✓"; setTimeout(()=>btn.textContent=o,1200); };
  const fb = () => {
    const ta=document.createElement("textarea"); ta.value=txt; ta.style.position="fixed"; ta.style.opacity="0";
    document.body.appendChild(ta); ta.select(); let ok=false;
    try{ ok=document.execCommand("copy") }catch(e){}
    document.body.removeChild(ta); ok ? done() : (btn.textContent="复制失败，请手动选中");
  };
  try{ (navigator.clipboard && navigator.clipboard.writeText) ? navigator.clipboard.writeText(txt).then(done, fb) : fb(); }
  catch(e){ fb(); }
}

/* ---------------- 渲染：状态与卡片 ---------------- */
function renderStatus(){
  const b = DATA.bot||{};
  const pill = $("#botPill");
  pill.innerHTML = b.running
    ? '<span class="dot on"></span> 机器人运行中' + (b.pid ? ' · PID '+esc(b.pid) : '')
    : '<span class="dot"></span> 机器人已停止';
  $("#builtAt").textContent = DATA.built_at || "";
  const job = DATA.job, jp = $("#jobPill");
  if (job && job.label) {
    jp.style.display = "inline-flex";
    jp.innerHTML = '<span class="dot" style="background:#d29922;box-shadow:0 0 9px #d29922"></span><span class="amber">正在运行：' + esc(job.label) + '（' + esc(job.started||"") + ' 开始）</span>';
  }
}
function renderCards(){
  const c = DATA.config||{}, d = DATA.dryrun||{}, df = DATA.data_files||[], bts = DATA.backtests||[];
  const bal = d.balance!=null ? d.balance : (c.wallet||1000);
  const rp = d.realized||0;
  const bt = bts.find(x=>!x.error) || bts[0];
  const lastK = df.reduce((a,f)=> (f.last && (!a||f.last>a)) ? f.last : a, null);
  const totalMB = df.reduce((a,f)=>a+(f.mb||0),0);
  $("#cards").innerHTML = `
  <div class="card"><h3>🤖 机器人</h3>
    <div class="kv"><span class="k">状态</span><span class="v ${b_running_cls()}">${DATA.bot&&DATA.bot.running?"运行中":"已停止"}</span></div>
    <div class="kv"><span class="k">模式</span><span class="v">${c.dry_run===false?"实盘 ⚠":"dry-run 模拟盘"}</span></div>
    <div class="kv"><span class="k">策略 / 周期</span><span class="v">${esc(c.strategy||"?")} · ${esc(c.timeframe||"?")}</span></div>
    <div class="kv"><span class="k">交易所 / 交易对</span><span class="v">${esc(c.exchange||"?")} · ${(c.pairs||[]).length} 对</span></div>
  </div>
  <div class="card"><h3>💰 模拟钱包</h3>
    <div class="big ${ccls(rp)}">${nf(bal)} USDT</div>
    <div class="kv"><span class="k">已实现盈亏</span><span class="v ${ccls(rp)}">${nfs(rp)} (${pfs(rp/(c.wallet||1000))})</span></div>
    <div class="kv"><span class="k">持仓 / 已平仓</span><span class="v">${d.open||0} / ${d.closed||0} 笔</span></div>
    <div class="kv"><span class="k">起始资金</span><span class="v">${nf(c.wallet||1000,0)} USDT</span></div>
  </div>
  <div class="card"><h3>🗂️ 行情数据</h3>
    <div class="big">${df.length} <span style="font-size:13px;font-weight:400" class="muted">个文件 · ${nf(totalMB,1)} MB</span></div>
    <div class="kv"><span class="k">最新K线(本地时间)</span><span class="v">${esc(lastK||"—")}</span></div>
    <div class="kv"><span class="k">覆盖</span><span class="v">${[...new Set(df.map(f=>f.pair))].length} 个交易对 · ${[...new Set(df.map(f=>f.tf))].join(" / ")||"—"}</span></div>
  </div>
  <div class="card"><h3>📈 最新回测</h3>
    ${bt ? `
    <div class="big ${ccls(bt.profit_pct)}">${pfs(bt.profit_pct)}</div>
    <div class="kv"><span class="k">时间 / 周期</span><span class="v">${esc(bt.mtime)} · ${esc(bt.timeframe||"?")}</span></div>
    <div class="kv"><span class="k">交易数 / 胜率</span><span class="v">${bt.n} 笔 · ${bt.winrate!=null?nf(bt.winrate*100,1)+"%":"—"}</span></div>
    ` : `<div class="muted">暂无回测结果</div>`}
  </div>`;

  function b_running_cls(){ return DATA.bot&&DATA.bot.running ? "green" : "muted"; }
}

/* ---------------- 渲染：操作台 ---------------- */
function renderOps(){
  const ops = [
    ["▶ 启动模拟盘（dry-run）", ".\\scripts\\dry-run.ps1", "停止：在运行它的窗口按 Ctrl+C"],
    ["📈 运行回测（5m）", ".\\scripts\\backtest.ps1", ""],
    ["📈 运行回测（15m）", ".\\scripts\\backtest.ps1 -Timeframe 15m", ""],
    ["🔄 更新行情数据", ".\\scripts\\download-data.ps1", "需要代理时请先打开 Clash"],
    ["🛑 强制停止机器人（应急）", "taskkill /IM freqtrade.exe /F", "正常请优先用 Ctrl+C"],
    ["♻ 重新生成本页（单次）", ".\\scripts\\dashboard.ps1 -Once", ""],
  ];
  $("#opsHint").textContent = DATA.autorun
    ? "— 点「▶ 运行」自动执行（命令同时复制到剪贴板，由 dashboard.ps1 窗口执行）"
    : "— 点「复制」，再到『CyberSPACE 操作窗口』粘贴 + 回车执行";
  const runLabel = DATA.autorun ? "▶ 运行" : "复制";
  const doneLabel = DATA.autorun ? "已触发 ✓" : "已复制 ✓";
  $("#ops").innerHTML = ops.map(([lbl,cmd,hint],i)=>`
    <div class="ops">
      <span class="lbl">${esc(lbl)}</span>
      <code>${esc(cmd)}</code>
      <button class="btn" data-i="${i}">${runLabel}</button>
      ${hint?`<span class="muted" style="font-size:12px">${esc(hint)}</span>`:""}
    </div>`).join("");
  document.querySelectorAll("#ops .btn").forEach(b=>{
    b.onclick = () => copyText(ops[+b.dataset.i][1], b, doneLabel);
  });
}

/* ---------------- 渲染：回测选择与图表 ---------------- */
function selBt(){ 
  const sel = $("#btSel"); 
  return (DATA.backtests||[]).find(b=>b.id===sel.value) || (DATA.backtests||[])[0];
}
function initSelector(){
  const bts = DATA.backtests||[], sel = $("#btSel");
  if(!bts.length){ sel.innerHTML = "<option>暂无回测</option>"; sel.disabled = true; return; }
  sel.innerHTML = bts.map(b=>`<option value="${esc(b.id)}">${esc(b.mtime)} · ${esc(b.timeframe||"?")} · ${pfs(b.profit_pct)} · ${b.n} 笔</option>`).join("");
  const saved = LS.get("cs.bt");
  if(saved && bts.some(b=>b.id===saved)) sel.value = saved;
  sel.onchange = () => { LS.set("cs.bt", sel.value); drawAllBt(); };
}
function mkCanvas(id){
  const c = document.getElementById(id); if(!c) return null;
  const dpr = window.devicePixelRatio||1, w = c.clientWidth||600, h = 240;
  c.width = Math.round(w*dpr); c.height = Math.round(h*dpr);
  const ctx = c.getContext("2d"); ctx.setTransform(dpr,0,0,dpr,0,0);
  ctx.clearRect(0,0,w,h);
  return {ctx,w,h};
}
function drawEquity(trades){
  const o = mkCanvas("equity"); if(!o) return; const {ctx,w,h} = o;
  if(!trades||!trades.length){ ctx.fillStyle="#8b949e"; ctx.font="13px sans-serif"; ctx.fillText("暂无数据",12,26); return; }
  const padL=56,padR=66,padT=14,padB=26, pw=w-padL-padR, ph=h-padT-padB;
  let acc=0; const vals=[0]; trades.forEach(t=>{ acc+=t.pnl||0; vals.push(acc); });
  let mn=Math.min(...vals), mx=Math.max(...vals);
  if(mn===mx){ mn-=1; mx+=1; }
  const rg=mx-mn; mn-=rg*0.08; mx+=rg*0.08;
  const X=i=>padL+pw*i/(vals.length-1), Y=v=>padT+(mx-v)/(mx-mn)*ph;
  ctx.strokeStyle="#232c37"; ctx.fillStyle="#8b949e"; ctx.font="11px Consolas,monospace"; ctx.textAlign="right"; ctx.textBaseline="middle";
  for(let g=0; g<5; g++){ const v=mx-(mx-mn)*g/4, y=Y(v);
    ctx.beginPath(); ctx.moveTo(padL,y); ctx.lineTo(padL+pw,y); ctx.stroke();
    ctx.fillText((v>=0?"+":"")+v.toFixed(1), padL-6, y); }
  if(mn<0 && mx>0){ ctx.strokeStyle="#3d4a5a"; ctx.setLineDash([4,4]);
    ctx.beginPath(); ctx.moveTo(padL,Y(0)); ctx.lineTo(padL+pw,Y(0)); ctx.stroke(); ctx.setLineDash([]); }
  const pos = acc>=0, col = pos?"#3fb950":"#f85149";
  const grad = ctx.createLinearGradient(0,padT,0,padT+ph);
  grad.addColorStop(0, pos?"rgba(63,185,80,.25)":"rgba(248,81,73,.25)");
  grad.addColorStop(1, "rgba(0,0,0,0)");
  ctx.beginPath(); ctx.moveTo(X(0),Y(vals[0]));
  for(let i=1;i<vals.length;i++) ctx.lineTo(X(i),Y(vals[i]));
  ctx.lineTo(X(vals.length-1),padT+ph); ctx.lineTo(X(0),padT+ph); ctx.closePath();
  ctx.fillStyle=grad; ctx.fill();
  ctx.beginPath(); ctx.moveTo(X(0),Y(vals[0]));
  for(let i=1;i<vals.length;i++) ctx.lineTo(X(i),Y(vals[i]));
  ctx.strokeStyle=col; ctx.lineWidth=1.6; ctx.stroke();
  const lx=X(vals.length-1), ly=Y(vals[vals.length-1]);
  ctx.fillStyle=col; ctx.beginPath(); ctx.arc(lx,ly,3,0,7); ctx.fill();
  ctx.textAlign="left"; ctx.fillStyle="#e6edf3"; ctx.fillText((acc>=0?"+":"")+acc.toFixed(2), Math.min(lx+7, w-62), ly);
  ctx.fillStyle="#8b949e"; ctx.textBaseline="top";
  ctx.textAlign="left";  ctx.fillText(trades[0].cd||"", padL, padT+ph+7);
  ctx.textAlign="right"; ctx.fillText(trades[trades.length-1].cd||"", padL+pw, padT+ph+7);
}
function drawBars(trades){
  const o = mkCanvas("bars"); if(!o) return; const {ctx,w,h} = o;
  if(!trades||!trades.length){ ctx.fillStyle="#8b949e"; ctx.font="13px sans-serif"; ctx.fillText("暂无数据",12,26); return; }
  const padL=56,padR=20,padT=14,padB=26, pw=w-padL-padR, ph=h-padT-padB;
  const vals = trades.map(t=>t.pnl||0);
  let mn=Math.min(...vals,0), mx=Math.max(...vals,0); if(mn===mx){mn-=1;mx+=1;}
  const rg=mx-mn; mn-=rg*0.08; mx+=rg*0.08;
  const Y=v=>padT+(mx-v)/(mx-mn)*ph;
  ctx.strokeStyle="#232c37"; ctx.fillStyle="#8b949e"; ctx.font="11px Consolas,monospace"; ctx.textAlign="right"; ctx.textBaseline="middle";
  for(let g=0; g<5; g++){ const v=mx-(mx-mn)*g/4, y=Y(v);
    ctx.beginPath(); ctx.moveTo(padL,y); ctx.lineTo(padL+pw,y); ctx.stroke();
    ctx.fillText((v>=0?"+":"")+v.toFixed(1), padL-6, y); }
  const y0=Y(0), bw=Math.max(1, Math.min(7, pw/vals.length*0.7));
  vals.forEach((v,i)=>{ const x=padL+pw*(i+0.5)/vals.length;
    ctx.fillStyle = v>0 ? "rgba(63,185,80,.85)" : (v<0 ? "rgba(248,81,73,.85)" : "#5a6b7d");
    const y=Math.min(Y(v),y0), hh=Math.max(1,Math.abs(Y(v)-y0));
    ctx.fillRect(x-bw/2, y, bw, hh); });
  ctx.strokeStyle="#3d4a5a"; ctx.beginPath(); ctx.moveTo(padL,y0); ctx.lineTo(padL+pw,y0); ctx.stroke();
  ctx.fillStyle="#8b949e"; ctx.textBaseline="top";
  ctx.textAlign="left";  ctx.fillText(trades[0].cd||"", padL, padT+ph+7);
  ctx.textAlign="right"; ctx.fillText(trades[trades.length-1].cd||"", padL+pw, padT+ph+7);
}
function renderBtStats(){
  const b = selBt(); const el = $("#btStats");
  if(!b){ el.innerHTML=""; return; }
  if(b.error){ el.innerHTML = `<div class="card muted">读取失败：${esc(b.error)}</div>`; return; }
  const items = [
    ["总收益", pfs(b.profit_pct), ccls(b.profit_pct)],
    ["总盈亏", nfs(b.profit_abs)+" U", ccls(b.profit_abs)],
    ["交易数", b.n+" 笔", ""],
    ["胜率", b.winrate!=null ? nf(b.winrate*100,1)+"%" : "—", ""],
    ["最大回撤", b.max_dd!=null ? nf(b.max_dd*100,2)+"%" : "—", "red"],
    ["平均每笔", nfs(b.avg_pnl)+" U", ccls(b.avg_pnl)],
    ["最佳单笔", nfs(b.best)+" U", "green"],
    ["最差单笔", nfs(b.worst)+" U", "red"],
    ["平均持仓", fdur(b.avg_dur), ""],
    ["期末余额", nf(b.final_balance)+" U", ccls(b.final_balance - (b.start_balance||1000))],
  ];
  el.innerHTML = items.map(([k,v,c])=>`<div class="card" style="padding:9px 12px">
     <div class="muted" style="font-size:12px">${esc(k)}</div>
     <div class="mono ${c}" style="font-size:16px;font-weight:700">${v}</div></div>`).join("");
  $("#btMeta").textContent = `${b.strategy||""} · ${b.span||""}`;
}
function renderBtTable(){
  const b = selBt(), tb = $("#btTable");
  if(!b){ tb.innerHTML=""; return; }
  const rows = (b.trades||[]).slice(-20).reverse();
  tb.innerHTML = "<thead><tr><th>交易对</th><th>方向</th><th>开仓</th><th>平仓</th><th>开仓价</th><th>平仓价</th><th>金额</th><th>盈亏(U)</th><th>盈亏%</th><th>持仓</th><th>平仓原因</th></tr></thead><tbody>"+
    rows.map(t=>`<tr>
      <td>${esc(t.pair)}</td><td>${t.short?"空":"多"}</td>
      <td>${esc(t.od)}</td><td>${esc(t.cd)}</td>
      <td class="num">${nf(t.or, (t.or||0)>=100?2:4)}</td><td class="num">${nf(t.cr, (t.cr||0)>=100?2:4)}</td>
      <td class="num">${nf(t.stake)}</td>
      <td class="num ${ccls(t.pnl)}">${nfs(t.pnl)}</td>
      <td class="num ${ccls(t.pnl)}">${pfs(t.pnlr)}</td>
      <td class="num">${fdur(t.dur)}</td>
      <td>${esc(String(t.reason||"").replace("exit_",""))}</td></tr>`).join("")+"</tbody>";
}
function drawAllBt(){ drawEquity((selBt()||{}).trades||[]); drawBars((selBt()||{}).trades||[]); renderBtStats(); renderBtTable(); }

/* ---------------- 渲染：模拟盘 / 数据 / 日志 ---------------- */
function renderDry(){
  const d = DATA.dryrun||{}, tb = $("#dryTable");
  if(!(d.rows||[]).length){
    tb.innerHTML = `<tbody><tr><td class="muted">${d.exists===false?"尚未生成数据库（机器人还没启动过）":"暂无交易——机器人还没开过仓"}</td></tr></tbody>`;
    return;
  }
  tb.innerHTML = "<thead><tr><th>交易对</th><th>方向</th><th>开仓</th><th>平仓</th><th>开仓价</th><th>平仓价</th><th>金额</th><th>盈亏(U)</th><th>状态</th><th>原因</th></tr></thead><tbody>"+
    d.rows.map(r=>`<tr>
      <td>${esc(r.pair)}</td><td>${r.short?"空":"多"}</td>
      <td>${esc(r.od)}</td><td>${r.open?"持仓中":esc(r.cd||"—")}</td>
      <td class="num">${nf(r.or, (r.or||0)>=100?2:4)}</td><td class="num">${r.open?"—":nf(r.cr,(r.cr||0)>=100?2:4)}</td>
      <td class="num">${nf(r.stake)}</td>
      <td class="num ${r.open?"muted":ccls(r.pnl)}">${r.open?"—":nfs(r.pnl)}</td>
      <td>${r.open?'<span class="blue">持仓中</span>':'<span class="muted">已平仓</span>'}</td>
      <td>${esc(String(r.reason||"").replace("exit_",""))}</td></tr>`).join("")+"</tbody>";
}
function renderData(){
  const df = DATA.data_files||[], tb = $("#dataTable");
  if(!df.length){ tb.innerHTML = '<tbody><tr><td class="muted">暂无数据文件</td></tr></tbody>'; return; }
  tb.innerHTML = "<thead><tr><th>交易对</th><th>周期</th><th>K线数</th><th>起始</th><th>结束</th><th>大小</th></tr></thead><tbody>"+
    df.map(f=>`<tr>
      <td>${esc(f.pair)}</td><td>${esc(f.tf)}</td>
      <td class="num">${f.rows!=null?f.rows:"—"}</td>
      <td>${esc(f.first||"—")}</td><td>${esc(f.last||"—")}</td>
      <td class="num">${nf(f.mb,2)} MB</td></tr>`).join("")+"</tbody>";
}
function renderLogs(){ $("#logs").textContent = DATA.logs || "（暂无日志）"; }

/* ---------------- 自动刷新 ---------------- */
let paused = false;
function scheduleRefresh(){ if(!paused) setTimeout(()=>window.location.reload(), 5000); }
function initPause(){
  const btn = $("#pauseBtn");
  btn.onclick = () => {
    paused = !paused;
    btn.textContent = paused ? "▶ 恢复刷新" : "⏸ 暂停刷新";
    if(!paused) scheduleRefresh();
  };
}

/* ---------------- 启动 ---------------- */
renderStatus(); renderCards(); renderOps();
initSelector(); drawAllBt();
renderDry(); renderData(); renderLogs();
initPause(); scheduleRefresh();
try{ const y = sessionStorage.getItem("cs.scrollY"); if(y) window.scrollTo(0, parseInt(y)); }catch(e){}
window.addEventListener("beforeunload", ()=>{ try{ sessionStorage.setItem("cs.scrollY", String(window.scrollY)) }catch(e){} });
addEventListener("resize", ()=>{ clearTimeout(window.__rz); window.__rz=setTimeout(drawAllBt, 200); });
</script>
</body>
</html>
'''


# ------------------------------------------------------------------- 主流程 --
def autorun_flag():
    argv = sys.argv[1:]
    if "--autorun" in argv:
        try:
            return argv[argv.index("--autorun") + 1] not in ("0", "false", "False", "no")
        except IndexError:
            pass
    return True


def main():
    cfg = read_json(ROOT / "config.json", {}) or {}
    ex = cfg.get("exchange") or {}
    wallet = cfg.get("dry_run_wallet") or 1000
    job = read_json(JOB, None)
    if not (isinstance(job, dict) and job.get("label")):
        job = None
    elif JOB.exists() and (time.time() - JOB.stat().st_mtime) > 6 * 3600:
        job = None  # 超过 6 小时的残留状态，视为无效
    payload = {
        "built_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "bot": bot_status(),
        "config": {
            "strategy": cfg.get("strategy"),
            "timeframe": cfg.get("timeframe"),
            "dry_run": cfg.get("dry_run"),
            "wallet": wallet,
            "exchange": ex.get("name"),
            "max_open_trades": cfg.get("max_open_trades"),
            "pairs": ex.get("pair_whitelist") or [],
        },
        "data_files": data_files(),
        "backtests": backtests(),
        "dryrun": dryrun(float(wallet)),
        "logs": log_tail(),
        "autorun": autorun_flag(),
        "job": job,
    }
    js = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    js = js.replace("</", "<\\/")  # 防止数据中出现 </script>
    OUT.write_text(TMPL.replace("__DATA_JSON__", js), encoding="utf-8")
    bt_n = len(payload["backtests"])
    print(f"dashboard.html 已生成 | 回测 {bt_n} 个 | 模拟盘持仓 {payload['dryrun']['open']} | {payload['built_at']}")


if __name__ == "__main__":
    main()
