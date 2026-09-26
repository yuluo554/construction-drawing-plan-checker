# -*- coding: utf-8 -*-
"""校核规则引擎 —— 汇总执行 三类检查，产出结构化校核报告（plan/03 §4）。

检查通道：
A. 一致性（图纸卡×方案卡，consistency.py）
B. 危大合规（阈值表驱动，weida.py）
C. 存在性（章节完整性/验算书/签署栏）
可选：RAG 依据检索（--rag），为冲突/危大项附规范条文引用。
"""
import re

from . import consistency
from .weida import full_compliance_check

_SIGN_RE = re.compile(r"编制[：:]|审核[：:]|批准[：:]|审批")
_CALC_RE = re.compile(r"计算书|验算")


def _existence_findings(pc):
    findings = []
    chap = full_compliance_check(pc)["章节完整性"]
    for miss in chap["缺失"]:
        findings.append({"rule_id": "R-E-001", "级别": "一般", "类型": "章节缺失",
                         "问题": "专项方案缺少标准章节：%s" % miss,
                         "方案": "章节树 %d 节" % len(pc.extras.get("outline", [])),
                         "依据": "建办质〔2021〕48号",
                         "建议": "按指南补充该章节内容"})
    if not any(_CALC_RE.search(p.value) for p in pc.parameters) and \
       not _CALC_RE.search(" ".join(o.get("title", "") for o in pc.extras.get("outline", []))):
        findings.append({"rule_id": "R-E-002", "级别": "一般", "类型": "验算书缺失",
                         "问题": "未检出计算书/验算内容",
                         "方案": "-", "依据": "48号指南(计算书及相关图纸)",
                         "建议": "附支撑体系计算书及相关图纸"})
    meta_text = " ".join(str(v) for v in pc.meta.values())
    if not _SIGN_RE.search(meta_text):
        findings.append({"rule_id": "R-E-003", "级别": "提示", "类型": "签署栏",
                         "问题": "首页未检出 编制/审核/批准 签署信息",
                         "方案": pc.meta.get("标题(首段)", "")[:40],
                         "依据": "37号令 第十一条",
                         "建议": "补全审批签署栏后实施"})
    return findings


def run_checks(drawing_card, plan_card, rag_on=False, kb=None):
    """返回校核报告 dict。"""
    findings = []

    # A 一致性（需两侧文档）
    if drawing_card is not None and plan_card is not None:
        findings += consistency.compare_cards(drawing_card, plan_card)

    # B 危大合规（方案侧）
    if plan_card is not None:
        comp = full_compliance_check(plan_card)
        for f in comp["危大判定"]:
            if f["级别"] == "非危大":
                continue
            ev = (f.get("证据") or [{}])[0]
            findings.append({
                "rule_id": "R-W-000", "级别": "致命", "类型": "危大合规",
                "问题": "%s：%s = %s%s（阈值 %s）" % (
                    f["级别"], f["param"], f["value"], "m", f.get("阈值", "-")),
                "方案": ev.get("原文", "")[:80] or "参数卡抽取",
                "依据": f.get("依据", ""),
                "建议": "编制专项施工方案" if f["级别"].startswith("危大")
                        else "编制专项施工方案并组织专家论证"})
        findings += _existence_findings(plan_card)

    # RAG 依据检索
    if rag_on and kb is not None:
        from ..knowledge.rag import kb_search
        for f in findings:
            if f["级别"] == "致命" and not f.get("条文"):
                hits = kb_search(f.get("问题", ""), top_k=1)
                if hits:
                    f["条文"] = {"source": hits[0]["source"], "path": hits[0]["path"],
                                 "score": hits[0]["score"],
                                 "text": hits[0]["text"][:120]}

    # 汇总
    summary = {"致命": 0, "一般": 0, "提示": 0}
    for f in findings:
        if f["级别"] in summary:
            summary[f["级别"]] += 1
    return {"findings": findings, "summary": summary,
            "结论": "存在致命问题，须整改后实施" if summary["致命"] else
                    ("有一般问题，建议完善" if summary["一般"] else "未发现问题线索")}
