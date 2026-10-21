# -*- coding: utf-8 -*-
"""安装态（非 editable）资产可用性测试 —— v0.1.0 的装态缺陷回归门。

v0.1.0 的 wheel 只含 Python 包，`data/`、`code/knowledge/`、`code/backend/static/`
都没进去，于是 `pip install` 之后：
    compliance → FileNotFoundError
    KB()       → chunks=0 且**静默**返回空检索（--rag 挂不上条文却不报错）
    Web        → 服务能起但首页 404

本文件的测试分两类：
  1. **源码态**（一定跑）：resources 的解析顺序、缺失时抛 AssetMissing、selftest 输出。
  2. **安装态**（慢，标 packaging）：真的构建 wheel → 装进临时 venv → 在**仓库外**的
     cwd 跑 `selftest` 与 `compliance`，断言用的是包内资产（而不是仓库回退）。

运行：cd code/backend && py -m pytest tests/test_packaging.py -q
只跑快的：py -m pytest tests/ -q -m "not packaging"
"""
import json
import os
import subprocess
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.normpath(os.path.join(BACKEND, "..", ".."))
PLAN_CARD = os.path.join(REPO, "data", "施工方案", "自制样例", "参数卡_plan_13.json")


def _clean_staged_assets():
    """删掉上次构建留下的 app/_data，避免"陈旧产物"掩盖构建钩子失效。

    实测踩过：`app/_data` 已存在时，即使 build_py 不铺资产，package-data 也会把它
    收进 wheel → 负控（关掉钩子）不会变红。所以每次构建前必须清干净。
    """
    import shutil
    staged = os.path.join(BACKEND, "app", "_data")
    if os.path.isdir(staged):
        shutil.rmtree(staged, ignore_errors=True)
    return staged


def run_py(py, *args, cwd=None, env_extra=None, timeout=600):
    env = dict(os.environ)
    env.setdefault("PYTHONUTF8", "1")
    env.pop("PYTHONPATH", None)
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run([py] + list(args), cwd=cwd, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    return proc.returncode, proc.stdout.decode("utf-8", "replace")


# ---------------- 1. 源码态：资源解析 ----------------

def test_asset_path_resolves_all_known_assets():
    from app.resources import asset_path
    for name in ("kb", "weida_list", "static", "rules"):
        p = asset_path(name)
        assert os.path.exists(p), name


def test_asset_path_raises_for_unknown_name():
    from app.resources import asset_path
    with pytest.raises(KeyError):
        asset_path("no-such-asset")


def test_missing_asset_raises_with_actionable_message(tmp_path, monkeypatch):
    """资产缺失必须抛 AssetMissing，且消息里含"已尝试的路径 + 修复办法"。

    这是 v0.1.0 的核心教训：KB() 原本静默变成空索引。
    """
    from app import resources
    # 把两条候选路径都指到不存在的位置
    monkeypatch.setattr(resources, "_PKG_DATA", str(tmp_path / "no-pkg"))
    monkeypatch.setattr(resources, "_REPO_ROOT", str(tmp_path / "no-repo"))
    with pytest.raises(resources.AssetMissing) as ei:
        resources.asset_path("kb")
    msg = str(ei.value)
    assert "kb" in msg
    assert "已尝试" in msg
    assert "修复" in msg


def test_kb_raises_instead_of_silently_empty(tmp_path, monkeypatch):
    """KB() 在知识库缺失时必须抛，不得返回 chunks=[] 的空索引。"""
    from app import resources
    from app.knowledge.rag import KB
    monkeypatch.setattr(resources, "_PKG_DATA", str(tmp_path / "no-pkg"))
    monkeypatch.setattr(resources, "_REPO_ROOT", str(tmp_path / "no-repo"))
    with pytest.raises(resources.AssetMissing):
        KB()


def test_kb_loads_expected_shape():
    from app.knowledge.rag import KB
    kb = KB()
    assert len(kb.chunks) == len(kb.vectors) == 55
    assert len(kb.vectors[0]) == 1024


def test_weida_list_loads_from_asset_resolution():
    from app.rules.weida import load_list
    spec = load_list()
    assert len(spec["危大工程范围_附件1"]) == 7
    assert len(spec["超过一定规模_附件2_须专家论证"]) == 7


def test_selftest_passes_in_source_tree():
    rc, out = run_py(sys.executable, "-m", "app.cli", "selftest", cwd=BACKEND)
    assert rc == 0, out
    assert "全部可用" in out, out
    # 源码态应命中"仓库"回退（除非构建过 _data，那时命中"包内"也算对）
    assert ("OK(仓库)" in out) or ("OK(包内)" in out), out


def test_selftest_fails_when_asset_missing(tmp_path):
    """负控：把两条候选路径都指空后，selftest 必须 rc=1 并列出 MISSING。"""
    from app import resources
    saved = (resources._PKG_DATA, resources._REPO_ROOT)
    resources._PKG_DATA = str(tmp_path / "no-pkg")
    resources._REPO_ROOT = str(tmp_path / "no-repo")
    try:
        from app.cli import _cmd_selftest
        rc = _cmd_selftest(None)
    finally:
        resources._PKG_DATA, resources._REPO_ROOT = saved
    assert rc == 1


def test_web_index_available_in_source_tree():
    """server 的静态目录解析必须能找到 index.html。

    注意：STATIC_DIR 是模块级常量（import 时算一次）。前面若有测试 monkeypatch 过
    resources 的候选路径，这里要用 `_resolve_static_dir()` 重算，而不是读旧常量。
    """
    from app import server
    d = server._resolve_static_dir()
    assert d, "应能解析到 static（源码态回退仓库、构建后命中包内）"
    assert os.path.isfile(os.path.join(d, "index.html"))


def test_static_assets_referenced_by_html_exist():
    """index.html 引用的本地资源必须真实存在（防"死引用"）。

    只检查静态文件类引用：跳过 http(s) 外链、`#` 锚点，以及运行时拼接的 API 路径。
    """
    import re
    from app.resources import asset_path
    static = asset_path("static")
    html = open(os.path.join(static, "index.html"), encoding="utf-8").read()
    refs = re.findall(r'(?:src|href)="([^"]+)"', html)
    missing = []
    for r in refs:
        if r.startswith(("http://", "https://", "#", "/api/")):
            continue
        if not r.endswith((".js", ".css", ".png", ".svg", ".ico", ".jpg")):
            continue          # 跳过模板/拼接表达式
        if "'" in r or "+" in r:
            continue
        rel = r.lstrip("/")
        if rel.startswith("static/"):
            rel = rel[len("static/"):]
        if not os.path.exists(os.path.join(static, rel)):
            missing.append(r)
    assert not missing, "index.html 引用了不存在的资源: %r" % missing


# ---------------- 2. 安装态（慢）：真构建 + 真装 + 仓库外跑 ----------------

@pytest.mark.packaging
def test_wheel_contains_runtime_assets(tmp_path):
    """构建 wheel，断言四类资产都在包里（而不是只在仓库里）。"""
    import zipfile
    _clean_staged_assets()          # 防陈旧 _data 掩盖构建钩子失效
    rc, out = run_py(sys.executable, "-m", "build", "--wheel",
                     "--outdir", str(tmp_path), cwd=REPO, timeout=900)
    assert rc == 0, out
    wheels = [n for n in os.listdir(str(tmp_path)) if n.endswith(".whl")]
    assert wheels, out
    with zipfile.ZipFile(os.path.join(str(tmp_path), wheels[0])) as z:
        names = z.namelist()
    for needle in ("app/_data/knowledge/kb_weida.json",
                   "app/_data/data/法规标准/危大工程范围清单.json",
                   "app/_data/static/index.html",
                   "app/_data/static/vendor/pdf.worker.min.js",
                   "app/_data/rules/checks.json"):
        assert any(needle in n for n in names), "wheel 缺 %s" % needle


@pytest.mark.packaging
@pytest.mark.skipif(os.name != "nt" and not os.path.exists("/usr/bin/python3"),
                    reason="需要可创建 venv 的 python")
def test_installed_wheel_works_outside_repo(tmp_path):
    """装进临时 venv，在**仓库外**的 cwd 跑 selftest 与 compliance。

    关键断言：selftest 报告资产来自"包内"（OK(包内)）——若显示"仓库"说明解析退回了
    源码布局，那就没真正验证 wheel 自足性。
    """
    import venv
    _clean_staged_assets()          # 防陈旧 _data 掩盖构建钩子失效
    rc, out = run_py(sys.executable, "-m", "build", "--wheel",
                     "--outdir", str(tmp_path / "dist"), cwd=REPO, timeout=900)
    assert rc == 0, out
    wheel = os.path.join(str(tmp_path / "dist"),
                         [n for n in os.listdir(str(tmp_path / "dist")) if n.endswith(".whl")][0])

    envdir = tmp_path / "venv"
    venv.create(str(envdir), with_pip=True)
    py = os.path.join(str(envdir), "Scripts" if os.name == "nt" else "bin",
                      "python.exe" if os.name == "nt" else "python")

    rc, out = run_py(py, "-m", "pip", "install", "-q", "--disable-pip-version-check", wheel,
                     timeout=900)
    assert rc == 0, out

    outside = tmp_path / "outside"
    outside.mkdir()
    rc, out = run_py(py, "-m", "app.cli", "selftest", cwd=str(outside))
    assert rc == 0, out
    assert "OK(包内)" in out, "资产未从包内解析（wheel 不自足）:\n" + out
    assert "MISSING" not in out, out

    if os.path.exists(PLAN_CARD):
        rc, out = run_py(py, "-m", "app.cli", "compliance", PLAN_CARD, cwd=str(outside))
        assert rc == 0, out
        data = json.loads(out[out.index("{"):])
        assert data["危大判定"], out
