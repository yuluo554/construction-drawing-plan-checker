# -*- coding: utf-8 -*-
"""端到端编排器 —— 图纸+方案 文件 → 解析 → 校核 → 报告（docx/json）。

工作流（LangGraph 风格，见 workflow.py）：
  intake(文件校验) → parse_drawing → parse_plan → check(规则引擎) → review(消歧/汇总) → export(报告)

用法：
    from app.agent.orchestrator import run_pipeline
    result = run_pipeline(drawing_path, plan_path, out_dir=".", use_llm=False, rag_on=False)
"""
import json
import os

from ..parsers.dxf_parser import parse_any_cad
from ..parsers.pdf_parser import parse_pdf
from ..parsers.docx_parser import parse_docx
from ..rules.engine import run_checks
from ..report.export import build_report_docx
from .workflow import Graph


def _parse_drawing(path, use_llm=False):
    ext = os.path.splitext(path)[1].lower()
    if use_llm:
        from .parsers import pingfa_llm
        pingfa_llm.set_llm_fallback(True)
    return parse_pdf(path) if ext == ".pdf" else parse_any_cad(path)


def build_graph(out_dir, use_llm=False, rag_on=False, kb=None):
    g = Graph("check-pipeline").set_entry("intake")

    def intake(state):
        for key in ("drawing_path", "plan_path"):
            if not state.get(key) or not os.path.exists(state[key]):
                raise FileNotFoundError(state.get(key))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        state["progress"] = "文件就绪"
        return state

    def parse_drawing(state):
        card = _parse_drawing(state["drawing_path"], use_llm)
        if card.warnings:
            state.setdefault("warnings", []).extend(card.warnings)
        state["drawing_card"] = card
        state["progress"] = "图纸解析：%d 条参数" % len(card.parameters)
        return state

    def parse_plan(state):
        card = parse_docx(state["plan_path"], use_llm=use_llm)
        if card.warnings:
            state.setdefault("warnings", []).extend(card.warnings)
        state["plan_card"] = card
        state["progress"] = "方案解析：%d 条参数" % len(card.parameters)
        return state

    def check(state):
        report = run_checks(state.get("drawing_card"), state.get("plan_card"),
                            rag_on=rag_on, kb=kb)
        report["_trace"] = state.get("_trace", [])
        report["warnings"] = state.get("warnings", [])
        report["plan_meta"] = state["plan_card"].meta
        report["drawing_meta"] = state["drawing_card"].meta
        report["llm_stats"] = state["plan_card"].extras.get("llm_stats")
        state["report"] = report
        state["progress"] = "校核完成：致命%d 一般%d 提示%d" % (
            report["summary"]["致命"], report["summary"]["一般"], report["summary"]["提示"])
        return state

    def export(state):
        report = state["report"]
        if out_dir:
            state["json_path"] = os.path.join(out_dir, "校核结果.json")
            with open(state["json_path"], "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2, default=str)
            state["docx_path"] = build_report_docx(
                report, state.get("drawing_card"), state.get("plan_card"),
                os.path.join(out_dir, "校核报告.docx"))
        return state

    g.add_node("intake", intake, retries=1)
    g.add_node("parse_drawing", parse_drawing, retries=1)
    g.add_node("parse_plan", parse_plan, retries=1)
    g.add_node("check", check, retries=0)
    g.add_node("export", export, retries=1)
    g.add_edge("intake", "parse_drawing").add_edge("parse_drawing", "parse_plan") \
      .add_edge("parse_plan", "check").add_edge("check", "export")
    return g


def run_pipeline(drawing_path, plan_path, out_dir=".", use_llm=False, rag_on=False):
    """端到端入口，返回最终 state（含 report/结果文件路径/trace）。"""
    kb = None
    if rag_on:
        from ..knowledge.rag import KB
        kb = KB()
    g = build_graph(out_dir, use_llm=use_llm, rag_on=rag_on, kb=kb)
    return g.invoke({"drawing_path": drawing_path, "plan_path": plan_path})
