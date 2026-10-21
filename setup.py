# -*- coding: utf-8 -*-
"""构建钩子：把运行期资产复制进 app/_data/，让 wheel 与 sdist 装完即可用。

v0.1.0 的缺陷（v0.1.1 修）：wheel 只含 Python 包，`data/`、`code/knowledge/`、
`code/backend/static/` 都没进去 → `pip install` 后 compliance 报 FileNotFoundError、
KB() 静默返回空检索、Web 首页 404。当时用"按源码仓分发"在文档里免责，但
`pip install <sdist/wheel>` 是正常用法，装完不能用就是缺陷。

做法：在 `build_py`（wheel/sdist 都经过它）里把三类资产复制到 `app/_data/`，
布局与 app/resources.py 的约定一致：
    app/_data/knowledge/kb_weida.json
    app/_data/data/法规标准/危大工程范围清单.json
    app/_data/static/{index.html,app.js,style.css,vendor/*}
    app/_data/rules/*.json
`app/_data` 是**构建产物**，不入库（见 .gitignore），避免仓库里出现两份副本。
"""
import os
import shutil

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py

HERE = os.path.dirname(os.path.abspath(__file__))
PKG_DIR = os.path.join(HERE, "code", "backend", "app")
PKG_DATA = os.path.join(PKG_DIR, "_data")

# (源, 目标相对 app/_data 的路径, 是否目录)
ASSETS = [
    (os.path.join(HERE, "code", "knowledge", "kb_weida.json"), "knowledge/kb_weida.json", False),
    (os.path.join(HERE, "data", "法规标准", "危大工程范围清单.json"),
     "data/法规标准/危大工程范围清单.json", False),
    (os.path.join(HERE, "code", "backend", "static"), "static", True),
    (os.path.join(HERE, "code", "rules"), "rules", True),
]


def _stage_assets(verbose=True):
    """把资产复制到 app/_data/；缺任何一项都直接报错（不允许"悄悄少装"）。"""
    missing = [src for src, _, _ in ASSETS if not os.path.exists(src)]
    if missing:
        raise SystemExit(
            "构建失败：找不到运行期资产，无法生成可用安装包：\n  "
            + "\n  ".join(missing)
            + "\n（这些文件必须在仓库里；wheel 缺它们会导致装完不能用）")
    if os.path.isdir(PKG_DATA):
        shutil.rmtree(PKG_DATA)
    for src, rel, is_dir in ASSETS:
        dst = os.path.join(PKG_DATA, *rel.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if is_dir:
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(src, dst)
        if verbose:
            print("staged asset ->", os.path.relpath(dst, HERE))


class build_py(_build_py):
    """先铺资产，再按常规收集包（资产随后被 package_data 收进 wheel）。"""

    def run(self):
        _stage_assets()
        super().run()

    def get_data_files(self):
        # 确保 app/_data 在 build_py 的 data_files 里（package_data 生效前先生成文件）
        files = super().get_data_files()
        return files


setup(cmdclass={"build_py": build_py})
