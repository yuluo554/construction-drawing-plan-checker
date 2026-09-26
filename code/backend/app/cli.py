# -*- coding: utf-8 -*-
"""命令行入口：
  py -m app.cli drawing <file.dxf|.pdf> [-o out.json]   解析图纸 → 图纸参数卡
  py -m app.cli plan    <file.docx>       [-o out.json] 解析方案 → 方案参数卡
  py -m app.cli compliance <plan_card.json> [-o o.json] 危大合规判定
在 code/backend 目录下运行。
"""
import argparse
import json
import os
import sys


def parse_args(argv):
    ap = argparse.ArgumentParser(prog="app.cli", description="施工图×施工方案 协同校核 CLI (v1)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("drawing", help="解析图纸(DXF/PDF)")
    p1.add_argument("file")
    p1.add_argument("-o", "--out", default="")
    p1.add_argument("--llm", action="store_true", help="规则未命中时启用 LLM 兜底（需 code/.env）")
    p2 = sub.add_parser("plan", help="解析施工方案(docx)")
    p2.add_argument("file")
    p2.add_argument("-o", "--out", default="")
    p2.add_argument("--llm", action="store_true", help="启用 LLM 结构化抽取（需 code/.env）")
    p3 = sub.add_parser("compliance", help="危大合规判定(输入方案参数卡JSON)")
    p3.add_argument("file")
    p3.add_argument("-o", "--out", default="")
    p4 = sub.add_parser("check", help="图纸×方案 一致性+危大 校核(输入两张参数卡JSON)")
    p4.add_argument("drawing")
    p4.add_argument("plan")
    p4.add_argument("-o", "--out", default="")
    p4.add_argument("--rag", action="store_true", help="致命项附规范条文检索依据（需 code/.env）")
    p5 = sub.add_parser("run", help="端到端：图纸+方案文件 → 解析→校核→报告(docx/json)")
    p5.add_argument("drawing")
    p5.add_argument("plan")
    p5.add_argument("-o", "--out", default=".")
    p5.add_argument("--llm", action="store_true", help="启用 LLM 抽取/兜底（需 code/.env）")
    p5.add_argument("--rag", action="store_true", help="致命项附规范条文检索依据（需 code/.env）")
    return ap.parse_args(argv)


def _emit(card, out):
    if out:
        card.save_json(out)
        print("saved ->", out)
    else:
        print(json.dumps(card.to_dict(), ensure_ascii=False, indent=2))


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    from .parsers.dxf_parser import parse_any_cad
    from .parsers.pdf_parser import parse_pdf
    from .parsers.docx_parser import parse_docx

    if args.cmd == "drawing":
        if getattr(args, "llm", False):
            from .parsers import pingfa_llm
            pingfa_llm.set_llm_fallback(True)
        ext = os.path.splitext(args.file)[1].lower()
        card = parse_pdf(args.file) if ext == ".pdf" else parse_any_cad(args.file)
        _emit(card, args.out)
    elif args.cmd == "plan":
        card = parse_docx(args.file, use_llm=args.llm)
        _emit(card, args.out)
    elif args.cmd == "compliance":
        from .schemas.parameter_card import ParameterCard
        from .rules.weida import full_compliance_check
        card = ParameterCard.load_json(args.file)
        result = full_compliance_check(card)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.out:
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print("saved ->", args.out)
    elif args.cmd == "check":
        from .schemas.parameter_card import ParameterCard
        from .rules.engine import run_checks
        dc = ParameterCard.load_json(args.drawing)
        pc = ParameterCard.load_json(args.plan)
        kb = None
        if args.rag:
            from .knowledge.rag import KB
            kb = KB()
        report = run_checks(dc, pc, rag_on=args.rag, kb=kb)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if args.out:
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            print("saved ->", args.out)
    elif args.cmd == "run":
        from .agent.orchestrator import run_pipeline
        state = run_pipeline(args.drawing, args.plan, out_dir=args.out,
                             use_llm=args.llm, rag_on=args.rag)
        report = state.get("report") or {}
        print("结论:", report.get("结论"), "| 汇总:", report.get("summary"))
        print("进度:", state.get("progress"))
        for t in state.get("_trace", []):
            print(" 节点 %s: %s (%.2fs)" % (t["node"], "OK" if t["ok"] else "FAIL", t["耗时s"]))
        if state.get("json_path"):
            print("JSON ->", state["json_path"])
        if state.get("docx_path"):
            print("报告 ->", state["docx_path"])


if __name__ == "__main__":
    main()
