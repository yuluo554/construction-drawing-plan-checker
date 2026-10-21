# -*- coding: utf-8 -*-
"""规范检索回归门（离线，零 API）—— 用固定查询向量复算 top1 命中。

运行：cd code/backend && py tools/bench_rag.py [--min-top1 0.55] [--max-top1 0.85]
读：code/knowledge/rag_probes.json（由 tools/build_rag_probes.py 生成）
断言：
  1. 夹具与知识库匹配（chunks 数、模型名一致）——失配即红，防止"用旧夹具测新索引"；
  2. 每个查询的 top1 chunk 落在预期 source/path 上（README「top1 全命中」）；
  3. 每个 top1 相似度 >= min_score（低于此值的命中会被 engine 拒挂）；
  4. 每个 top1 相似度 <= max_top1（过高说明夹具与索引同源过度拟合，或门槛设得过松）。

退出码：0 = 全部断言通过；1 = 有断言失败。
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.console import force_utf8_output  # noqa: E402
from app.knowledge.rag import KB, _cos  # noqa: E402

force_utf8_output()   # Windows 默认代码页下含中文的输出会抛 UnicodeEncodeError

PROBES_PATH = Path(__file__).resolve().parents[2] / "knowledge" / "rag_probes.json"
MIN_TOP1 = 0.55
MAX_TOP1 = 0.85


def load_probes(path=PROBES_PATH):
    with open(str(path), "r", encoding="utf-8") as f:
        return json.load(f)


def check(probes, kb, min_top1=MIN_TOP1, max_top1=MAX_TOP1):
    """返回 (failures, rows)；rows 供打印。纯计算，便于单测直接调用。"""
    failures = []
    rows = []
    if probes.get("kb_chunks") != len(kb.chunks):
        failures.append("夹具 kb_chunks=%s 与索引 %d 不一致（索引已变，需重跑 "
                        "tools/build_rag_probes.py）" % (probes.get("kb_chunks"), len(kb.chunks)))
    if probes.get("model") and kb.model and probes["model"] != kb.model:
        failures.append("夹具 model=%s 与索引 model=%s 不一致" % (probes["model"], kb.model))

    for p in probes.get("probes", []):
        qv = p.get("query_vector") or []
        if len(qv) != 1024:
            failures.append("%s: 查询向量维度 %d != 1024" % (p.get("query", "")[:16], len(qv)))
            continue
        scored = sorted(((_cos(qv, v), c) for v, c in zip(kb.vectors, kb.chunks)),
                        key=lambda t: t[0], reverse=True)
        if not scored:
            failures.append("%s: 索引为空" % p.get("query", "")[:16])
            continue
        score, top = scored[0]
        want_src = p.get("expect_source", "")
        want_path = p.get("expect_path", "")
        hit = top.get("source", "") == want_src and top.get("path", "") == want_path
        rows.append({"query": p.get("query", ""), "score": round(score, 4),
                     "source": top.get("source", ""), "path": top.get("path", ""),
                     "hit": hit})
        if not hit:
            failures.append("top1 未命中预期：得到 %r/%r，期望 %r/%r" % (
                top.get("source", ""), top.get("path", ""), want_src, want_path))
        if score < min_top1:
            failures.append("top1 相似度 %.4f < %.2f（会被 engine 拒挂，检索形同失效）"
                            % (score, min_top1))
        if score > max_top1:
            failures.append("top1 相似度 %.4f > %.2f（异常偏高，检查夹具与索引是否同源泄漏）"
                            % (score, max_top1))
    return failures, rows


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    min_top1, max_top1 = MIN_TOP1, MAX_TOP1
    for flag, setter in (("--min-top1", "min"), ("--max-top1", "max")):
        if flag in argv:
            i = argv.index(flag)
            try:
                val = float(argv[i + 1])
            except (IndexError, ValueError):
                print("用法: py tools/bench_rag.py [--min-top1 0.55] [--max-top1 0.85]")
                return 2
            if setter == "min":
                min_top1 = val
            else:
                max_top1 = val
            del argv[i:i + 2]
    if argv:
        print("用法: py tools/bench_rag.py [--min-top1 0.55] [--max-top1 0.85]")
        return 2

    if not os.path.exists(str(PROBES_PATH)):
        print("FAIL: 探针夹具不存在 -> %s（先跑 tools/build_rag_probes.py）" % PROBES_PATH)
        return 1
    kb = KB()
    if not kb.chunks:
        print("FAIL: 知识库未加载（%s）" % kb.path)
        return 1
    probes = load_probes()
    failures, rows = check(probes, kb, min_top1=min_top1, max_top1=max_top1)

    print("知识库: %d chunks / model=%s" % (len(kb.chunks), kb.model))
    print("%-6s %-6s %-28s %s" % ("score", "命中", "source", "path"))
    for r in rows:
        print("%-6.4f %-6s %-28s %s" % (r["score"], "OK" if r["hit"] else "MISS",
                                        r["source"][:28], r["path"]))
    if failures:
        for msg in failures:
            print("FAIL:", msg)
        return 1
    lo = min(r["score"] for r in rows) if rows else 0.0
    hi = max(r["score"] for r in rows) if rows else 0.0
    print("PASS: %d/%d top1 命中，相似度区间 %.4f–%.4f（门槛 [%.2f, %.2f]）"
          % (len(rows), len(rows), lo, hi, min_top1, max_top1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
