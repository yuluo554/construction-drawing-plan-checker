# -*- coding: utf-8 -*-
"""平法标注解析器（22G101 体系）—— 规则版 v1。

支持（梁/柱/板集中标注的常见写法）：
  梁: KL1(3) 300×600  /  Φ8@100/200(2)  /  2Φ22; 3Φ18  /  G4Φ12 / N4Φ12
  柱: KZ1 600×600  /  24Φ22  /  4Φ12@100/200  /  8Φ22(角筋)
  板: LB1 h=120  /  B: XΦ12@150 YΦ10@180  /  T:XΦ12@150
符号归一：Φ(HPB300)、B(HRB335)、C(HRB400)、D(RRB400)、E(HRB500)
说明：LLM 兜底层留接口 parse_with_llm()，v1 仅规则；非法值（超范围）丢弃。
"""
import re
from typing import List, Optional

from ..schemas.parameter_card import Parameter, Evidence

# ---------- 基础 ----------

BAR_DIA = r"([ΦφABCDE])(\d+(?:\.\d+)?)"          # 钢筋符号 + 直径
BEAM_STIR_RE = re.compile(BAR_DIA + r"@\s*(\d+)(?:\s*/\s*(\d+))?\s*(?:\((\d+)\))?")
BEAM_SIDE_RE = re.compile(r"([GN])(\d+)" + BAR_DIA)
BEAM_LONG_RE = re.compile(r"(\d+)?" + BAR_DIA + r"(?:\s*;\s*(\d+)?" + BAR_DIA + r")?")

BEAM_TAG_RE = re.compile(r"\b(KL|WKL|KZL|JZL|XL|L)(\d+)\s*(?:\((\d+)[AB]?\))?\s*(\d+)\s*[×xX*]\s*(\d+)")
COL_TAG_RE = re.compile(r"\b(KZ|KZZ|XZ|LZ)(\d+)\s+(\d+)\s*[×xX*]\s*(\d+)")
SLAB_TAG_RE = re.compile(r"\b(LB|WB|YXB|XB)(\d+)\s*(?:h\s*=\s*(\d+))?")
SLAB_REBAR_RE = re.compile(r"([BT])\s*[:：]\s*X\s*" + BAR_DIA + r"@\s*(\d+)\s*(?:Y\s*" + BAR_DIA + r"@\s*(\d+))?")

BEAM_TYPE = {"KL": "框架梁", "WKL": "屋面框架梁", "KZL": "框支梁", "L": "非框架梁",
             "JZL": "井字梁", "XL": "悬挑梁"}
COLUMN_TYPE = {"KZ": "框架柱", "KZZ": "框支柱", "XZ": "芯柱", "LZ": "梁上柱"}
SLAB_TYPE = {"LB": "楼面板", "WB": "屋面板", "YXB": "延伸悬挑板", "XB": "悬挑板"}

CONC_RE = re.compile(r"(?:混凝土强度等级|混凝土)[为：:\s]*[^，。\n]{0,8}?(C\d{2,3})")
CONC_PART = re.compile(r"(基础底板|底板|基础|筏板|承台|地梁|墙|柱|梁|板|楼梯|构造柱|圈梁|屋面)")
PROTECT_RE = re.compile(r"保护层厚度[为：:\s]*(\d+)\s*(?:mm|毫米)?")


def _valid_dia(d):
    return 4 <= d <= 40


def _valid_spacing(s):
    return 50 <= s <= 400


def _valid_sec(w, h):
    return 100 <= w <= 2000 and 150 <= h <= 3000


def _p(entity, attr, value, ev, unit="", category="component"):
    return Parameter(entity=entity, category=category, attr=attr, value=value,
                     unit=unit, source="drawing", evidence=ev)


# ---------- 梁 ----------

def parse_beam_tag(text, ev=None):
    out = []
    m = BEAM_TAG_RE.search(text)
    if not m:
        return out
    code, num, spans, w, h = m.groups()
    w, h = float(w), float(h)
    if not _valid_sec(w, h):
        return out
    name = code + num
    entity = "%s(%s)" % (BEAM_TYPE.get(code, code), name)
    out.append(_p(entity, "编号", name, ev))
    if spans:
        out.append(_p(entity, "跨数", spans, ev, "跨"))
    out.append(_p(entity, "截面", "%dx%d" % (int(w), int(h)), ev, "mm"))
    cleaned = text

    ms = BEAM_STIR_RE.search(text, m.end())
    if ms:
        sym, dia, s1, s2, legs = ms.groups()
        if _valid_dia(float(dia)) and _valid_spacing(float(s1)):
            val = "%s%s@%s" % (sym, dia, s1) + ("/%s" % s2 if s2 else "")
            out.append(_p(entity, "箍筋", val + ("(%s肢)" % legs if legs else ""), ev, "mm"))
            cleaned = cleaned.replace(ms.group(0), "")

    cleaned = BEAM_SIDE_RE.sub("", cleaned)     # 去掉腰筋片段，避免误判为通长筋
    for ml in BEAM_LONG_RE.finditer(cleaned):
        n1, sy1, d1, n2, sy2, d2 = ml.groups()
        if n1 and _valid_dia(float(d1)):
            out.append(_p(entity, "上部通长筋", "%s%s%s" % (n1, sy1, d1), ev))
        if n2 and _valid_dia(float(d2)):
            out.append(_p(entity, "下部纵筋", "%s%s%s" % (n2, sy2, d2), ev))

    mside = BEAM_SIDE_RE.search(text)
    if mside:
        kind, n, sym, dia = mside.groups()
        out.append(_p(entity, "构造腰筋" if kind == "G" else "抗扭腰筋",
                      "%s%s%s" % (n, sym, dia), ev))
    return out


# ---------- 柱 ----------

def parse_column_tag(text, ev=None):
    out = []
    m = COL_TAG_RE.search(text)
    if not m:
        return out
    code, num, w, h = m.groups()
    w, h = float(w), float(h)
    if not _valid_sec(w, h):
        return out
    name = code + num
    entity = "%s(%s)" % (COLUMN_TYPE.get(code, code), name)
    out.append(_p(entity, "编号", name, ev))
    out.append(_p(entity, "截面", "%dx%d" % (int(w), int(h)), ev, "mm"))
    rest = text[m.end():]

    mc = re.search(r"(\d+)" + BAR_DIA + r"\s*\(角筋\)", rest)
    if mc:
        n, sym, dia = mc.groups()
        out.append(_p(entity, "角筋", "%s%s%s" % (n, sym, dia), ev))
        rest = rest.replace(mc.group(0), "")

    mall = re.search(r"(\d+)" + BAR_DIA, rest)
    if mall:
        n, sym, dia = mall.groups()
        out.append(_p(entity, "全部纵筋", "%s%s%s" % (n, sym, dia), ev))
        rest = rest.replace(mall.group(0), "")

    ms = BEAM_STIR_RE.search(rest)
    if ms:
        sym, dia, s1, s2, legs = ms.groups()
        if _valid_dia(float(dia)) and _valid_spacing(float(s1)):
            val = "%s%s@%s" % (sym, dia, s1) + ("/%s" % s2 if s2 else "")
            out.append(_p(entity, "箍筋", val + ("(%s肢)" % legs if legs else ""), ev, "mm"))
    return out


# ---------- 板 ----------

def parse_slab_tag(text, ev=None):
    out = []
    m = SLAB_TAG_RE.search(text)
    if not m:
        return out
    code, num, thick = m.groups()
    name = code + num
    entity = "%s(%s)" % (SLAB_TYPE.get(code, code), name)
    out.append(_p(entity, "编号", name, ev))
    if thick:
        out.append(_p(entity, "板厚", thick, ev, "mm"))
    for mrb in SLAB_REBAR_RE.finditer(text):
        pos, sy1, d1, s1, sy2, d2, s2 = mrb.groups()
        val = "X%s%s@%s" % (sy1, d1, s1)
        if sy2 and d2 and s2:
            val += " Y%s%s@%s" % (sy2, d2, s2)
        out.append(_p(entity, "底部配筋" if pos == "B" else "顶部配筋", val, ev))
    return out


# ---------- 材料（总说明） ----------

def parse_material(text, ev=None):
    out = []
    for mm in CONC_RE.finditer(text):
        part = CONC_PART.search(text)
        entity = "混凝土" + ("(%s)" % part.group(1) if part else "")
        out.append(Parameter(entity=entity, category="material", attr="强度等级",
                             value=mm.group(1), source="drawing", evidence=ev))
    for mp in PROTECT_RE.finditer(text):
        if 10 <= int(mp.group(1)) <= 60:
            out.append(Parameter(entity="钢筋混凝土", category="material", attr="保护层厚度",
                                 value=mp.group(1), unit="mm", source="drawing", evidence=ev))
    return out


# ---------- 总入口 ----------

ANN_MARK_RE = re.compile(r"[@×]|Φ|[Cc]\s*\d")
_ANN_CHAR = r"0-9A-Za-z×@Φφ()./%;；\u4e00-\u9fa5"


def compact_annotation(text):
    """PDF/CAD 导出常将字符逐个定位（'K Z 1   6 0 0 × 6 0 0' 或 '混 凝 土 … C 3 5'）。
    判定特征：含多空格串，或单字符 token 占多数（字符拆分定位）。
    执行：先删标注字符间单空格（伪空格），再把 ≥2 空格折叠为1个词边界。"""
    if not ANN_MARK_RE.search(text):
        return text
    toks = text.split()
    single_n = sum(1 for t in toks if len(t) == 1)
    has_cd = bool(re.search(r"[Cc]\s*\d", text))
    char_spaced = single_n >= 4 or (has_cd and single_n >= 2)
    if not char_spaced and not re.search(r"\S\s{2,}\S", text):
        return text
    t = re.sub(r"(?<=[%s]) (?=[%s])" % (_ANN_CHAR, _ANN_CHAR), "", text)
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip()


TAG_SPLIT_RE = re.compile(r"\b(?:WKL|KZL|JZL|KL|KZZ|KZ|XZ|LZ|LB|WB|YXB|XB|XL|L)\d")


def split_segments(text):
    """合并行内若含多个构件标签（梁+柱标注被并到一行），按标签切分后逐段解析，
    避免柱纵筋被误挂到梁上。"""
    ms = list(TAG_SPLIT_RE.finditer(text))
    if len(ms) <= 1:
        return [text]
    segs = []
    pre = text[:ms[0].start()].strip()
    if pre:
        segs.append(pre)
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        seg = text[m.start():end].strip()
        if seg:
            segs.append(seg)
    return segs


def parse_text(text, ev=None):
    """对一段图纸文本依次尝试梁/柱/板/材料解析；多标签行先切分。
    规则未命中且开启 LLM 兜底（--llm）时，走大模型兜底抽取。"""
    text = compact_annotation(text)
    params = []
    for seg in split_segments(text):
        params += parse_beam_tag(seg, ev)
        params += parse_column_tag(seg, ev)
        params += parse_slab_tag(seg, ev)
        params += parse_material(seg, ev)
    if not params and ANN_MARK_RE.search(text):
        from . import pingfa_llm
        if pingfa_llm._FALLBACK_ON:
            params += pingfa_llm.parse_with_llm(text, ev)
    return params


def parse_with_llm(text):
    """LLM 兜底接口（v2 接入 .env 大模型；v1 返回空）。"""
    return []
