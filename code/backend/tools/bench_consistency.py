# -*- coding: utf-8 -*-
"""配对数据一致性校核评测 —— N 组(图纸+方案)已知差异，测检出率/误报/危大准确率。

运行：cd code/backend && py tools/bench_consistency.py [N] [起始种子]
（纯规则通路，零 LLM 成本；每组自动生成 配对图纸+方案 并执行 run_checks）
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.parsers.docx_parser import parse_docx  # noqa: E402
from app.parsers.dxf_parser import parse_dxf  # noqa: E402
from app.rules.engine import run_checks  # noqa: E402
from tools import gen_sample_drawing, gen_sample_plan  # noqa: E402


def one_pair(seed):
    # 图纸（DXF）
    doc, truth = gen_sample_drawing.build(seed)
    with tempfile.TemporaryDirectory() as td:
        dpath = os.path.join(td, "s.dxf")
        doc.saveas(dpath)
        drawing_card = parse_dxf(dpath)
    # 方案（docx，配对：混凝土图纸真值传入）
    sc = gen_sample_plan.scenario(seed, drawing_conc=truth["concrete"])
    with tempfile.TemporaryDirectory() as td:
        ppath = os.path.join(td, "p.docx")
        gen_sample_plan.build_docx(sc, ppath)
        plan_card = parse_docx(ppath)
    report = run_checks(drawing_card, plan_card, rag_on=False)
    return sc, report


def main(n=10, seed0=1):
    diff_total = diff_hit = weida_total = weida_hit = 0
    false_fatal = 0
    examples = []
    for s in range(seed0, seed0 + n):
        sc, report = one_pair(s)
        findings = report["findings"]
        fatal = [f for f in findings if f["级别"] == "致命"]
        conc_findings = [f for f in fatal if f.get("rule_id") == "R-C-001"]
        weida_findings = [f for f in fatal if f.get("类型") == "危大合规"]

        # 1) 植入的混凝土差异必须被检出
        if sc["预期混凝土差异"]:
            diff_total += 1
            if conc_findings:
                diff_hit += 1
            elif len(examples) < 5:
                examples.append("seed%d 混凝土差异漏检" % s)
        # 2) 危大判定与真值一致
        weida_total += 1
        expect = sc["预期危大判定"]
        got_weida = [f for f in weida_findings if expect[:2] in f["问题"]]
        if (expect == "非危大" and not weida_findings) or (expect != "非危大" and got_weida):
            weida_hit += 1
        elif len(examples) < 5:
            examples.append("seed%d 危大不符: 预期%s 实际%s" % (
                s, expect, [f["问题"][:30] for f in weida_findings]))
        # 3) 误报：非植入的致命项
        unexpected = [f for f in fatal
                      if not (f.get("rule_id") == "R-C-001" and sc["预期混凝土差异"])
                      and f.get("类型") != "危大合规"]
        false_fatal += len(unexpected)
        for f in unexpected[:2]:
            if len(examples) < 8:
                examples.append("seed%d 误报: %s" % (s, f.get("问题", "")[:50]))

    print("配对数:%d" % n)
    print("植入混凝土差异检出: %d/%d" % (diff_hit, diff_total))
    print("危大判定准确: %d/%d" % (weida_hit, weida_total))
    print("非预期致命项(误报): %d" % false_fatal)
    for e in examples:
        print(" -", e)


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    s0 = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    main(n, s0)
