# -*- coding: utf-8 -*-
"""图纸文本行聚类合并 —— 平法标注常拆成多行文本实体（编号行+配筋行），
按 y 坐标聚类、x 排序拼接后再送解析器，才能抽全箍筋/纵筋。

同 y 行内还需按 x 邻近分链（xtol）：否则同一标高的柱标注与梁标注（相距数米）
会被错误合并，导致柱纵筋挂到梁上。"""
from collections import defaultdict


def merge_rows(items, ytol, xtol=60.0):
    """items: [(y, x, text, ev)] → [(merged_text, [ev...])]，同一坐标系。"""
    if not items:
        return []
    rows = defaultdict(list)
    for y, x, text, ev in items:
        placed = False
        for key in list(rows.keys()):
            if abs(key - y) <= ytol:
                rows[key].append((x, text, ev))
                placed = True
                break
        if not placed:
            rows[y].append((x, text, ev))

    out = []
    for key in sorted(rows.keys(), reverse=True):
        parts = sorted(rows[key], key=lambda t: t[0])
        # x 邻近分链：间距超过 xtol 即断开为独立标注块
        chains, cur = [], [parts[0]]
        for prt in parts[1:]:
            if prt[0] - cur[-1][0] <= xtol:
                cur.append(prt)
            else:
                chains.append(cur)
                cur = [prt]
        chains.append(cur)
        for chain in chains:
            merged = " ".join(t for _, t, _ in chain if t)
            evs = [ev for _, _, ev in chain if ev is not None]
            if merged.strip():
                out.append((merged.strip(), evs))
    return out
