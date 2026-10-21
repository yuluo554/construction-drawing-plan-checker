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

# --- RAG 依据挂载策略（v0.1.0 起）-----------------------------------------
# 知识库只覆盖"危大管理文件族"（37号令/31号文附件/48号指南），因此只有危大合规类
# 问题能挂条文；参数冲突、章节缺失、签署栏等没有对应条文，挂上去就是张冠李戴。
RAG_ELIGIBLE_TYPES = ("危大合规",)
# 相关性门槛：中文短查询 vs 条文长文本的余弦相似度普遍偏低，0.3 几乎什么都放进来
# （实测 R-C-001 曾以 0.3745 被挂上"超规模危大须专家论证"）。0.55 取自本仓
# 实测的匹配区间下沿，见 tools/bench_rag.py。
RAG_MIN_SCORE = 0.55


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

    # RAG 依据检索：只给"危大合规"类挂条文，且必须过相关性门槛
    if rag_on and kb is not None:
        from ..knowledge.rag import kb_search
        for f in findings:
            if f["级别"] != "致命" or f.get("条文"):
                continue
            if f.get("类型") not in RAG_ELIGIBLE_TYPES:
                # 明确记录"不适用"，而不是留空 dict 让人以为检索过但没结果
                f["条文"] = None
                f["条文检索"] = {"状态": "不适用", "原因": "知识库仅覆盖危大管理文件族，"
                                                     "%s类问题无对应条文" % f.get("类型", "该")}
                continue
            hits = kb_search(f.get("问题", ""), top_k=1, kb=kb, min_score=RAG_MIN_SCORE)
            if hits:
                f["条文"] = {"source": hits[0]["source"], "path": hits[0]["path"],
                             "score": hits[0]["score"],
                             "text": hits[0]["text"][:120]}
                f["条文检索"] = {"状态": "命中", "门槛": RAG_MIN_SCORE}
            else:
                f["条文"] = None
                f["条文检索"] = {"状态": "未检索到匹配条文", "门槛": RAG_MIN_SCORE,
                                "原因": "top1 相似度低于 %.2f" % RAG_MIN_SCORE}

    # 汇总
    summary = {"致命": 0, "一般": 0, "提示": 0}
    for f in findings:
        if f["级别"] in summary:
            summary[f["级别"]] += 1
    return {"findings": findings, "summary": summary,
            "结论": "存在致命问题，须整改后实施" if summary["致命"] else
                    ("有一般问题，建议完善" if summary["一般"] else "未发现问题线索")}
