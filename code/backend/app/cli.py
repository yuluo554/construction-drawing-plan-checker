# -*- coding: utf-8 -*-
"""命令行入口：
  py -m app.cli drawing <file.dxf|.pdf> [-o out.json]   解析图纸 → 图纸参数卡
  py -m app.cli plan    <file.docx>       [-o out.json] 解析方案 → 方案参数卡
  py -m app.cli compliance <plan_card.json> [-o o.json] 危大合规判定
在 code/backend 目录下运行。

退出码约定（v0.1.0 起）：
  0 = 成功
  1 = 运行失败（解析异常 / 流水线节点失败 / 未产出结果文件）
  2 = 用法或输入不可用（文件不存在 / 缺 --rag 所需配置）
"""
import argparse
import json
import os
import sys

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2


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
    # 安装态自查：资产在不在、知识库能否加载、阈值清单能否读、Web 静态文件在不在。
    # 加这个子命令是因为 v0.1.0 的装态缺陷（资产缺失）只能靠"跑一条业务命令看报错"发现。
    sub.add_parser("selftest", help="自检运行期资产与依赖（装完先跑这个）")
    return ap.parse_args(argv)


def _emit(card, out):
    if out:
        card.save_json(out)
        print("saved ->", out)
    else:
        print(json.dumps(card.to_dict(), ensure_ascii=False, indent=2))


def _require_files(paths):
    """返回缺失的输入文件列表（前置校验，避免带着坏路径跑到底再崩）。"""
    return [p for p in paths if not p or not os.path.isfile(p)]


def _empty_parse_error(card, kind):
    """解析器对坏文件会静默返回空卡（只记 warnings）——这里把它变成失败。

    0 条参数意味着下游校核没有任何输入，产出"未发现问题"是假成功。
    """
    if card.parameters:
        return None
    detail = "；".join(card.warnings) if card.warnings else "无告警信息"
    return "%s解析未得到任何参数（%s），文件可能损坏或格式不符" % (kind, detail)


def _check_rag_config():
    """--rag 的前置检查：embedding 配置 + 知识库资产。

    返回 (ok, message)。message 是可执行指引。
    v0.1.0 只查了配置；装态下知识库缺失会让 KB() 静默变成空索引、条文一条都挂不上，
    所以这里把"资产可加载"也纳入预检（v0.1.1）。
    """
    from .llm.client import load_env
    cfg = load_env()
    missing = [k for k in ("LLM_BASE_URL", "LLM_API_KEY") if not str(cfg.get(k) or "").strip()]
    if missing:
        return False, (
            "错误：--rag 需要 embedding 服务配置，缺少 %s。\n"
            "  做法：复制 code/.env.example 为 code/.env，填入 LLM_BASE_URL 与 LLM_API_KEY\n"
            "       （OpenAI 兼容接口，如阿里云百炼），或去掉 --rag 只跑规则通道。"
            % " / ".join(missing))
    from .resources import AssetMissing, asset_path
    try:
        asset_path("kb")
    except AssetMissing as exc:
        return False, "错误：--rag 需要规范知识库，但资产不可用。\n%s" % exc
    return True, ""


def _cmd_drawing(args):
    missing = _require_files([args.file])
    if missing:
        print("错误：图纸文件不存在 ->", missing[0], file=sys.stderr)
        return EXIT_USAGE
    from .parsers.dxf_parser import parse_any_cad
    from .parsers.pdf_parser import parse_pdf
    try:
        if getattr(args, "llm", False):
            from .parsers import pingfa_llm
            pingfa_llm.set_llm_fallback(True)
        ext = os.path.splitext(args.file)[1].lower()
        card = parse_pdf(args.file) if ext == ".pdf" else parse_any_cad(args.file)
        err = _empty_parse_error(card, "图纸")
        if err:
            print("错误：" + err, file=sys.stderr)
            return EXIT_FAIL
        _emit(card, args.out)
    except Exception as exc:
        print("错误：图纸解析失败 -> %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return EXIT_FAIL
    return EXIT_OK


def _cmd_plan(args):
    missing = _require_files([args.file])
    if missing:
        print("错误：方案文件不存在 ->", missing[0], file=sys.stderr)
        return EXIT_USAGE
    from .parsers.docx_parser import parse_docx
    try:
        card = parse_docx(args.file, use_llm=args.llm)
        err = _empty_parse_error(card, "方案")
        if err:
            print("错误：" + err, file=sys.stderr)
            return EXIT_FAIL
        _emit(card, args.out)
    except Exception as exc:
        print("错误：方案解析失败 -> %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return EXIT_FAIL
    return EXIT_OK


def _cmd_compliance(args):
    missing = _require_files([args.file])
    if missing:
        print("错误：参数卡文件不存在 ->", missing[0], file=sys.stderr)
        return EXIT_USAGE
    from .schemas.parameter_card import ParameterCard
    from .rules.weida import full_compliance_check
    try:
        card = ParameterCard.load_json(args.file)
        result = full_compliance_check(card)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.out:
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print("saved ->", args.out)
    except Exception as exc:
        print("错误：危大合规判定失败 -> %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return EXIT_FAIL
    return EXIT_OK


def _cmd_check(args):
    missing = _require_files([args.drawing, args.plan])
    if missing:
        print("错误：参数卡文件不存在 ->", missing[0], file=sys.stderr)
        return EXIT_USAGE
    if args.rag:
        ok, msg = _check_rag_config()
        if not ok:
            print(msg, file=sys.stderr)
            return EXIT_USAGE
    from .schemas.parameter_card import ParameterCard
    from .rules.engine import run_checks
    try:
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
    except Exception as exc:
        print("错误：校核失败 -> %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return EXIT_FAIL
    return EXIT_OK


def _cmd_run(args):
    missing = _require_files([args.drawing, args.plan])
    if missing:
        print("错误：输入文件不存在 ->", missing[0], file=sys.stderr)
        return EXIT_USAGE
    if args.rag:
        ok, msg = _check_rag_config()
        if not ok:
            print(msg, file=sys.stderr)
            return EXIT_USAGE
    from .agent.orchestrator import run_pipeline
    try:
        state = run_pipeline(args.drawing, args.plan, out_dir=args.out,
                             use_llm=args.llm, rag_on=args.rag)
    except Exception as exc:
        print("错误：流水线启动失败 -> %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return EXIT_FAIL

    report = state.get("report") or {}
    print("结论:", report.get("结论"), "| 汇总:", report.get("summary"))
    print("进度:", state.get("progress"))
    for t in state.get("_trace", []):
        print(" 节点 %s: %s (%.2fs)" % (t["node"], "OK" if t["ok"] else "FAIL", t["耗时s"]))
    if state.get("json_path"):
        print("JSON ->", state["json_path"])
    if state.get("docx_path"):
        print("报告 ->", state["docx_path"])

    # 失败可见性：节点失败 / 没产出结果文件都不得报成功
    failed = [t for t in state.get("_trace", []) if not t.get("ok")]
    if failed:
        print("错误：流水线节点失败 -> %s" % ", ".join(t["node"] for t in failed),
              file=sys.stderr)
        for e in state.get("_errors", []) or []:
            print("  %s: %s" % (e.get("node"), e.get("error")), file=sys.stderr)
        return EXIT_FAIL
    if not state.get("json_path") or not os.path.isfile(state["json_path"]):
        print("错误：未产出校核结果文件（结论不可用，详见上方节点输出）", file=sys.stderr)
        return EXIT_FAIL
    # 两侧任一张参数卡为空 = 解析静默失败，不得当作"未发现问题"
    empty = [name for name, key in (("图纸", "drawing_card"), ("方案", "plan_card"))
             if state.get(key) is None or not getattr(state[key], "parameters", None)]
    if empty:
        print("错误：%s解析未得到任何参数，校核结论不可信（见上方 warnings）" % "/".join(empty),
              file=sys.stderr)
        return EXIT_FAIL
    return EXIT_OK


def _cmd_selftest(args):
    """自检：安装态最容易坏的是"资产没随包分发"。逐项报告并给出可执行结论。

    退出码：0 = 全部可用；1 = 有关键资产缺失（依赖它的功能会失败）。
    """
    from .resources import describe
    rows = describe()
    ok = True
    print("运行期资产：")
    for name, path, where in rows:
        mark = {"package": "OK(包内)", "repo": "OK(仓库)", "missing": "MISSING"}[where]
        print("  %-11s %-10s %s" % (name, mark, path or "-"))
        if where == "missing":
            ok = False

    print("功能探针：")
    probes = []

    try:
        from .rules.weida import load_list
        spec = load_list()
        n = len(spec.get("危大工程范围_附件1", [])) + len(spec.get("超过一定规模_附件2_须专家论证", []))
        probes.append(("危大阈值清单可读", True, "%d 条规则" % n))
    except Exception as exc:
        probes.append(("危大阈值清单可读", False, "%s: %s" % (type(exc).__name__, exc)))
        ok = False

    try:
        from .knowledge.rag import KB
        kb = KB()
        probes.append(("知识库可加载", bool(kb.chunks),
                       "%d chunks / %d 维" % (len(kb.chunks), len(kb.vectors[0]) if kb.vectors else 0)))
        if not kb.chunks:
            ok = False
    except Exception as exc:
        probes.append(("知识库可加载", False, "%s: %s" % (type(exc).__name__, exc)))
        ok = False

    try:
        from . import server
        idx = os.path.join(server.STATIC_DIR, "index.html") if server.STATIC_DIR else ""
        good = bool(idx) and os.path.isfile(idx)
        probes.append(("Web 静态首页存在", good, idx or "static 目录缺失"))
        if not good:
            ok = False
    except Exception as exc:
        probes.append(("Web 静态首页存在", False, "%s: %s" % (type(exc).__name__, exc)))
        ok = False

    for name, good, detail in probes:
        print("  %-16s %-4s %s" % (name, "OK" if good else "FAIL", detail))

    print("结论：", "全部可用" if ok else "存在缺失项，见上方 MISSING/FAIL（--rag 与 Web 界面会受影响）")
    return EXIT_OK if ok else EXIT_FAIL


def main(argv=None):
    from .console import force_utf8_output
    force_utf8_output()   # Windows 默认代码页下中文帮助文本会抛 UnicodeEncodeError
    args = parse_args(argv if argv is not None else sys.argv[1:])
    handlers = {
        "drawing": _cmd_drawing,
        "plan": _cmd_plan,
        "compliance": _cmd_compliance,
        "check": _cmd_check,
        "run": _cmd_run,
        "selftest": _cmd_selftest,
    }
    handler = handlers.get(args.cmd)
    if handler is None:  # argparse 的 required=True 已挡住，这里只是兜底
        print("错误：未知子命令 ->", args.cmd, file=sys.stderr)
        return EXIT_USAGE
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
