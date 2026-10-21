# -*- coding: utf-8 -*-
"""运行期数据资产定位 —— 让"装完能用"与"源码态能用"走同一条代码路径。

背景（v0.1.0 的安装态缺陷，v0.1.1 修复）：
v0.1.0 的 wheel 只装 Python 包，`data/`、`code/knowledge/`、`code/backend/static/`
都没进去。于是 `pip install`（非 editable）之后：
    - `app.cli compliance` → FileNotFoundError: .../site-packages/data/法规标准/...json
    - `KB()` → chunks=0 且 **静默**返回空检索结果（--rag 挂不上任何条文却不报错）
    - Web 服务能启动但 `GET /` 没有 index.html、`/static/*` 全 404
v0.1.0 的 README 把这写成"按源码仓分发"，但 `pip install <sdist>` 是个正常用法，
装完不能用就是缺陷，不能靠文档免责。

本模块的约定：
1. **包内资产优先**：`app/_data/`（由 setup.py 的构建钩子从仓库复制，随 wheel/sdist 分发）
2. **仓库布局回退**：`code/backend/app` 的 4 级父目录（源码态 / editable 安装）
3. 两条路径都没有 → 抛 `AssetMissing`，**由调用方决定是失败还是降级**；
   绝不静默返回空（那是 v0.1.0 的 D1/D4 同款失效形态）。
"""
import os

# app/_data 下的相对布局（构建钩子按同一结构复制）
_PKG_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_data")

# 仓库布局：code/backend/app → 仓库根
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                          "..", "..", ".."))

# 逻辑名 → (包内相对路径, 仓库内相对路径)
_ASSETS = {
    "kb": ("knowledge/kb_weida.json", "code/knowledge/kb_weida.json"),
    "weida_list": ("data/法规标准/危大工程范围清单.json", "data/法规标准/危大工程范围清单.json"),
    "static": ("static", "code/backend/static"),
    "rules": ("rules", "code/rules"),
}


class AssetMissing(RuntimeError):
    """运行期资产（知识库 / 阈值清单 / Web 静态文件）找不到。"""


def _candidates(name):
    try:
        pkg_rel, repo_rel = _ASSETS[name]
    except KeyError:
        raise KeyError("未知资产名: %r（可用: %s）" % (name, ", ".join(sorted(_ASSETS))))
    return (os.path.join(_PKG_DATA, *pkg_rel.split("/")),
            os.path.join(_REPO_ROOT, *repo_rel.split("/")))


def asset_path(name, must_exist=True):
    """返回资产的绝对路径。

    must_exist=True（默认）时两条路径都找不到就抛 AssetMissing，错误信息里列出
    已尝试的路径与修复办法——不要返回 None 让上层静默降级。
    """
    pkg_path, repo_path = _candidates(name)
    for p in (pkg_path, repo_path):
        if os.path.exists(p):
            return p
    if not must_exist:
        return pkg_path
    raise AssetMissing(
        "缺少运行期资产 %r。已尝试：\n  - %s（wheel/sdist 内，由 setup.py 构建钩子生成）\n"
        "  - %s（仓库布局）\n"
        "修复：从源码安装时请用 `pip install -e .`（editable）或在仓库根执行 "
        "`python setup.py build_py` 后重装；若你拿到的是 wheel，说明构建时未包含资产，"
        "请改用 Release 的 source zip 或 sdist。" % (name, pkg_path, repo_path))


def asset_available(name):
    """资产是否可用（不抛异常，供"是否启用某功能"的判断使用）。"""
    try:
        asset_path(name)
        return True
    except AssetMissing:
        return False


def describe():
    """诊断用：列出每个资产的解析结果（供 `--selftest` 或排障打印）。"""
    out = []
    for name in sorted(_ASSETS):
        pkg_path, repo_path = _candidates(name)
        if os.path.exists(pkg_path):
            out.append((name, pkg_path, "package"))
        elif os.path.exists(repo_path):
            out.append((name, repo_path, "repo"))
        else:
            out.append((name, None, "missing"))
    return out
