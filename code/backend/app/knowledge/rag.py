# -*- coding: utf-8 -*-
"""规范知识库 RAG —— 向量索引（纯 Python 余弦，条文规模数百条足够）+ 检索。

索引文件：code/knowledge/kb_weida.json
    {"model": "...", "chunks": [{"id","source","path","text"}], "vectors": [[...], ...]}
embedding：阿里云百炼 qwen3.7-text-embedding-flash（1024 维）。
"""
import json
import math
import os
from pathlib import Path

KB_PATH = Path(__file__).resolve().parents[3] / "knowledge" / "kb_weida.json"
EMBED_MODEL = "qwen3.7-text-embedding-flash"
BATCH = 8


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
    def __init__(self, path=KB_PATH):
        self.path = path
        self.chunks, self.vectors, self.model = [], [], EMBED_MODEL
        if path and os.path.exists(path):
            self.load(path)

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

    def search(self, query, top_k=5, min_score=0.3):
        """返回 [{score, source, path, text}]。索引为空时返回 []（不报错，规则通道兜底）。"""
        if not self.chunks:
            return []
        qv = embed_texts([query], model=self.model)[0]
        scored = [(_cos(qv, v), c) for v, c in zip(self.vectors, self.chunks)]
        scored.sort(key=lambda t: t[0], reverse=True)
        return [{"score": round(s, 4), **{k: c.get(k, "") for k in ("source", "path", "text")}}
                for s, c in scored[:top_k] if s >= min_score]


def kb_search(query, top_k=5, kb=None):
    """供 Agent 调用的检索工具入口。"""
    kb = kb or KB()
    return kb.search(query, top_k=top_k)
