# -*- coding: utf-8 -*-
"""PDF 图纸解析器（PyMuPDF）—— 矢量 PDF 路径 v1。

流程：逐页提取文本块(bbox) → 判断矢量/扫描 → 平法解析(带bbox证据) →
     表格提取(find_tables) → 标题栏线索。
扫描件：标记 warning"无文本层，需 OCR"，走 OCR 通路的接口留待 v2。
"""
import os
from typing import List

from ..schemas.parameter_card import ParameterCard, Evidence
from . import pingfa

TITLE_KWS = {"工程名称": "project_name", "图 名": "sheet_title", "图名": "sheet_title",
             "图 号": "sheet_no", "图号": "sheet_no", "比例": "scale",
             "设 计": "designer", "设计": "designer", "审核": "checker",
             "日 期": "date", "日期": "date"}

_TAG_RE = None


def _has_tag(line):
    """行内是否含构件编号（用于相邻行配对解析的触发）。"""
    global _TAG_RE
    if _TAG_RE is None:
        import re as _re
        _TAG_RE = _re.compile(r"\b(?:KL|WKL|KZL|JZL|XL|L|KZ|KZZ|XZ|LZ|LB|WB|YXB|XB)\d", _re.IGNORECASE)
    return bool(_TAG_RE.search(line))


def _title_meta(texts):
    meta = {}
    for t in texts:
        t = t.strip()
        for kw, key in TITLE_KWS.items():
            if kw in t and len(t) <= 40:
                val = t.split(kw)[-1].strip(" :：=－-")
                if val and not meta.get(key):
                    meta[key] = val
    return meta


def parse_pdf(path: str) -> ParameterCard:
    card = ParameterCard(doc_type="drawing", file=os.path.abspath(path))
    try:
        import fitz
        doc = fitz.open(path)
    except Exception as exc:
        card.warnings.append("PDF 打开失败: %s" % exc)
        return card

    all_texts = []
    page_lines = []  # (page, y, x, line, ev)
    total_chars = 0
    for pno in range(min(doc.page_count, 50)):
        page = doc[pno]
        # 文本块（带 bbox）
        try:
            blocks = page.get_text("blocks") or []
        except Exception:
            blocks = []
        page_chars = 0
        for b in blocks:
            x0, y0, x1, y1, text = b[0], b[1], b[2], b[3], b[4]
            if not text or not text.strip():
                continue
            page_chars += len(text.strip())
            all_texts.append(text)
            for li, line in enumerate(text.splitlines()):
                line = line.strip()
                if not line:
                    continue
                ev = Evidence(doc=os.path.basename(path), page=pno + 1,
                              bbox=[round(x0, 1), round(y0 + li * 12, 1), round(x1, 1), round(y1, 1)],
                              raw=line[:120])
                page_lines.append((pno, y0 + li * 12, x0, line, ev))
        total_chars += page_chars
        if page_chars == 0:
            card.warnings.append("第%d页无文本层（疑似扫描件，需 OCR 通路）" % (pno + 1))

        # 表格（矢量 PDF）
        try:
            tabs = page.find_tables()
            card.extras.setdefault("tables", [])
            for ti, tab in enumerate(tabs.tables):
                rows = tab.extract()
                card.extras["tables"].append({"page": pno + 1, "index": ti,
                                              "rows": len(rows), "cols": len(rows[0]) if rows else 0,
                                              "preview": [r[:3] for r in rows[:3]]})
        except Exception:
            pass

    # 行聚类合并（编号行+配筋行），逐行+逐簇双路解析，去重
    from .textutil import merge_rows
    parsed_keys = set()

    def _parse_feed(line, ev):
        for p in pingfa.parse_text(line, ev):
            key = (p.entity, p.attr, p.value)
            if key not in parsed_keys:
                parsed_keys.add(key)
                card.add(p)

    from collections import defaultdict
    by_page = defaultdict(list)
    for pno, y, x, line, ev in page_lines:
        by_page[pno].append((y, x, line, ev))
        _parse_feed(line, ev)
    for pno, items in by_page.items():
        rows = merge_rows(items, ytol=12.0, xtol=40.0)
        for i, (line, evs) in enumerate(rows):
            _parse_feed(line, evs[0] if evs else None)
            # 相邻行配对：平法"编号行+配筋行"常跨块堆叠（y距超过行聚类容差）
            if i + 1 < len(rows) and _has_tag(line):
                nxt, nxt_evs = rows[i + 1]
                _parse_feed(line + " " + nxt, evs[0] if evs else None)

    card.extras["page_count"] = doc.page_count
    card.extras["total_chars"] = total_chars
    card.extras["vector"] = total_chars > 50
    card.meta = _title_meta(all_texts)
    return card
