# -*- coding: utf-8 -*-
"""图纸参数卡 × 方案参数卡 一致性校验引擎（plan/03 §4.1）。

对齐策略：
1. 实体归一（别名/部位）→ 2. 属性对齐 → 3. 数值单位换算比对 → 4. 差异分级（致命/一般/提示）
每条 finding 携带 双侧证据，可溯源。
"""
import re

from ..schemas.parameter_card import ParameterCard

ALIAS = {
    "砼": "混凝土", "砼强度": "混凝土强度", "垫层": "垫层混凝土",
}
ATTR_ALIAS = {
    "强度等级": ["强度等级", "混凝土强度等级", "等级"],
    "板厚": ["板厚", "楼板厚度", "板厚度"],
    "保护层厚度": ["保护层厚度"],
    "支撑搭设高度": ["支撑搭设高度", "支架高度", "支模高度", "模板支架高度"],
    "立杆间距": ["立杆间距", "立杆纵横距"],
    "步距": ["步距", "水平杆步距"],
}


def _norm(s):
    s = str(s or "").strip()
    for k, v in ALIAS.items():
        s = s.replace(k, v)
    return s


def _canonical_attr(attr):
    a = _norm(attr)
    for canon, aliases in ATTR_ALIAS.items():
        if a in aliases:
            return canon
    return a


def _mm(value, unit):
    """数值 → mm（无法解析返回 None）。"""
    try:
        v = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    u = (unit or "mm").strip().lower()
    if u in ("m", "米"):
        return v * 1000.0
    if u in ("mm", "毫米", ""):
        return v
    return None


def _grade(v):
    m = re.search(r"C\d{2,3}", str(v), re.I)
    return m.group(0).upper() if m else None


def _by_attr(card, attr_canon, category=None):
    out = []
    for p in card.parameters:
        if p.attr in ("__error__",):
            continue
        if _canonical_attr(p.attr) == attr_canon:
            if category and p.category != category:
                continue
            out.append(p)
    return out


def _collect_grades(card):
    """{(部位, 等级): param}"""
    out = {}
    for p in card.parameters:
        if _canonical_attr(p.attr) == "强度等级":
            g = _grade(p.value)
            if g:
                qual = re.search(r"[（(]([^）)]+)[）)]", p.entity)
                out[(qual.group(1) if qual else "", g)] = p
    return out


def compare_grades(dc, pc, findings):
    dg, pg = _collect_grades(dc), _collect_grades(pc)
    d_vals = {g for _, g in dg}
    p_vals = {g for _, g in pg}
    # 消歧：方案存在多个无部位强度等级 → 转"待人工确认"，避免逐值误报冲突
    p_plain = sorted({g for (q, g) in pg if not q})
    if len(p_plain) > 1:
        findings.append({
            "rule_id": "R-C-020", "级别": "一般", "类型": "待人工确认",
            "问题": "方案存在多个混凝土强度等级（%s），未能自动对应部位" % "/".join(p_plain),
            "图纸": "/".join(sorted(d_vals)) or "未抽取到", "方案": "/".join(p_plain),
            "证据": {"方案": pg[(min((q for q, g in pg if not q), key=len), p_plain[0])].evidence.raw[:80]
                     if any(not q for q, _ in pg) else ""},
            "建议": "人工确认各强度等级对应构件部位后复核"})
        p_vals = set()
    for (q, g), p in pg.items():
        if not q:
            continue
        for (dq, dg_), dp in dg.items():
            if dq and _norm(dq) == _norm(q) and dg_ != g:
                findings.append({
                    "rule_id": "R-C-001", "级别": "致命", "类型": "参数冲突",
                    "问题": "混凝土强度等级 图纸与方案不一致（部位：%s）" % q,
                    "图纸": "%s（%s）" % (dg_, dp.entity),
                    "方案": "%s（%s）" % (g, p.entity),
                    "证据": {"图纸": dp.evidence.raw[:80] if dp.evidence else "",
                             "方案": p.evidence.raw[:80] if p.evidence else ""},
                    "建议": "以图纸总说明为准修改方案混凝土强度等级，并同步验算书"})

    # 2) 方案等级集合 vs 图纸等级集合（无部位信息时整体比对；多值已转消歧）
    for (q, g) in pg:
        if q or len(p_plain) > 1:
            continue
        if d_vals and g not in d_vals:
            findings.append({
                "rule_id": "R-C-001", "级别": "致命", "类型": "参数冲突",
                "问题": "方案混凝土强度等级 %s 在图纸中不存在" % g,
                "图纸": "/".join(sorted(d_vals)) or "未抽取到",
                "方案": g,
                "证据": {"方案": pg[(q, g)].evidence.raw[:80] if pg[(q, g)].evidence else ""},
                "建议": "核对图纸总说明的混凝土强度等级并修改方案"})
    for (q, g) in dg:
        if q:
            continue
        if p_vals and g not in p_vals:
            findings.append({
                "rule_id": "R-C-002", "级别": "提示", "类型": "覆盖缺失",
                "问题": "图纸混凝土强度等级 %s 未在方案中体现" % g,
                "图纸": g, "方案": "/".join(sorted(p_vals)) or "未抽取到",
                "证据": {"图纸": dg[(q, g)].evidence.raw[:80] if dg[(q, g)].evidence else ""},
                "建议": "确认方案是否覆盖该强度等级构件（如未涉及可忽略）"})


def compare_numeric(dc, pc, attr_canon, rule_id, name, tol=1e-6):
    """同属性数值比对（mm 归一）。方案侧多值时转待人工确认（消歧）。"""
    findings = []
    ds = [(p, _mm(p.value, p.unit)) for p in _by_attr(dc, attr_canon)]
    ps = [(p, _mm(p.value, p.unit)) for p in _by_attr(pc, attr_canon)]
    ds = [(p, v) for p, v in ds if v is not None]
    ps = [(p, v) for p, v in ps if v is not None]
    if not ds or not ps:
        return findings
    d_vals = {v for _, v in ds}
    p_vals = {v for _, v in ps}
    if len(p_vals) > 1:
        findings.append({
            "rule_id": "R-C-020", "级别": "一般", "类型": "待人工确认",
            "问题": "方案中 %s 存在多个数值（%s），请人工确认适用部位" % (
                name, "/".join("%g" % v for v in sorted(p_vals))),
            "图纸": "/".join("%g" % v for v in sorted(d_vals)), "方案": "/".join("%g" % v for v in sorted(p_vals)),
            "证据": {"方案": ps[0][0].evidence.raw[:80] if ps[0][0].evidence else ""},
            "建议": "确认不同部位分别采用的数值后复核"})
        return findings
    for p, pv in ps:
        if not any(abs(pv - dv) <= tol for dv in d_vals):
            dp, dv = ds[0]
            findings.append({
                "rule_id": rule_id, "级别": "致命", "类型": "参数冲突",
                "问题": "%s 图纸与方案不一致" % name,
                "图纸": "%s mm" % dv, "方案": "%s mm" % pv,
                "证据": {"图纸": dp.evidence.raw[:80] if dp.evidence else "",
                         "方案": p.evidence.raw[:80] if p.evidence else ""},
                "建议": "以图纸为准修改方案参数，并复核相关验算"})
    return findings


def check_sections_cited(dc, pc):
    """方案引用的构件截面（WxH）应存在于图纸。"""
    findings = []
    d_secs = {p.value.replace("×", "x").replace("X", "x").lower()
              for p in dc.parameters if p.attr == "截面"}
    if not d_secs:
        return findings
    for p in pc.parameters:
        for m in re.finditer(r"(\d{3,4})\s*[×xX*]\s*(\d{3,4})", str(p.value)):
            sec = "%sx%s" % (m.group(1), m.group(2))
            if sec not in d_secs:
                findings.append({
                    "rule_id": "R-C-010", "级别": "一般", "类型": "引用不存在",
                    "问题": "方案引用构件截面 %s 在图纸中未找到" % sec,
                    "图纸": "/".join(sorted(d_secs))[:80], "方案": p.value[:40],
                    "证据": {"方案": p.evidence.raw[:80] if p.evidence else ""},
                    "建议": "核对截面尺寸来源（图纸变更？其他楼层？），避免方案张冠李戴"})
                break
    return findings


def compare_cards(dc, pc):
    """主入口：返回 findings 列表。"""
    findings = []
    compare_grades(dc, pc, findings)
    findings += compare_numeric(dc, pc, "板厚", "R-C-003", "楼板厚度", tol=0.5)
    findings += compare_numeric(dc, pc, "保护层厚度", "R-C-004", "保护层厚度")
    findings += check_sections_cited(dc, pc)
    return findings
