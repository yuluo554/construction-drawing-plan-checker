# -*- coding: utf-8 -*-
"""CLI 退出码回归测试（D1）：失败必须非 0，成功必须 0。

用 subprocess 跑真实进程取退出码——不 mock、不看 stdout，因为本仓的原始缺陷
恰恰是"打印正常但 exit 0"。约定：0=成功、1=运行失败、2=用法/输入不可用。

运行：cd code/backend && py -m pytest tests/test_cli_exit_codes.py -q
"""
import os
import subprocess
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.normpath(os.path.join(BACKEND, "..", ".."))
DRAWING = os.path.join(REPO, "data", "施工图纸", "自制样例", "sample_beam_plan.dxf")
PLAN = os.path.join(REPO, "data", "施工方案", "自制样例", "sample_formwork_plan_13.docx")
HAS_PAIR = os.path.exists(DRAWING) and os.path.exists(PLAN)


def run_cli(*args, cwd=BACKEND, env_extra=None):
    """跑 `python -m app.cli ...`，返回 (退出码, 合并输出)。"""
    env = dict(os.environ)
    env.setdefault("PYTHONUTF8", "1")
    env.pop("PYTHONPATH", None)
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run([sys.executable, "-m", "app.cli"] + list(args),
                          cwd=cwd, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, timeout=300)
    out = proc.stdout.decode("utf-8", "replace")
    return proc.returncode, out


# ---------- 输入不可用 → 2 ----------

def test_run_missing_inputs_exit_2(tmp_path):
    rc, out = run_cli("run", str(tmp_path / "nope.dxf"), str(tmp_path / "nope.docx"),
                      "-o", str(tmp_path / "out"))
    assert rc == 2, out
    assert not (tmp_path / "out").exists(), "输入不可用时不应创建产物目录"


def test_drawing_missing_file_exit_2(tmp_path):
    rc, out = run_cli("drawing", str(tmp_path / "nope.dxf"))
    assert rc == 2, out


def test_plan_missing_file_exit_2(tmp_path):
    rc, out = run_cli("plan", str(tmp_path / "nope.docx"))
    assert rc == 2, out


def test_unknown_subcommand_exit_2():
    rc, out = run_cli("nosuch")
    assert rc == 2, out


# ---------- 解析静默失败 → 1 ----------

def test_drawing_corrupt_file_exit_1(tmp_path):
    """坏 DXF 会让解析器返回空卡（只记 warnings）；必须当失败，不能报成功。"""
    bad = tmp_path / "bad.dxf"
    bad.write_text("not a real dxf at all", encoding="utf-8")
    rc, out = run_cli("drawing", str(bad))
    assert rc == 1, out


def test_plan_corrupt_file_exit_1(tmp_path):
    bad = tmp_path / "bad.docx"
    bad.write_text("not a docx", encoding="utf-8")
    rc, out = run_cli("plan", str(bad))
    assert rc == 1, out


# ---------- 缺 embedding 配置时的 --rag → 2（不等 check 节点崩） ----------

@pytest.mark.skipif(not HAS_PAIR, reason="配对演示数据缺失")
def test_run_rag_without_env_exit_2(tmp_path):
    """清空 LLM_* 环境变量并指向一个不存在的 .env，模拟"无 Key 的干净机器"。

    原缺陷：check 节点抛 MissingSchema、产物目录为空，但退出码 0。
    """
    empty_env = tmp_path / "empty.env"
    empty_env.write_text("", encoding="utf-8")
    rc, out = run_cli("run", DRAWING, PLAN, "-o", str(tmp_path / "out"), "--rag",
                      cwd=tmp_path, env_extra={"LLM_API_KEY": "", "LLM_BASE_URL": "",
                                               "LLM_MODEL": "", "PYTHONPATH": BACKEND})
    assert rc == 2, out
    assert "LLM_BASE_URL" in out or "LLM_API_KEY" in out, out
    assert "--rag" in out, "应给出可执行指引（去掉 --rag 或补 .env）"


# ---------- 正控：正常路径仍然 0 且真产出两份文件 ----------

@pytest.mark.skipif(not HAS_PAIR, reason="配对演示数据缺失")
def test_run_valid_pair_exit_0(tmp_path):
    out_dir = tmp_path / "out"
    rc, out = run_cli("run", DRAWING, PLAN, "-o", str(out_dir))
    assert rc == 0, out
    assert (out_dir / "校核结果.json").is_file(), out
    assert (out_dir / "校核报告.docx").is_file(), out
    assert "存在致命问题" in out, out


# ---------- 基准脚本的退出码门（D3） ----------

def test_bench_drawings_pass_and_negative_control():
    """门槛达标 → 0；把门槛提到 1.01（不可达）→ 必须 1。"""
    rc, out = run_cli_script("tools/bench_drawings.py", "3", "1")
    assert rc == 0, out

    rc, out = run_cli_script("tools/bench_drawings.py", "3", "1", "--min-f1", "1.01")
    assert rc == 1, out
    assert "FAIL" in out, out


def test_bench_consistency_pass():
    rc, out = run_cli_script("tools/bench_consistency.py", "3", "1")
    assert rc == 0, out
    assert "PASS" in out, out


# ---------- 非 UTF-8 控制台（Windows 默认代码页）下的中文输出 ----------

LEGACY_CODEC = "cp1252"


def _run_under_legacy_codepage(cmd):
    """用 PYTHONIOENCODING 强制非 UTF-8 控制台跑一条命令，返回 (rc, 输出)。"""
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = LEGACY_CODEC     # 覆盖入口处 reconfigure 之前的状态
    env["PYTHONUTF8"] = "0"                    # 关闭 UTF-8 模式，逼近 Windows 默认
    env.pop("PYTHONPATH", None)
    proc = subprocess.run([sys.executable] + cmd, cwd=BACKEND, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
    return proc.returncode, proc.stdout.decode("utf-8", "replace")


def test_cli_help_survives_legacy_codepage():
    """CI 曾在 windows-latest 上因 cp1252 输出中文而红（UnicodeEncodeError）。

    这里用 PYTHONIOENCODING 强制非 UTF-8 控制台，断言入口处已把编码切成 UTF-8。
    负控：移除 app/cli.py 里的 force_utf8_output() 调用后本测试变红。
    """
    rc, out = _run_under_legacy_codepage(["-m", "app.cli", "--help"])
    assert "UnicodeEncodeError" not in out, out
    assert "charmap" not in out, out
    assert rc == 0, out


def test_bench_rag_survives_legacy_codepage():
    """bench_rag 输出含中文，同样必须在非 UTF-8 控制台下可跑（CI windows 腿覆盖）。"""
    rc, out = _run_under_legacy_codepage(["tools/bench_rag.py"])
    assert "UnicodeEncodeError" not in out, out
    assert "charmap" not in out, out
    assert rc == 0, out


def test_console_helper_reconfigures_streams():
    """直接单测 helper：断言它把流切成 UTF-8（不依赖子进程行为）。"""
    import io
    import sys as _sys
    from app.console import force_utf8_output
    buf = io.TextIOWrapper(io.BytesIO(), encoding=LEGACY_CODEC, errors="strict")
    saved = _sys.stdout
    _sys.stdout = buf
    try:
        force_utf8_output()
        assert buf.encoding.lower().replace("-", "") == "utf8", buf.encoding
    finally:
        _sys.stdout = saved


def run_cli_script(script, *args):
    env = dict(os.environ)
    env.setdefault("PYTHONUTF8", "1")
    env.pop("PYTHONPATH", None)
    proc = subprocess.run([sys.executable, script] + list(args), cwd=BACKEND, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600)
    return proc.returncode, proc.stdout.decode("utf-8", "replace")
