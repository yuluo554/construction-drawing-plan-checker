# -*- coding: utf-8 -*-
"""规范知识库 RAG —— 向量索引（纯 Python 余弦，条文规模数百条足够）+ 检索。

索引文件：code/knowledge/kb_weida.json
    {"model": "...", "chunks": [{"id","source","path","text"}], "vectors": [[...], ...]}
embedding：阿里云百炼 qwen3.7-text-embedding-flash（1024 维）。
"""
import json
import math
import os

EMBED_MODEL = "qwen3.7-text-embedding-flash"
BATCH = 8
DEFAULT_MIN_SCORE = 0.55   # 相关性门槛（v0.1.0 起；原为 0.3，见 kb_search 说明）


def default_kb_path():
    """知识库路径：包内 app/_data 优先，回退仓库布局；都没有则抛 AssetMissing。

    v0.1.0 的 `KB()` 在文件缺失时静默 chunks=[] → search() 恒返回 []，于是
    `--rag` 挂不上任何条文却不报错。现在改成显式失败（见 app/resources.py）。
    """
    from ..resources import asset_path
    return asset_path("kb")


def embed_texts(texts, model=EMBED_MODEL):
    """批量向量化。返回 [[float,...], ...]"""
    from ..llm.client import load_env
    import requests
    cfg = load_env()
    url = cfg["LLM_BASE_URL"].rstrip("/") + "/embeddings"
    headers = {"Authorization": "Bearer " + cfg["LLM_API_KEY"], "Content-Type": "application/json"}
    vecs = []
    for i in range(0, len(texts), BATCH):
        batch = [t[:1000] for t in texts[i:i + BATCH]]
        r = requests.post(url, headers=headers, timeout=60,
                          json={"model": model, "input": batch})
        r.raise_for_status()
        body = r.json()
        data = sorted(body["data"], key=lambda d: d["index"])
        for d in data:
            emb = d.get("embedding")
            if isinstance(emb, list):
                vecs.append(emb)
            else:  # 个别网关返回异常结构时补零向量，保持索引对齐
                vecs.append([0.0] * 1024)
    return vecs


def _cos(a, b):
    if not isinstance(a, (list, tuple)) or not isinstance(b, (list, tuple)):
        return 0.0
    try:
        dot = 0.0
        na = 0.0
        nb = 0.0
        for x, y in zip(a, b):
            xi = float(x)
            yi = float(y)
            dot += xi * yi
            na += xi * xi
            nb += yi * yi
    except (TypeError, ValueError):
        return 0.0
    na = math.sqrt(na) or 1.0
    nb = math.sqrt(nb) or 1.0
    return dot / (na * nb)


class KB:
    def __init__(self, path=None):
        # path=None 时按"包内 _data 优先、仓库布局回退"解析；找不到就抛 AssetMissing。
        # 显式传 path 时仍要求文件存在（否则就是调用方写错了路径，不该静默变空索引）。
        self.path = path or default_kb_path()
        self.chunks, self.vectors, self.model = [], [], EMBED_MODEL
        if not os.path.exists(self.path):
            from ..resources import AssetMissing
            raise AssetMissing("知识库文件不存在: %s" % self.path)
        self.load(self.path)

    def load(self, path):
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        self.chunks = d["chunks"]
        self.vectors = d["vectors"]
        self.model = d.get("model", EMBED_MODEL)

    def save(self, path=None):
        path = path or self.path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"model": self.model, "chunks": self.chunks, "vectors": self.vectors},
                      f, ensure_ascii=False)

    def add(self, chunks, vectors):
        self.chunks.extend(chunks)
        self.vectors.extend(vectors)

    def search(self, query, top_k=5, min_score=DEFAULT_MIN_SCORE):
        """返回 [{score, source, path, text}]。索引为空时返回 []（不报错，规则通道兜底）。

        低于 min_score 的命中不返回——宁可为空也不要挂不相干条文。
        """
        if not self.chunks:
            return []
        qv = embed_texts([query], model=self.model)[0]
        scored = [(_cos(qv, v), c) for v, c in zip(self.vectors, self.chunks)]
        scored.sort(key=lambda t: t[0], reverse=True)
        return [{"score": round(s, 4), **{k: c.get(k, "") for k in ("source", "path", "text")}}
                for s, c in scored[:top_k] if s >= min_score]


def kb_search(query, top_k=5, kb=None, min_score=DEFAULT_MIN_SCORE):
    """供 Agent 调用的检索工具入口。

    min_score 默认 0.55（v0.1.0 起，原为 0.3）：0.3 对"中文短查询 vs 条文长文本"
    的余弦相似度太松，会把不相干条文挂到结论上（实测 0.3745 被判为命中）。
    调用方（app/rules/engine.py）显式传同一门槛，保证报告口径一致。
    """
    kb = kb or KB()
    return kb.search(query, top_k=top_k, min_score=min_score)
