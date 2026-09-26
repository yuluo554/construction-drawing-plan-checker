# -*- coding: utf-8 -*-
"""平法标注 LLM 兜底解析 —— 规则未命中时由大模型抽槽位，结果经合法性校验。

开关：pingfa.set_llm_fallback(True)（CLI --llm 时开启；默认关闭以控制成本）。
防幻觉：LLM 输出的直径/间距/数量必须落在工程合法范围内，否则丢弃。
"""
from typing import List, Optional

from ..schemas.parameter_card import Parameter, Evidence

_FALLBACK_ON = False
_DIA_RANGE = (4, 40)
_SP_RANGE = (50, 400)
_LEGAL_SYMS = {"Φ", "φ", "C", "B", "D", "E", "A"}

PROMPT = """从下面的平法标注文本中抽取钢筋参数槽位，输出JSON（没有对应槽位就不要输出）：
{{"箍筋":{{"直径":8,"间距加密":100,"间距非加密":200,"肢数":2,"符号":"Φ"}},
"上部通长筋":{{"数量":2,"符号":"Φ","直径":22}},
"下部纵筋":{{"数量":3,"符号":"Φ","直径":18}},
"腰筋":{{"类型":"G","数量":4,"符号":"Φ","直径":12}},
"全部纵筋":{{"数量":24,"符号":"Φ","直径":22}},
"截面":{{"宽":300,"高":600}}}}
标注文本：{text}"""


def set_llm_fallback(on: bool):
    global _FALLBACK_ON
    _FALLBACK_ON = on


def _ok(v, rng):
    try:
        return rng[0] <= float(v) <= rng[1]
    except (TypeError, ValueError):
        return False


def parse_with_llm(text: str, ev: Optional[Evidence] = None) -> List[Parameter]:
    """LLM 兜底：返回合法参数列表（conf=0.8）。"""
    try:
        from ..llm.client import chat_json
        data = chat_json(PROMPT.format(text=text), max_tokens=800, temperature=0)
    except Exception:
        return []
    out: List[Parameter] = []

    def _p(entity, attr, value, unit="mm"):
        out.append(Parameter(entity=entity, category="component", attr=attr,
                             value=str(value), unit=unit, conf=0.8,
                             source="drawing", evidence=ev))

    m = data.get("截面") or {}
    if _ok(m.get("宽"), (100, 2000)) and _ok(m.get("高"), (150, 3000)):
        _p("构件(待归类)", "截面", "%sx%s" % (int(float(m["宽"])), int(float(m["高"]))))

    s = data.get("箍筋") or {}
    if _ok(s.get("直径"), _DIA_RANGE) and _ok(s.get("间距加密"), _SP_RANGE):
        sym = s.get("符号") if s.get("符号") in _LEGAL_SYMS else "Φ"
        val = "%s%s@%s" % (sym, int(float(s["直径"])), int(float(s["间距加密"])))
        if s.get("间距非加密"):
            val += "/%s" % int(float(s["间距非加密"]))
        if s.get("肢数"):
            val += "(%s肢)" % int(float(s["肢数"]))
        _p("构件(待归类)", "箍筋", val)

    for key, attr in (("上部通长筋", "上部通长筋"), ("下部纵筋", "下部纵筋"),
                      ("腰筋", "腰筋"), ("全部纵筋", "全部纵筋")):
        d = data.get(key) or {}
        if _ok(d.get("直径"), _DIA_RANGE) and d.get("数量"):
            sym = d.get("符号") if d.get("符号") in _LEGAL_SYMS else "Φ"
            _p("构件(待归类)", attr, "%s%s%s" % (int(float(d["数量"])), sym, int(float(d["直径"]))))
    return out
