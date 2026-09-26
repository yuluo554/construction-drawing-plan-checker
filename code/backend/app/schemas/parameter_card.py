# -*- coding: utf-8 -*-
"""工程参数卡 Schema —— 图纸/方案解析的统一中间表示。

设计要点（见 plan/02 §4、plan/03）：
- 每个参数必须携带证据（来源文档、页码/章节、bbox、原文片段）；
- source 区分来自图纸(drawing)还是方案(plan)，供后续一致性校核对齐。
"""
import json
from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class Evidence:
    """参数证据：可回溯到原文位置。"""
    doc: str = ""            # 文档文件名
    page: int = -1           # 图纸页码 / 方案中的序号
    section: str = ""        # 方案章节号（如 "3.2"），图纸为空
    bbox: Optional[list] = None  # [x0, y0, x1, y1]，PDF 坐标；无则 None
    raw: str = ""            # 原文片段

    def to_dict(self):
        return asdict(self)


@dataclass
class Parameter:
    """单条参数：实体-属性-值。"""
    entity: str              # 实体名（梁KL1 / 基础底板混凝土 / 落地扣件式脚手架 …）
    category: str            # 类别：component构件 / material材料 / measure措施参数 / overview工程概况
    attr: str                # 属性（截面 / 强度等级 / 立杆纵距 / 开挖深度 …）
    value: str               # 归一化字符串值
    unit: str = ""           # 单位
    conf: float = 1.0        # 置信度 0~1（规则=1.0，LLM/OCR 更低）
    source: str = "drawing"  # drawing | plan
    evidence: Optional[Evidence] = None

    def to_dict(self):
        d = asdict(self)
        d["evidence"] = self.evidence.to_dict() if self.evidence else None
        return d


@dataclass
class ParameterCard:
    """一份文档解析后的完整参数卡。"""
    doc_type: str = "drawing"           # drawing | plan
    file: str = ""                      # 源文件路径
    meta: dict = field(default_factory=dict)   # 图框元数据 / 方案工程概况
    parameters: List[Parameter] = field(default_factory=list)
    extras: dict = field(default_factory=dict)  # 图纸：图层/文本统计；方案：章节树/表格数
    warnings: List[str] = field(default_factory=list)

    def add(self, param: Parameter):
        self.parameters.append(param)

    def to_dict(self):
        return {
            "doc_type": self.doc_type,
            "file": self.file,
            "meta": self.meta,
            "parameters": [p.to_dict() for p in self.parameters],
            "extras": self.extras,
            "warnings": self.warnings,
        }

    def save_json(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @staticmethod
    def load_json(path: str) -> "ParameterCard":
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        card = ParameterCard(doc_type=d.get("doc_type", ""), file=d.get("file", ""),
                             meta=d.get("meta", {}), extras=d.get("extras", {}),
                             warnings=d.get("warnings", []))
        for p in d.get("parameters", []):
            ev = p.get("evidence")
            card.parameters.append(Parameter(
                entity=p.get("entity", ""), category=p.get("category", ""),
                attr=p.get("attr", ""), value=p.get("value", ""), unit=p.get("unit", ""),
                conf=p.get("conf", 1.0), source=p.get("source", "drawing"),
                evidence=Evidence(**ev) if ev else None))
        return card
