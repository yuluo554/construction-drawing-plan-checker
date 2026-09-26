# -*- coding: utf-8 -*-
"""批量自制图纸基准评测 —— N 张随机图纸 vs 真值，输出字段级 P/R/F1。

运行：cd code/backend && py tools/bench_drawings.py [N] [起始种子]
说明：DXF 路径为规则解析的主通路；评测不含 LLM 调用（零成本可重复）。
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.parsers.dxf_parser import parse_dxf  # noqa: E402
from tools.gen_sample_drawing import build  # noqa: E402


def extract_fields(card):
    """参数卡 → {(tag, attr): value}（仅构件类，截面归一为 WxH）。"""
    out = {}
    for p in card.parameters:
        if p.category != "component" or p.attr in ("编号",):
            continue
        m = None
        for code in ("(", ")"):
            pass
        tag = p.entity.split("(")[-1].rstrip(")")
        val = p.value
        if p.attr == "跨数":
            val = val
        out[(tag, p.attr)] = val
    return out


def truth_fields(truth):
    out = {}
    for b in truth["beams"]:
        t = b["tag"]
        out[(t, "截面")] = "%dx%d" % tuple(b["sec"])
        out[(t, "跨数")] = str(b["spans"])
        out[(t, "箍筋")] = b["stirrup"]
        out[(t, "上部通长筋")] = b["top"]
        out[(t, "下部纵筋")] = b["bottom"]
    for c in truth["columns"]:
        t = c["tag"]
        out[(t, "截面")] = "%dx%d" % tuple(c["sec"])
        out[(t, "全部纵筋")] = c["rebar"]
        out[(t, "箍筋")] = "%s%s@%s(%d肢)" % tuple(c["stir"])
    return out


def main(n=10, seed0=1):
    tp = fp = fn = 0
    per_attr = {}
    for s in range(seed0, seed0 + n):
        doc, truth = build(s)
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "s.dxf")
            doc.saveas(path)
            card = parse_dxf(path)
        got = extract_fields(card)
        exp = truth_fields(truth)
        for k, v in exp.items():
            attr = k[1]
            stat = per_attr.setdefault(attr, {"tp": 0, "fp": 0, "fn": 0})
            g = got.get(k)
            if g is not None and normalize(k, g) == normalize(k, v):
                tp += 1
                stat["tp"] += 1
            else:
                fn += 1
                stat["fn"] += 1
                if g is not None:
                    fp += 1
                    stat["fp"] += 1
        extra = set(got) - set(exp)
        for k in extra:
            fp += 1
            per_attr.setdefault(k[1], {"tp": 0, "fp": 0, "fn": 0})["fp"] += 1

    print("样本数:%d  TP:%d FP:%d FN:%d" % (n, tp, fp, fn))
    print("%-10s %6s %6s %6s %8s" % ("字段", "P", "R", "F1", "样例数"))
    for attr, st in sorted(per_attr.items()):
        p = st["tp"] / max(st["tp"] + st["fp"], 1)
        r = st["tp"] / max(st["tp"] + st["fn"], 1)
        f1 = 2 * p * r / max(p + r, 1e-9)
        print("%-10s %6.2f %6.2f %6.2f %8d" % (attr, p, r, f1, st["tp"] + st["fn"]))


def normalize(key, val):
    tag, attr = key
    v = str(val).replace(" ", "").replace("×", "x").replace("X", "x")
    if attr in ("箍筋",):
        # 真值 'Φ8@100/200(2肢)' 与抽取值归一对齐
        v = v.replace("(2肢)", "(2)").replace("(4肢)", "(4)")
    return v.lower()


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    s0 = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    main(n, s0)
