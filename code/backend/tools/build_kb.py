# -*- coding: utf-8 -*-
"""构建规范知识库：48号指南 docx + 危大清单 JSON → 条文块 → 向量索引。

运行：cd code/backend && py tools/build_kb.py
输出：code/knowledge/kb_weida.json
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

REPO = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
GUIDE_DOCX = os.path.join(REPO, "data", "法规标准",
                          "建办质〔2021〕48号-危险性较大的分部分项工程专项施工方案编制指南.docx")
WEIDA_JSON = os.path.join(REPO, "data", "法规标准", "危大工程范围清单.json")
KB_OUT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "knowledge",
                                       "kb_weida.json"))

MAX_CHUNK = 420  # 字符，超过则续块


def docx_chunks(path):
    """48号指南 → 条文块（章节路径 + 合并短段）。"""
    import docx as docx_lib
    document = docx_lib.Document(path)
    chunks = []
    path_stack = []  # [(level, title)]
    buf = []

    def flush():
        text = "\n".join(buf).strip()
        buf.clear()
        if len(text) < 15:
            return
        while len(text) > MAX_CHUNK * 1.6:
            cut = text.rfind("。", 0, MAX_CHUNK)
            cut = cut if cut > 100 else MAX_CHUNK
            chunks.append(text[:cut + 1])
            text = text[cut + 1:]
        chunks.append(text)

    p = docx_lib.Document(path).paragraphs
    for para in p:
        text = para.text.strip()
        if not text:
            continue
        style = ""
        try:
            style = para.style.name or ""
        except Exception:
            pass
        is_head = ("Heading" in style or "标题" in style) and len(text) < 40
        if is_head:
            flush()
            try:
                level = int("".join(ch for ch in style if ch.isdigit()) or 1)
            except ValueError:
                level = 1
            path_stack = [x for x in path_stack if x[0] < level] + [(level, text)]
        else:
            buf.append(text)
            if sum(len(x) for x in buf) > MAX_CHUNK:
                flush()
    flush()
    spath = " > ".join(t for _, t in path_stack[-3:]) if path_stack else ""
    return [{"id": "g%d" % i, "source": "建办质〔2021〕48号 专项施工方案编制指南",
             "path": spath, "text": c} for i, c in enumerate(chunks)]


def weida_chunks(path):
    """危大清单 JSON → 人类可读阈值条文块。"""
    with open(path, "r", encoding="utf-8") as f:
        spec = json.load(f)

    def cond_text(cond):
        if "rules" in cond:
            return "；".join(cond_text(r) for r in cond["rules"])
        if cond.get("op") == "true":
            return str(cond.get("param", ""))
        return "%s %s %s%s" % (cond.get("param", ""), cond.get("op", ">="), cond.get("value", ""),
                               cond.get("unit", "") and (" " + cond["unit"]))

    out = []
    for level, key in (("危大(须专项施工方案)", "危大工程范围_附件1"),
                       ("超规模(须专家论证)", "超过一定规模_附件2_须专家论证")):
        for r in spec.get(key, []):
            conds = []
            for cond in r.get("触发条件", []):
                if "rules" in cond:
                    conds.extend(cond_text(sub) for sub in cond["rules"])
                else:
                    conds.append(cond_text(cond))
            text = "【%s|%s】触发条件：%s。管理要求：%s" % (
                level, r.get("类别", ""), "；".join(conds),
                "组织专家论证后方可实施" if level.startswith("超规模") else "编制专项施工方案并按规定审批")
            out.append({"id": "w%d" % len(out), "source": "住建部令37号/建办质〔2018〕31号附件",
                        "path": r.get("类别", ""), "text": text})
    # 程序合规链条
    for i, item in enumerate(spec.get("程序合规链条", [])):
        out.append({"id": "p%d" % i, "source": "住建部令37号 危大工程管理规定",
                    "path": "管理程序", "text": item})
    return out


def main():
    from app.knowledge.rag import KB, embed_texts
    chunks = docx_chunks(GUIDE_DOCX) + weida_chunks(WEIDA_JSON)
    print("条文块:", len(chunks))
    kb = KB(KB_OUT)
    vectors = embed_texts([c["text"] for c in chunks])
    kb.add(chunks, vectors)
    kb.save()
    print("索引保存:", KB_OUT, "| 总条数:", len(kb.chunks))


if __name__ == "__main__":
    main()
