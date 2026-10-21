# -*- coding: utf-8 -*-
"""RAG 依据相关性测试（D4）：条文只能挂在有对应条文的类别上，且必须过门槛。

原缺陷：engine.py 对任何致命项无条件取 top-1，导致「混凝土强度等级不一致」
被挂上「超规模危大须专家论证」（score 仅 0.3745）。本文件用假的 KB 验证
**挂载策略**，不需要 embedding API；真实索引的相似度区间由 tools/bench_rag.py 守。

运行：cd code/backend && py -m pytest tests/test_rag_relevance.py -q
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.rules.engine import RAG_ELIGIBLE_TYPES, RAG_MIN_SCORE, run_checks  # noqa: E402
from app.schemas.parameter_card import Parameter, ParameterCard  # noqa: E402


class FakeKB:
    """假知识库：记录被查询的内容，返回预设命中（可控分数）。"""

    def __init__(self, score=0.9):
        self.queries = []
        self.score = score

    def search(self, query, top_k=5, min_score=None):
        self.queries.append({"query": query, "min_score": min_score})
        if min_score is not None and self.score < min_score:
            return []
        return [{"score": self.score, "source": "住建部令37号 危大工程管理规定",
                 "path": "管理程序", "text": "超规模危大 → 组织专家论证会"}]


def _plan_with_height(height):
    card = ParameterCard(doc_type="plan", file="syn")
    card.add(Parameter(entity="模板支撑体系", category="measure", attr="支撑搭设高度",
                       value=height, unit="m", source="plan"))
    return card


def _plan_two_docs():
    """构造一张"参数冲突 + 危大合规"同时存在的报告输入。"""
    dc = ParameterCard(doc_type="drawing", file="d")
    dc.add(Parameter(entity="混凝土", category="material", attr="强度等级",
                     value="C35", source="drawing"))
    pc = ParameterCard(doc_type="plan", file="p")
    pc.add(Parameter(entity="混凝土", category="material", attr="强度等级",
                     value="C30", source="plan"))
    pc.add(Parameter(entity="模板支撑体系", category="measure", attr="支撑搭设高度",
                     value="6.2", unit="m", source="plan"))
    return dc, pc


def test_param_conflict_gets_no_clause():
    """参数冲突类不挂条文，且不去查知识库（查了也只会张冠李戴）。"""
    dc, pc = _plan_two_docs()
    kb = FakeKB(score=0.99)   # 即便分数极高，类别不符也不该挂
    report = run_checks(dc, pc, rag_on=True, kb=kb)
    conflicts = [f for f in report["findings"] if f.get("类型") == "参数冲突"]
    assert conflicts, "构造数据应产生参数冲突"
    for f in conflicts:
        assert f.get("条文") is None, "参数冲突不得挂条文，实际: %r" % (f.get("条文"),)
        info = f.get("条文检索") or {}
        assert info.get("状态") == "不适用", info
    # 参数冲突的"问题"文本不应进入检索
    assert all("强度等级" not in q["query"] for q in kb.queries), kb.queries


def test_weida_finding_gets_clause_with_threshold():
    """危大合规类可以挂条文，且检索时必须带上 RAG_MIN_SCORE。"""
    kb = FakeKB(score=0.9)
    report = run_checks(None, _plan_with_height("6.2"), rag_on=True, kb=kb)
    fatal = [f for f in report["findings"] if f["级别"] == "致命"]
    assert fatal, "6.2m 高支模应判为危大"
    for f in fatal:
        assert f.get("类型") in RAG_ELIGIBLE_TYPES
        assert f["条文"] is not None, "危大合规类应挂上条文"
        assert f["条文"]["score"] >= RAG_MIN_SCORE
    assert kb.queries, "应调用过检索"
    assert all(q["min_score"] == RAG_MIN_SCORE for q in kb.queries), kb.queries


def test_below_threshold_marks_not_found():
    """低于门槛 → 条文为 None，并显式标记"未检索到匹配条文"。"""
    kb = FakeKB(score=RAG_MIN_SCORE - 0.05)
    report = run_checks(None, _plan_with_height("6.2"), rag_on=True, kb=kb)
    fatal = [f for f in report["findings"] if f["级别"] == "致命"]
    assert fatal
    for f in fatal:
        assert f.get("条文") is None
        info = f.get("条文检索") or {}
        assert info.get("状态") == "未检索到匹配条文", info


def test_rag_off_leaves_no_clause():
    report = run_checks(None, _plan_with_height("6.2"), rag_on=False)
    for f in report["findings"]:
        assert f.get("条文") is None


def test_min_score_is_tightened():
    """0.55 是 v0.1.0 的选择；回归到 0.3（原值）必须让本测试变红。"""
    assert RAG_MIN_SCORE >= 0.5, "RAG 门槛被调回松值（原缺陷值 0.3）"
