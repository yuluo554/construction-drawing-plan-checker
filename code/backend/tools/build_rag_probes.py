# -*- coding: utf-8 -*-
"""生成 RAG 检索探针夹具（需 API Key，只在更新知识库或门槛时运行）。

运行：cd code/backend && py tools/build_rag_probes.py
产出：code/knowledge/rag_probes.json

为什么要夹具：向量化需要外部 embedding API，CI 没有 Key。把 5 个标准查询的
**查询向量**（不是答案）冻结进仓库，就能在离线状态下对 55 条 chunk 复算 top1
相似度，从而让「规范检索 top1 命中区间」这条自述变成可复现的门。
KB 或模型变更后须重跑本脚本（否则夹具与索引失配，门会红——这是预期行为）。
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.knowledge.rag import KB, _cos, embed_texts  # noqa: E402

PROBES_PATH = Path(__file__).resolve().parents[2] / "knowledge" / "rag_probes.json"

# 5 类问题 × 覆盖 55 条 chunk（与 README「规范检索（5 类问题 × 55 条文块）」对应）
PROBES = [
    ("模板支撑体系搭设高度超过8米属于超规模危大工程吗", "住建部令37号/建办质〔2018〕31号附件",
     "模板工程及支撑体系"),
    ("基坑开挖深度5米以上需要编制专项施工方案", "住建部令37号/建办质〔2018〕31号附件", "基坑工程"),
    ("落地式钢管脚手架搭设高度24米是否危大", "住建部令37号/建办质〔2018〕31号附件", "脚手架工程"),
    ("专项施工方案应当包含哪些章节内容", "住建部令37号 危大工程管理规定", "管理程序"),
    ("超规模危大工程专家论证会参会人员要求", "住建部令37号 危大工程管理规定", "管理程序"),
]


def main():
    kb = KB()
    if not kb.chunks:
        print("FAIL: 知识库未加载（%s）" % kb.path)
        return 1
    print("知识库: %d chunks / model=%s" % (len(kb.chunks), kb.model))
    queries = [p[0] for p in PROBES]
    vectors = embed_texts(queries, model=kb.model)
    if len(vectors) != len(queries):
        print("FAIL: 向量条数 %d != 查询条数 %d" % (len(vectors), len(queries)))
        return 1

    out = []
    for (q, want_source, want_path), vec in zip(PROBES, vectors):
        scored = sorted(((_cos(vec, v), c) for v, c in zip(kb.vectors, kb.chunks)),
                        key=lambda t: t[0], reverse=True)
        top = scored[0]
        out.append({
            "query": q,
            "query_vector": [round(x, 6) for x in vec],
            "expect_source": want_source,
            "expect_path": want_path,
            "expected_top1": round(top[0], 4),
            "expected_top1_source": top[1].get("source", ""),
            "expected_top1_path": top[1].get("path", ""),
        })
        print("%.4f  %s" % (top[0], q[:34]))

    payload = {
        "_说明": "RAG 检索探针夹具：5 个标准查询的查询向量与实测 top1。"
                 "由 tools/build_rag_probes.py 生成，供离线回归门 tools/bench_rag.py 使用。"
                 "向量只含查询编码，不含任何密钥。",
        "model": kb.model,
        "kb_path": "code/knowledge/kb_weida.json",
        "kb_chunks": len(kb.chunks),
        "min_score": 0.55,
        "probes": out,
    }
    PROBES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(str(PROBES_PATH), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print("saved ->", PROBES_PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main())
