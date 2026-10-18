"""CyberSPACE 项目本地兼容补丁（sitecustomize）。

背景 / 问题
-----------
本机（Windows + 火绒等安全软件环境）上，TCP 回环连接被拦截：
- Python 的 asyncio 在 Windows 上创建事件循环时，会用 socket.socketpair()
  做"自管道"（self-pipe），而 CPython 在 Windows 上是用
  「回环 TCP：listen + connect + accept」来模拟 socketpair 的（socket.py 的
  纯 Python 回退实现，第 645 行 lsock.accept()）。
- 本机的回环 accept() 会被随机/持续卡死（甚至频繁出现 WinError 10048
  端口冲突），导致所有 asyncio 程序（freqtrade、Jupyter 等）随机挂起。

修复 / 方案
-----------
把默认的 TCP 版 socketpair 替换为 **UDP 版实现**：
- 创建一个 UDP socket 绑定 127.0.0.1:0，并 connect 到自己（自连接）；
- dup() 出第二个 fd，两个 fd 共享同一个接收队列；
- UDP 不需要三次握手、不需要 listen/accept，因此不可能被同样的方式卡死。

asyncio 自管道只需要「写一个字节 → 另一端可读」的语义，UDP 版本完全满足。
非默认参数（AF_UNIX、非 SOCK_STREAM 等）的调用会回退到系统原始实现。

部署：把本文件复制到 venv 的 site-packages 目录（见项目 README）：
    Copy-Item compat\sitecustomize.py .venv\Lib\site-packages\sitecustomize.py -Force
"""

import socket as _sock

_orig_socketpair = _sock.socketpair


def _udp_socketpair(family=None, type=_sock.SOCK_STREAM, proto=0):
    fam = _sock.AF_INET if family is None else family
    if fam == _sock.AF_INET and type == _sock.SOCK_STREAM and proto == 0:
        for _ in range(5):
            try:
                a = _sock.socket(_sock.AF_INET, _sock.SOCK_DGRAM)
                try:
                    a.bind(("127.0.0.1", 0))
                    a.connect(a.getsockname())
                    b = a.dup()
                except BaseException:
                    a.close()
                    raise
                return a, b
            except OSError:
                continue  # 极端情况下 bind/dup 失败，短暂重试
    # 其他参数组合或多次失败：回退到系统原始实现
    return _orig_socketpair(fam, type, proto)


_sock.socketpair = _udp_socketpair
