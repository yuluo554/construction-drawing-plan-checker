# -*- coding: utf-8 -*-
"""控制台输出编码 —— 让含中文的输出在 Windows 默认代码页下不崩。

背景（v0.1.0 实测的 CI 失败）：`windows-latest` 上 `python -m app.cli --help`
因为帮助文本含中文、而 stdout 编码是 cp1252，抛 UnicodeEncodeError 直接退出 1。
这不是"CI 环境问题"——开发者在中文 Windows 的 cmd 里跑同样的命令也会崩。

用法：在每个可执行入口（CLI、bench 脚本）开头调一次 force_utf8_output()。
"""
import sys


def force_utf8_output():
    """把 stdout/stderr 切到 UTF-8（errors='replace' 兜底，避免二次崩溃）。"""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass  # 已被重定向到不支持改编码的对象时保持原样