# -*- coding: utf-8 -*-
"""端到端编排器测试：真实配对数据 跑 run_pipeline（规则通路，零 API）。"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

REPO = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DRAWING = os.path.join(REPO, "data", "施工图纸", "自制样例", "sample_beam_plan.dxf")
PLAN = os.path.join(REPO, "data", "施工方案", "自制样例", "sample_formwork_plan_13.docx")


@pytest.mark.skipif(not (os.path.exists(DRAWING) and os.path.exists(PLAN)),
                    reason="配对演示数据缺失")
def test_pipeline_end_to_end(tmp_path):
    from app.agent.orchestrator import run_pipeline
    out_dir = str(tmp_path)
    state = run_pipeline(DRAWING, PLAN, out_dir=out_dir, use_llm=False, rag_on=False)
    assert state.get("_done")
    assert not state.get("_errors")
    report = state["report"]
    assert report["summary"]["致命"] >= 1          # 植入的混凝土差异
    assert any(f["rule_id"] == "R-W-000" for f in report["findings"])   # 6.2m 高支模
    assert os.path.exists(state["json_path"])
    assert os.path.exists(state["docx_path"])
    # trace 记录 5 个节点全部成功
    assert len(state["_trace"]) == 5 and all(t["ok"] for t in state["_trace"])
    # docx 报告非空
    assert os.path.getsize(state["docx_path"]) > 5000


@pytest.mark.skipif(not os.path.exists(PLAN), reason="方案样例缺失")
def test_pipeline_missing_drawing(tmp_path):
    from app.agent.orchestrator import run_pipeline
    state = run_pipeline(os.path.join(tmp_path, "不存在.dxf"), PLAN, out_dir=str(tmp_path))
    assert state.get("_errors")            # intake 失败被记录
    assert not state.get("_done") or state.get("_errors")
