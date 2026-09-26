# -*- coding: utf-8 -*-
"""一致性校验引擎 + 规则引擎 测试（合成参数卡，零 API 依赖）。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.rules import consistency  # noqa: E402
from app.rules.engine import run_checks  # noqa: E402
from app.schemas.parameter_card import Evidence, Parameter, ParameterCard  # noqa: E402


def _card():
    return ParameterCard(doc_type="drawing", file="syn")


def _p(card, entity, attr, value, unit="", category="material", source="drawing", raw=""):
    card.add(Parameter(entity=entity, category=category, attr=attr, value=value, unit=unit,
                       source=source, conf=1.0,
                       evidence=Evidence(doc="x", page=1, raw=raw or "%s=%s" % (attr, value))))


def test_grade_conflict_fatal():
    dc, pc = _card(), ParameterCard(doc_type="plan", file="syn2")
    _p(dc, "混凝土", "强度等级", "C35")
    _p(pc, "混凝土", "强度等级", "C30", source="plan")
    findings = consistency.compare_cards(dc, pc)
    assert any(f["级别"] == "致命" and f["rule_id"] == "R-C-001" for f in findings)


def test_grade_consistent_no_finding():
    dc, pc = _card(), ParameterCard(doc_type="plan", file="syn2")
    _p(dc, "混凝土", "强度等级", "C35")
    _p(pc, "混凝土", "强度等级", "C35", source="plan")
    assert not [f for f in consistency.compare_cards(dc, pc) if f["rule_id"] == "R-C-001"]


def test_grade_by_part_conflict():
    dc, pc = _card(), ParameterCard(doc_type="plan", file="syn2")
    _p(dc, "混凝土(基础底板)", "强度等级", "C35")
    _p(pc, "混凝土(基础底板)", "强度等级", "C30", source="plan")
    findings = consistency.compare_cards(dc, pc)
    assert any("基础底板" in f["问题"] for f in findings if f["级别"] == "致命")


def test_slab_thickness_unit_conversion():
    dc, pc = _card(), ParameterCard(doc_type="plan", file="syn2")
    _p(dc, "楼面板(LB1)", "板厚", "120", unit="mm", category="component")
    _p(pc, "模板支撑体系", "板厚", "0.12", unit="m", source="plan")
    assert not [f for f in consistency.compare_cards(dc, pc) if f["rule_id"] == "R-C-003"]
    # 换成不一致的单值 → 致命冲突
    pc2 = ParameterCard(doc_type="plan", file="syn3")
    _p(pc2, "模板支撑体系", "板厚", "0.15", unit="m", source="plan")
    findings = consistency.compare_cards(dc, pc2)
    assert any(f["rule_id"] == "R-C-003" and f["级别"] == "致命" for f in findings)


def test_multi_value_disambiguation():
    """方案多值 → 待人工确认（一般），不误报致命冲突。"""
    dc, pc = _card(), ParameterCard(doc_type="plan", file="syn2")
    _p(dc, "楼面板(LB1)", "板厚", "120", unit="mm", category="component")
    _p(pc, "模板支撑体系", "板厚", "0.12", unit="m", source="plan")
    _p(pc, "模板支撑体系", "板厚", "0.15", unit="m", source="plan")
    findings = consistency.compare_cards(dc, pc)
    assert any(f["rule_id"] == "R-C-020" and f["级别"] == "一般" for f in findings)
    assert not [f for f in findings if f["级别"] == "致命"]


def test_section_cited_missing():
    dc, pc = _card(), ParameterCard(doc_type="plan", file="syn2")
    _p(dc, "框架梁(KL1)", "截面", "300x600", category="component")
    _p(pc, "梁", "截面尺寸", "650x900", source="plan", category="component")
    findings = consistency.compare_cards(dc, pc)
    assert any(f["rule_id"] == "R-C-010" for f in findings)


def test_engine_summary_and_weida():
    dc, pc = _card(), ParameterCard(doc_type="plan", file="syn2")
    _p(dc, "混凝土", "强度等级", "C35")
    _p(pc, "混凝土", "强度等级", "C30", source="plan")
    _p(pc, "模板支撑体系", "支撑搭设高度", "8.5", unit="m", source="plan", category="measure")
    pc.extras["outline"] = [{"level": 1, "num": "一", "title": "工程概况"}]
    report = run_checks(dc, pc, rag_on=False)
    assert report["summary"]["致命"] >= 2          # 混凝土冲突 + 高支模超规模
    assert any(f["rule_id"] == "R-W-000" and "8.5" in f["问题"] for f in report["findings"])
    assert report["结论"].startswith("存在致命问题")


def test_engine_clean_project():
    dc, pc = _card(), ParameterCard(doc_type="plan", file="syn2")
    _p(dc, "混凝土", "强度等级", "C35")
    _p(pc, "混凝土", "强度等级", "C35", source="plan")
    pc.extras["outline"] = [{"level": 1, "num": "一", "title": "工程概况"},
                            {"level": 1, "num": "二", "title": "编制依据"},
                            {"level": 1, "num": "三", "title": "施工计划"},
                            {"level": 1, "num": "四", "title": "施工工艺技术"},
                            {"level": 1, "num": "五", "title": "施工安全保证措施"},
                            {"level": 1, "num": "六", "title": "施工管理及作业人员配备和分工"},
                            {"level": 1, "num": "七", "title": "验收要求"},
                            {"level": 1, "num": "八", "title": "应急处置措施"},
                            {"level": 1, "num": "九", "title": "计算书及相关图纸"}]
    pc.meta["编制：张三 审核：李四 批准：王五"] = ""
    report = run_checks(dc, pc, rag_on=False)
    assert report["summary"]["致命"] == 0
