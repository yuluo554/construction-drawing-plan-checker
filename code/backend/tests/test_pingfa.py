# -*- coding: utf-8 -*-
"""平法标注解析器单元测试。运行：py -m pytest backend/tests/test_pingfa.py -q"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.parsers.pingfa import parse_beam_tag, parse_column_tag, parse_slab_tag, parse_material  # noqa: E402


def test_beam_full():
    params = parse_beam_tag("KL1(3) 300×600 Φ8@100/200(2) 2Φ22; 3Φ18 G4Φ12")
    got = {(p.entity, p.attr): p.value for p in params}
    assert got[("框架梁(KL1)", "编号")] == "KL1"
    assert got[("框架梁(KL1)", "跨数")] == "3"
    assert got[("框架梁(KL1)", "截面")] == "300x600"
    assert "Φ8@100/200" in got[("框架梁(KL1)", "箍筋")]
    assert got[("框架梁(KL1)", "上部通长筋")] == "2Φ22"
    assert got[("框架梁(KL1)", "下部纵筋")] == "3Φ18"
    assert got[("框架梁(KL1)", "构造腰筋")] == "4Φ12"


def test_beam_g4_not_as_longitudinal():
    """腰筋 G4Φ12 不得误判为上部通长筋。"""
    params = parse_beam_tag("L2 200×400 G4Φ12")
    attrs = [p.attr for p in params]
    assert "上部通长筋" not in attrs
    assert "构造腰筋" in attrs


def test_column_full():
    params = parse_column_tag("KZ1 600×600 24Φ22 8Φ20(角筋) Φ10@100/200(4)")
    got = {(p.entity, p.attr): p.value for p in params}
    assert got[("框架柱(KZ1)", "截面")] == "600x600"
    assert got[("框架柱(KZ1)", "全部纵筋")] == "24Φ22"
    assert got[("框架柱(KZ1)", "角筋")] == "8Φ20"
    assert "Φ10@100/200" in got[("框架柱(KZ1)", "箍筋")]


def test_slab():
    params = parse_slab_tag("LB1 h=120 B: XΦ12@150 YΦ10@180 T: XΦ12@150")
    got = {(p.entity, p.attr): p.value for p in params}
    assert got[("楼面板(LB1)", "板厚")] == "120"
    assert "XΦ12@150" in got[("楼面板(LB1)", "底部配筋")]


def test_material():
    params = parse_material("混凝土强度等级：基础底板C35，其余C30；保护层厚度为25mm")
    vals = [(p.entity, p.attr, p.value) for p in params]
    assert ("混凝土(基础底板)", "强度等级", "C35") in vals
    assert ("钢筋混凝土", "保护层厚度", "25") in vals


def test_invalid_rejected():
    """非法值（超范围截面）应被丢弃。"""
    assert parse_beam_tag("KL9 99999×2 Φ8@1/1 99Φ99") == [] or all(
        p.attr in ("编号",) for p in parse_beam_tag("KL9 50×100"))
