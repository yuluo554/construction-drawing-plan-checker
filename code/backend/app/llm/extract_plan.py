# -*- coding: utf-8 -*-
"""方案 LLM 结构化抽取 —— 候选行压缩 + 防幻觉校验。

流程（控制成本与幻觉）：
1. 压缩：仅收集含数字或关键名词的段落/表格行，编号为 [L1]…[Ln]；
2. 抽取：一次 LLM 调用（JSON 模式），要求每条输出携带 原文编号+原文摘录；
3. 校验：原文摘录必须是候选行子串、值必须出现在摘录中，否则丢弃（防幻觉）；
4. 产物：Parameter 列表（conf=0.85, source="plan"）。
"""
import re
from ..schemas.parameter_card import Parameter, Evidence

CANDIDATE_RE = re.compile(
    r"\d|混凝土|强度|等级|钢筋|直径|间距|步距|立杆|横距|纵距|高度|深度|厚度|跨度|荷载|"
    r"基坑|支撑|支架|脚手架|模板|层数|面积|结构|基础|悬挑|锚固|扣件|钢管|托座|边坡|支护")
MAX_LINES_PER_CALL = 140
MAX_LINE_LEN = 160

PROMPT_TEMPLATE = """以下是从一份施工方案中筛选出的候选行（已编号）。请抽取工程参数。

【抽取范围】混凝土强度等级、钢筋规格、构件截面、脚手架参数（立杆间距/步距/搭设高度/悬挑长度）、
模板支撑参数（支架高度/立杆间距/步距/面板厚度）、基坑参数（开挖深度/支护形式）、
工程概况（建筑面积/层数/结构形式/基础形式/建筑高度）、危大相关参数（支撑高度/基坑深度/搭设高度）。

【硬性规则】
1. 每条输出必须给 原文编号 与 原文摘录；原文摘录必须逐字取自该候选行，不得改写；
2. 值必须出现在原文摘录中；原文没有的参数不要编造；
3. 单位跟随原文（m/mm/kN/m²），数值保持原样不要换算；
4. 只输出 JSON：{{"参数":[{{"实体":"...","属性":"...","值":"...","单位":"...","类别":"material|measure|overview","原文编号":"L12","原文摘录":"..."}}]}}

候选行：
{lines}"""


def collect_candidates(document, outline, section_of):
    """收集候选行 → [(编号, 行文本, pidx, tablerow, 章节号)]。"""
    candidates = []
    seen = set()
    for i, para in enumerate(document.paragraphs):
        text = re.sub(r"\s+", " ", para.text.strip())
        if not text or len(text) > MAX_LINE_LEN:
            continue
        if not CANDIDATE_RE.search(text):
            continue
        if text in seen:
            continue
        seen.add(text)
        candidates.append((text, i, None))
    # 表格行（拼接整行，键值对通常跨格）
    try:
        from docx.table import Table
        from docx.text.paragraph import Paragraph
        pcount = 0
        for child in document.element.body.iterchildren():
            if child.tag.endswith("}p"):
                pcount += 1
            elif child.tag.endswith("}tbl"):
                tbl = Table(child, document)
                pcount += 1
                for row in tbl.rows:
                    cells = [re.sub(r"\s+", " ", c.text.strip()) for c in row.cells]
                    cells = [c for c in cells if c]
                    if not cells:
                        continue
                    line = " | ".join(cells)
                    if len(line) > MAX_LINE_LEN or line in seen or not CANDIDATE_RE.search(line):
                        continue
                    seen.add(line)
                    candidates.append((line, pcount - 1, line))
    except Exception:
        pass
    sec_of = {text: section_of(pidx) for text, pidx, _ in candidates}
    return [(("L%d" % (i + 1)), text, pidx, tablerow, sec_of[text])
            for i, (text, pidx, tablerow) in enumerate(candidates)]


def extract_with_llm(document, outline, filename, client=None):
    """返回 (params, stats)。stats 含 候选数/抽取数/幻觉拦截数。"""
    if client is None:
        from .client import chat_json as client
    sec_of_func = lambda pidx: _current_section(outline, pidx)  # noqa: E731
    cands = collect_candidates(document, outline, sec_of_func)
    params = []
    blocked = 0
    norm = lambda s: re.sub(r"\s+", "", s)  # noqa: E731

    for start in range(0, len(cands), MAX_LINES_PER_CALL):
        batch = cands[start:start + MAX_LINES_PER_CALL]
        lines_block = "\n".join("%s %s" % (lid, text) for lid, text, _, _, _ in batch)
        by_id = {lid: (text, pidx, tablerow, sec) for lid, text, pidx, tablerow, sec in batch}
        try:
            data = client(PROMPT_TEMPLATE.format(lines=lines_block), max_tokens=6000)
            items = data.get("参数", []) if isinstance(data, dict) else []
        except Exception as exc:
            params.append(_err_param("LLM调用失败: %s" % exc))
            continue
        for it in items:
            lid = str(it.get("原文编号", "")).strip()
            quote = str(it.get("原文摘录", "")).strip()
            if lid not in by_id:
                blocked += 1
                continue
            src, pidx, tablerow, sec = by_id[lid]
            # 防幻觉：摘录必须逐字来自候选行（忽略空白差异），且值出现在摘录中
            if norm(quote) and norm(quote) not in norm(src):
                blocked += 1
                continue
            value = str(it.get("值", "")).strip()
            if not value or (norm(value) and norm(value) not in norm(quote)) :
                blocked += 1
                continue
            ev = Evidence(doc=filename, page=pidx, section=sec, raw=(tablerow or quote)[:160])
            params.append(Parameter(
                entity=str(it.get("实体", "")).strip() or "未分类",
                category=str(it.get("类别", "")).strip() or "measure",
                attr=str(it.get("属性", "")).strip() or "未分类",
                value=value, unit=str(it.get("单位", "")).strip(),
                conf=0.85, source="plan", evidence=ev))
    stats = {"候选行": len(cands), "LLM抽取": len(params), "幻觉拦截": blocked}
    return params, stats


def _current_section(outline, pidx):
    sec = ""
    for item in outline:
        if item["pidx"] <= pidx and item["num"]:
            sec = item["num"]
    return sec


def _err_param(msg):
    p = Parameter(entity="__error__", category="error", attr="llm", value=msg, source="plan")
    return p
