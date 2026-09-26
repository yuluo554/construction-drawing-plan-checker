# -*- coding: utf-8 -*-
"""危大识别引擎 + 文档解析器集成测试（使用仓库真实数据）。

运行：cd code/backend && py -m pytest tests/ -q
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

REPO = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DATA = os.path.join(REPO, "data")

from app.parsers.docx_parser import parse_docx  # noqa: E402
from app.parsers.dxf_parser import parse_dxf  # noqa: E402
from app.parsers.pdf_parser import parse_pdf  # noqa: E402
from app.rules.weida import full_compliance_check  # noqa: E402
from app.schemas.parameter_card import ParameterCard, Parameter  # noqa: E402

GAOZHIMO_DOCX = os.path.join(DATA, "施工方案", "高支模专项施工方案样例(CallStorm-SmartReview仓库).docx")


# ---------- 危大引擎（合成参数卡） ----------

def _card_with(entity, attr, value, unit="m"):
    card = ParameterCard(doc_type="plan", file="synthetic")
    card.add(Parameter(entity=entity, category="measure", attr=attr, value=value,
                       unit=unit, source="plan"))
    return card


def test_pit_5m_is_super_scale():
    res = full_compliance_check(_card_with("基坑工程", "基坑开挖深度", "5.2"))
    hit = res["危大判定"][0]
    assert hit["级别"] == "超规模(须专家论证)"


def test_pit_2m_not_weida():
    res = full_compliance_check(_card_with("基坑工程", "基坑开挖深度", "2"))
    assert res["危大判定"][0]["级别"] == "非危大"


def test_formwork_8m_super_scale_and_6m_weida():
    r8 = full_compliance_check(_card_with("模板支撑体系", "支撑搭设高度", "8.5"))
    assert r8["危大判定"][0]["级别"] == "超规模(须专家论证)"
    r6 = full_compliance_check(_card_with("模板支撑体系", "支撑搭设高度", "6"))
    assert r6["危大判定"][0]["级别"] == "危大(须专项施工方案)"


def test_scaffold_30m_weida_not_super():
    res = full_compliance_check(_card_with("脚手架工程", "搭设高度", "30"))
    assert res["危大判定"][0]["级别"] == "危大(须专项施工方案)"


def test_chapter_missing_detection():
    card = ParameterCard(doc_type="plan", file="synthetic")
    card.extras["outline"] = [{"level": 1, "num": "一", "title": "工程概况"}]
    res = full_compliance_check(card)
    missing = res["章节完整性"]["缺失"]
    assert "应急处置" in missing and "计算书" in missing


# ---------- docx 真实文件 ----------

@pytest.mark.skipif(not os.path.exists(GAOZHIMO_DOCX), reason="样例方案不存在")
def test_docx_real_gaozhimo():
    card = parse_docx(GAOZHIMO_DOCX)
    assert card.extras["outline"], "应解析出章节树"
    assert len(card.extras["outline"]) >= 5
    assert card.extras["table_count"] >= 1
    attrs = {(p.entity, p.attr): p.value for p in card.parameters}
    # 高支模方案应能抽出 支撑/支模 高度 或 混凝土强度等级 至少其一
    has_height = any(k[1] in ("支撑搭设高度", "立杆间距", "搭设高度") for k in attrs)
    has_conc = any(k[1] == "强度等级" for k in attrs)
    assert has_height or has_conc, "至少应抽到 支撑高度 或 混凝土强度：" + json.dumps(
        list(attrs.items())[:20], ensure_ascii=False)


# ---------- DXF 真实文件 ----------

def test_dxf_real_libredwg():
    path = os.path.join(DATA, "CAD样例", "libredwg", "example_2000.dxf")
    if not os.path.exists(path):
        pytest.skip("DXF 样例不存在")
    card = parse_dxf(path)
    assert card.extras.get("text_count", 0) >= 0
    assert "DXF 读取失败" not in " ".join(card.warnings)


# ---------- PDF 合成样例（矢量路径） ----------

def test_pdf_synthetic_pingfa(tmp_path):
    import fitz
    pdf_path = str(tmp_path / "beam_drawing.pdf")
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "KL1(3) 300×600", fontsize=10, fontname="china-s")
    page.insert_text((72, 120), "Φ8@100/200(2) 2Φ22; 3Φ18", fontsize=10, fontname="china-s")
    page.insert_text((72, 140), "KZ1 600×600 24Φ22", fontsize=10, fontname="china-s")
    page.insert_text((72, 160), "混凝土强度等级为C35", fontsize=10, fontname="china-s")
    doc.save(pdf_path)

    card = parse_pdf(pdf_path)
    assert card.extras["vector"] is True
    attrs = {(p.entity, p.attr): p.value for p in card.parameters}
    assert attrs.get(("框架梁(KL1)", "截面")) == "300x600"
    assert attrs.get(("框架柱(KZ1)", "全部纵筋")) == "24Φ22"
    assert any(k[1] == "强度等级" and v == "C35" for k, v in attrs.items())
    # 证据 bbox 必须存在（前端高亮依赖）
    ev = card.parameters[0].evidence
    assert ev and ev.bbox and len(ev.bbox) == 4 and ev.page == 1
