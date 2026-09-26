# -*- coding: utf-8 -*-
"""调试箍筋失配样本（逐种子容错）。"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.parsers.dxf_parser import parse_dxf
from tools.gen_sample_drawing import build
from tools.bench_drawings import extract_fields, truth_fields, normalize


def main():
    n = 0
    for s in range(1, 21):
        try:
            doc, truth = build(s)
            with tempfile.TemporaryDirectory() as td:
                p = os.path.join(td, "s.dxf")
                doc.saveas(p)
                card = parse_dxf(p)
            got = extract_fields(card)
            exp = truth_fields(truth)
            for b in truth["beams"]:
                exp[(b["tag"], "下部纵筋")] = b["bottom"]
            for k, v in exp.items():
                if k[1] != "箍筋":
                    continue
                g = got.get(k)
                if g is not None and normalize(k, g) != normalize(k, v):
                    n += 1
                    if n <= 10:
                        print("seed%d %s: 抽取=%r 真值=%r" % (s, k, g, v))
        except Exception as exc:
            print("seed%d ERROR %s" % (s, exc))
    print("箍筋失配总数:", n)


if __name__ == "__main__":
    main()
