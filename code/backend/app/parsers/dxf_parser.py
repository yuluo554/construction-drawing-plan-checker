# -*- coding: utf-8 -*-
"""DXF 图纸解析器（ezdxf）—— 图纸参数卡 v1。

流程：读 DXF → 收集全部文本(TEXT/MTEXT/ATTRIB/DIMENSION) → 平法解析 →
     图框/标题栏线索(工程名称/图号/比例) → 图层与实体统计。
DWG 输入：提示需先经 ODA File Converter 转 DXF（TODO: 集成自动转换）。
"""
import os
from typing import List

from ..schemas.parameter_card import ParameterCard, Evidence
from . import pingfa


def _iter_texts(doc):
    """遍历模型空间全部文本实体，返回 [(text, bbox_or_None)]。"""
    msp = doc.modelspace()
    out = []
    try:
        for e in msp:
            t = e.dxftype()
            if t == "TEXT":
                pos = e.dxf.insert
                out.append((e.dxf.text, [pos.x, pos.y, pos.x, pos.y]))
            elif t == "MTEXT":
                pos = e.dxf.insert
                plain = e.plain_text() if hasattr(e, "plain_text") else e.text
                out.append((plain, [pos.x, pos.y, pos.x, pos.y]))
            elif t == "INSERT":
                try:
                    for attr in e.attribs:
                        out.append((attr.dxf.text, None))
                except Exception:
                    pass
            elif t == "DIMENSION":
                try:
                    txt = e.dxf.text
                    if txt and txt not in ("<>", ""):
                        out.append((txt, None))
                except Exception:
                    pass
    except Exception as exc:  # 单个实体损坏不中断整体解析
        out.append(("_ENTITY_ERROR:%s" % exc, None))
    return out


def _guess_title_block(texts):
    """从文本中提取图框/标题栏线索（v1 关键词启发式）。"""
    meta = {}
    kws = {"工程名称": "project_name", "工程名": "project_name", "图 名": "sheet_title",
           "图名": "sheet_title", "图 号": "sheet_no", "图号": "sheet_no", "比例": "scale",
           "设 计": "designer", "设计": "designer", "审核": "checker", "日 期": "date", "日期": "date"}
    for text, _ in texts:
        t = text.strip()
        for kw, key in kws.items():
            if kw in t and len(t) <= 40:
                val = t.split(kw)[-1].strip(" :：=－-")
                if val and not meta.get(key):
                    meta[key] = val
    return meta


def parse_dxf(path: str) -> ParameterCard:
    card = ParameterCard(doc_type="drawing", file=os.path.abspath(path))
    try:
        import ezdxf
        doc = ezdxf.readfile(path)
    except Exception as exc:
        card.warnings.append("DXF 读取失败: %s" % exc)
        return card

    texts = _iter_texts(doc)
    card.extras["text_count"] = len(texts)
    try:
        card.extras["layers"] = sorted({e.dxf.layer for e in doc.modelspace() if hasattr(e, "dxf") and hasattr(e.dxf, "layer")})[:50]
    except Exception:
        pass
    try:
        card.extras["entity_types"] = {t: n for t, n in sorted(
            __import__("collections").Counter(e.dxftype() for e in doc.modelspace()).items())}
    except Exception:
        pass

    card.meta = _guess_title_block(texts)

    # 行聚类合并（编号行+配筋行），再逐行/逐簇解析
    from .textutil import merge_rows
    items = []
    for text, bbox in texts:
        if not text.strip() or text.startswith("_ENTITY_ERROR"):
            continue
        ev = Evidence(doc=os.path.basename(path), page=0,
                      bbox=[round(v, 1) for v in bbox] if bbox else None, raw=text.strip()[:120])
        items.append((bbox[1] if bbox else 0, bbox[0] if bbox else 0, text.strip(), ev))
    ev0 = Evidence(doc=os.path.basename(path), page=0)
    merged = merge_rows(items, ytol=1.5, xtol=80.0) or [("", [])]
    parsed_keys = set()

    def _parse_feed(line, ev):
        for p in pingfa.parse_text(line, ev):
            key = (p.entity, p.attr, p.value)
            if key not in parsed_keys:
                parsed_keys.add(key)
                card.add(p)

    for line, evs in merged:
        _parse_feed(line, evs[0] if evs else ev0)
    for text, bbox in texts:  # 逐条兜底（合并遗漏的场景）
        if text.strip() and not text.startswith("_ENTITY_ERROR"):
            ev = Evidence(doc=os.path.basename(path), page=0,
                          bbox=[round(v, 1) for v in bbox] if bbox else None, raw=text.strip()[:120])
            _parse_feed(text, ev)

    if not texts:
        card.warnings.append("DXF 中未发现文本实体")
    return card


def parse_any_cad(path: str) -> ParameterCard:
    """CAD 入口分发：.dxf 直接解析；.dwg 提示转换。"""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".dxf":
        return parse_dxf(path)
    card = ParameterCard(doc_type="drawing", file=os.path.abspath(path))
    card.warnings.append("DWG 需先转换为 DXF：请安装 ODA File Converter 后执行转换（TODO 集成自动转换）")
    return card
