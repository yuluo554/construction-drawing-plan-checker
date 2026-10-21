# -*- coding: utf-8 -*-
"""自述数字与台账一致性门禁（D3 / D7 的回归门）。

防的是三件事，都曾真实发生：
  1. README 写「876 字段」而实测 873（D3）——数字必须能被某条命令复现，且写明种子；
  2. data/README.md 的文件清单里出现磁盘上不存在的路径（D7）——台账要么真、要么标明"未入仓"；
  3. 测试数自述漂移——README 里的「N 项」必须等于实际收集数。

运行：cd code/backend && py -m pytest tests/test_self_reported_numbers.py -q
本文件只读文件、不跑重型基准（基准由 CI 的 bench 步骤守）。
"""
import json
import os
import re
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.normpath(os.path.join(BACKEND, "..", ".."))
README = os.path.join(REPO, "README.md")
DATA_README = os.path.join(REPO, "data", "README.md")
DATA = os.path.join(REPO, "data")


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def count_tests():
    """统计 tests/ 下的测试函数数（与 pytest 的收集口径一致：test_ 前缀的函数）。"""
    total = 0
    tdir = os.path.join(BACKEND, "tests")
    for name in sorted(os.listdir(tdir)):
        if not (name.startswith("test_") and name.endswith(".py")):
            continue
        src = read(os.path.join(tdir, name))
        total += len(re.findall(r"^def (test_\w+)", src, re.M))
    return total


# ---------- D3：README 的基准数字 ----------

def test_readme_has_no_stale_field_count():
    """旧自述 876 不可复现（实测 seed 1 → 873）；它不得再出现在 README。"""
    text = read(README)
    assert "876" not in text, "README 仍含不可复现的 876 字段（实测 seed 1 = 873）"


def test_readme_field_count_matches_bench_and_names_seed():
    """README 写出的 873 必须与种子写在同一行，且与真值口径（30 张 × beams×5 + columns×3）一致。"""
    text = read(README)
    assert "873" in text, "README 应写明实测字段数 873"
    lines = [ln for ln in text.splitlines() if "873" in ln]
    assert lines, "未能定位 873 所在行"
    # 种子可以写在数字前或后，只要同一行
    assert any(("seed 1" in ln) or ("seed1" in ln.lower()) for ln in lines), \
        "873 必须与种子写在同一行（bench_drawings 逐张递增种子，30 2 → 867）: %r" % lines


def test_bench_drawings_has_exit_gate():
    """D3 的根因之一是脚本没有退出码门——必须还在。"""
    src = read(os.path.join(BACKEND, "tools", "bench_drawings.py"))
    assert "sys.exit(main(" in src, "bench_drawings.py 缺 sys.exit(main(...))"
    assert "MIN_F1" in src


def test_bench_consistency_has_exit_gate():
    src = read(os.path.join(BACKEND, "tools", "bench_consistency.py"))
    assert "sys.exit(main(" in src, "bench_consistency.py 缺 sys.exit(main(...))"
    assert "MIN_WEIDA_RATE" in src


def test_readme_rag_band_matches_fixture():
    """README 写的检索相似度区间必须与探针夹具的实测值一致（防再次写错区间）。"""
    probes_path = os.path.join(REPO, "code", "knowledge", "rag_probes.json")
    if not os.path.exists(probes_path):
        pytest.skip("探针夹具缺失")
    with open(probes_path, "r", encoding="utf-8") as f:
        probes = json.load(f)
    scores = [p["expected_top1"] for p in probes.get("probes", [])]
    assert scores
    lo, hi = min(scores), max(scores)
    text = read(README)
    assert ("%.4f" % lo) in text or ("%.2f" % lo) in text, \
        "README 未写实测相似度下沿 %.4f" % lo
    assert ("%.4f" % hi) in text or ("%.2f" % hi) in text, \
        "README 未写实测相似度上沿 %.4f" % hi
    # 旧的 0.55–0.80 是"声称区间"，与实测不符，不得再作为结果出现
    assert "0.55–0.80" not in text and "0.55-0.80" not in text, \
        "README 仍含旧的声称区间 0.55–0.80（实测为 %.4f–%.4f）" % (lo, hi)


# ---------- 测试数自述 ----------

def test_readme_test_count_matches_collection():
    """README 里的「N 项 ... 测试」必须等于实际测试函数数。

    这条是自指门：每加一条测试都要同步 README 的数字。
    """
    text = read(README)
    m = re.search(r"运行测试（(\d+)\s*项", text)
    assert m, "README 快速开始里应写明「运行测试（N 项...」"
    claimed = int(m.group(1))
    actual = count_tests()
    assert claimed == actual, "README 写 %d 项，实际 %d 项（同步 README）" % (claimed, actual)


def test_readme_dir_tree_test_count_matches_collection():
    text = read(README)
    m = re.search(r"(\d+)\s*项单元/集成测试", text)
    assert m, "README 目录结构里应写明「N 项单元/集成测试」"
    claimed = int(m.group(1))
    actual = count_tests()
    assert claimed == actual, "目录结构写 %d 项，实际 %d 项" % (claimed, actual)


# ---------- D7：data/README.md 的文件清单 ----------

LISTED_RE = re.compile(r"^\|\s*`([^`]+)`\s*\|", re.M)


def _listed_paths():
    """从 data/README.md 的表格里抽出被反引号包裹的路径（可能是通配/目录）。"""
    out = []
    for raw in LISTED_RE.findall(read(DATA_README)):
        if "/" not in raw:      # 不是路径（例如纯文件名关键词）
            continue
        out.append(raw.strip())
    return out


def test_data_readme_listed_paths_exist_or_declared_absent():
    """台账里出现的每个路径，要么在磁盘上，要么该行显式声明「未随仓库分发」。"""
    lines = read(DATA_README).splitlines()
    missing = []
    for line in lines:
        m = LISTED_RE.match(line)
        if not m:
            continue
        raw = m.group(1).strip()
        if "/" not in raw:
            continue
        if "未随仓库分发" in line or "未入仓" in line:
            continue
        parts = [p for p in raw.split("/") if p]
        if raw.endswith("/"):
            # 目录条目：整个路径就是目录
            if not os.path.isdir(os.path.join(DATA, *parts)):
                missing.append(raw)
            continue
        parent = os.path.join(DATA, *parts[:-1])
        leaf = parts[-1]
        if not os.path.isdir(parent):
            missing.append(raw)
            continue
        names = os.listdir(parent)
        if "*" in leaf or "..." in leaf:
            # 通配或省略号缩写（如 `xxx-...编制指南.docx`）：只要父目录有前缀匹配即可
            prefix = leaf.split("*")[0].split("...")[0]
            suffix = leaf.rsplit("*")[-1].split("...")[-1]
            ok = any(n.startswith(prefix) and n.endswith(suffix) for n in names)
        else:
            ok = leaf in names
        if not ok:
            missing.append(raw)
    assert not missing, "台账列出但磁盘不存在、且未声明未入仓：%r" % missing


def test_data_readme_declares_local_only_docx():
    """含真实联系人信息的 docx 必须继续被声明为「未随仓库分发」。"""
    text = read(DATA_README)
    assert "未随仓库分发" in text
    assert "高支模专项施工方案样例" in text


# ---------- D6：数据文件的复核元数据 ----------

def test_weida_list_has_review_metadata():
    path = os.path.join(DATA, "法规标准", "危大工程范围清单.json")
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    review = d.get("_复核") or {}
    assert review.get("reviewed_on"), "危大工程范围清单.json 缺 _复核.reviewed_on"
    assert review.get("next_review_due"), "危大工程范围清单.json 缺 _复核.next_review_due"
    # 阈值清单本身未被动过：附件1/附件2 各 7 条
    assert len(d["危大工程范围_附件1"]) == 7
    assert len(d["超过一定规模_附件2_须专家论证"]) == 7


def test_kb_has_generation_metadata():
    path = os.path.join(REPO, "code", "knowledge", "kb_weida.json")
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    meta = d.get("_meta") or {}
    assert meta.get("generated_at"), "kb_weida.json 缺 _meta.generated_at"
    assert meta.get("model_version"), "kb_weida.json 缺 _meta.model_version"
    assert len(d["chunks"]) == len(d["vectors"]) == meta.get("chunks"), \
        "chunks/vectors 条数与 _meta 不一致"
    assert len(d["vectors"][0]) == 1024, "向量维度应为 1024"
