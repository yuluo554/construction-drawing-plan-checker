# -*- coding: utf-8 -*-
"""危大工程识别引擎 —— 基于 data/法规标准/危大工程范围清单.json 的阈值判定。

输入：方案参数卡（含 脚手架/基坑/模板支撑 参数）；
输出：判定列表（非危大/危大→专项方案/超规模→专家论证），附依据与证据。
另含：专项方案章节完整性检查（对照建办质〔2021〕48号 指南的标准章节）。
"""
import json
import os

# 我方参数卡 (entity, attr) → 清单 param 名
PARAM_MAP = {
    ("基坑工程", "基坑开挖深度"): "基坑开挖深度",
    ("模板支撑体系", "支撑搭设高度"): "模板支撑体系搭设高度",
    ("脚手架工程", "搭设高度"): "落地式钢管脚手架搭设高度",
}

# 建办质〔2021〕48号 指南对专项方案内容的标准章节（同义词组任一命中即算覆盖）
REQUIRED_CHAPTER_KEYWORDS = [
    ("工程概况",),
    ("编制依据", "编制说明"),
    ("施工计划", "进度计划"),
    ("施工工艺", "工艺流程", "施工方案", "施工技术"),
    ("施工安全保证", "安全管理", "安全保证措施", "安全措施"),
    ("验收",),
    ("应急处置", "应急预案", "应急措施"),
    ("计算书", "计算"),
    ("施工管理", "管理及作业人员"),
]

DEFAULT_LIST_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "data",
                                 "法规标准", "危大工程范围清单.json")


def load_list(path=None):
    p = os.path.normpath(path or DEFAULT_LIST_PATH)
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _to_float(v):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def _iter_conditions(rule):
    """展开 触发条件（含 combine.any 嵌套 rules）→ 产出平铺的阈值条件。"""
    for cond in rule.get("触发条件", []):
        if isinstance(cond.get("rules"), list):
            for sub in cond["rules"]:
                yield sub
        else:
            yield cond


def evaluate_weida(card, list_path=None):
    """返回 findings 列表：{级别, 类别, 判定, 阈值, 实际值, 依据, 证据章节}。"""
    spec = load_list(list_path)
    findings = []

    # 收集卡内可判定参数
    measured = {}
    for p in card.parameters:
        key = PARAM_MAP.get((p.entity, p.attr))
        if key:
            val = _to_float(p.value)
            if val is not None and (p.unit or "m") in ("m", "米"):
                measured.setdefault(key, []).append({"value": val, "sec": p.evidence.section if p.evidence else "",
                                                     "raw": p.evidence.raw if p.evidence else ""})

    rules1 = spec.get("危大工程范围_附件1", [])
    rules2 = spec.get("超过一定规模_附件2_须专家论证", [])
    ids2 = {id(r) for r in rules2}

    for param_name, samples in measured.items():
        val = max(s["value"] for s in samples)  # 取最不利（最大值）判定
        hit = {"级别": "非危大", "param": param_name, "value": val}
        for r in rules1 + rules2:
            for cond in _iter_conditions(r):
                if cond.get("param") != param_name:
                    continue
                th = cond.get("value")
                op = cond.get("op", ">=")
                if th is None or not isinstance(th, (int, float)):
                    continue
                matched = (val >= th) if op == ">=" else (val > th)
                if matched:
                    level = "超规模(须专家论证)" if id(r) in ids2 else "危大(须专项施工方案)"
                    if level == "超规模(须专家论证)" or hit["级别"] != "超规模(须专家论证)":
                        hit = {"级别": level, "param": param_name, "value": val,
                               "阈值": th, "类别": r.get("类别"),
                               "依据": "住建部令第37号/建办质〔2018〕31号 " + r.get("类别", ""),
                               "证据": [{"章节": s["sec"], "原文": s["raw"][:60]} for s in samples]}
        findings.append(hit)

    return findings


def check_chapters(card):
    """专项方案章节完整性（对照 48号指南标准内容，同义词组任一命中即覆盖）。"""
    outline = [o.get("title", "") for o in card.extras.get("outline", [])]
    all_titles = " ".join(outline)
    missing = []
    for group in REQUIRED_CHAPTER_KEYWORDS:
        if not any(kw in all_titles or kw in card.meta.get("标题(首段)", "") for kw in group):
            missing.append(group[0])
    return {"应含章节": [list(g) for g in REQUIRED_CHAPTER_KEYWORDS],
            "缺失": missing,
            "说明": "依据建办质〔2021〕48号《危大工程专项施工方案编制指南》"}


def full_compliance_check(card, list_path=None):
    return {
        "危大判定": evaluate_weida(card, list_path),
        "章节完整性": check_chapters(card),
    }
