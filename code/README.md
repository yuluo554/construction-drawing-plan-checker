# 智建赛题10 —— 施工图与施工方案协同智能系统（代码）

> 技术方案见 `../plan/`（00 总览 → 03 模块设计）；数据见 `../data/`。
> 当前进度：**阶段5 完成**（Web 服务 + 前端界面：上传/校核面板/PDF 证据高亮/报告下载），阶段6 将做评测完善、技术报告、演示视频与 Docker 打包。

## Web 界面（一条命令）

```bash
cd code/backend
py -m uvicorn app.server:app --port 8000
# 浏览器打开 http://127.0.0.1:8000
# 上传图纸(PDF/DXF) + 方案(docx) → 开始协同校核 → 问题清单/条文依据/PDF bbox 高亮定位 → 下载报告 docx
```

## 端到端一条命令（CLI 版）

```bash
cd code/backend
py -m app.cli run ../data/施工图纸/自制样例/sample_beam_plan.dxf \
                  ../data/施工方案/自制样例/sample_formwork_plan_13.docx \
                  -o 输出目录 --llm --rag
# → 控制台: 结论/汇总/各节点耗时; 输出目录: 校核结果.json + 校核报告.docx
```

## 目录

```
code/
├── backend/
│   ├── app/
│   │   ├── cli.py                  # 命令行入口（run/drawing/plan/compliance/check）
│   │   ├── schemas/parameter_card.py   # 工程参数卡（统一中间表示，含证据溯源）
│   │   ├── parsers/
│   │   │   ├── pingfa.py           # 平法标注解析器（梁/柱/板/材料，规则版+分段切分）
│   │   │   ├── pingfa_llm.py       # 平法 LLM 兜底（合法性校验，conf=0.8）
│   │   │   ├── dxf_parser.py       # DXF 图纸解析（ezdxf，行聚类+x邻近分链）
│   │   │   ├── pdf_parser.py       # 矢量 PDF 解析（PyMuPDF，bbox 证据定位）
│   │   │   ├── docx_parser.py      # 施工方案解析（章节树+表格键值+规则抽取）
│   │   │   └── textutil.py         # 文本行聚类合并工具
│   │   ├── rules/
│   │   │   ├── consistency.py      # 图纸×方案一致性校验（消歧/单位换算/冲突分级）
│   │   │   ├── engine.py           # 规则引擎（一致性+危大+存在性 三通道汇总）
│   │   │   └── weida.py            # 危大工程识别引擎（37号令/31号文阈值表驱动）
│   │   ├── knowledge/rag.py        # 规范知识库 RAG（百炼 embedding + 纯Python余弦检索）
│   │   ├── server.py               # Web 服务（上传/解析/校核/报告下载，静态托管）
│   │   ├── agent/
│   │   │   ├── workflow.py         # 轻量状态机（节点/边/条件路由/重试/耗时，LangGraph同语义）
│   │   │   └── orchestrator.py     # 端到端编排：intake→解析图纸→解析方案→校核→报告
│   │   ├── report/export.py        # 校核报告 docx 导出（汇总+分级清单+签署栏）
│   │   └── llm/
│   │       ├── client.py           # OpenAI兼容客户端（百炼；enable_thinking可关；JSON截断修复）
│   │       └── extract_plan.py     # 方案 LLM 结构化抽取（候选行压缩+防幻觉回溯校验）
│   ├── static/                     # 免构建前端（index.html + app.js + style.css + vendor: Vue3/PDF.js）
│   ├── tools/                      # 数据生成与评测（图纸/方案生成、两项基准、KB构建）
│   └── tests/                      # 26 个单元/集成测试（含 Web API 测试）
├── rules/checks.json               # 校核规则库元数据（可审阅增删）
└── knowledge/kb_weida.json         # 规范条文向量索引（55 块）
```

## 快速开始

```bash
cd code/backend
py -m pip install -r requirements.txt

# 1) 解析图纸（DXF 或矢量 PDF）→ 图纸参数卡
py -m app.cli drawing ../../data/施工图纸/自制样例/sample_beam_plan.dxf -o out_drawing.json

# 2) 解析施工方案（docx）→ 方案参数卡
py -m app.cli plan "../../data/施工方案/高支模专项施工方案样例(CallStorm-SmartReview仓库).docx" -o out_plan.json

# 3) 危大合规判定（输入方案参数卡）
py -m app.cli compliance out_plan.json
```

运行测试：`py -m pytest tests/ -q`（14 项全通过）

## 已验证能力（阶段1–4，2026-09-26）

| 能力 | 验证方式 | 结果 |
|------|----------|------|
| 平法标注解析（梁/柱/板集中标注） | **30 张随机图纸基准 vs 真值** | 876 字段 **P=R=F1=1.00**（0误报0漏报） |
| 矢量 PDF 解析（含 bbox 证据） | fitz 生成 PDF → 参数卡 | 22 参数全带页码+bbox |
| 方案规则抽取（章节树+表格键值） | 8万字真实高支模方案样例（含真实联系方式，**未随仓库分发**；可用 `tools/gen_sample_plan.py` 自制样例复现同类测试） | 174 节章节树、40 参数带章节证据 |
| **方案 LLM 结构化抽取**（阶段2） | 同上 docx，1341 候选行 | **202 条抽取、5 条幻觉拦截、0 失败**，参数总量 228 |
| **平法 LLM 兜底**（阶段2） | 异体写法 'L-5b 250x500 B12@150(2)' | conf=0.8 正确抽取，非法值拦截 |
| **规范 RAG 检索**（阶段3） | 48号指南+危大清单 → 55 条文块，5 类问题检索 | 全部命中（top1 分数 0.55–0.80） |
| **一致性校验**（阶段3） | **15 组配对数据（植入已知差异）** | **植入差异检出 7/7、危大判定 15/15、误报 0** |
| **端到端编排**（阶段4） | `run` 命令跑真实配对数据 | 5 节点全通（0.23+0.06+0.83s），docx+json 落盘 |
| **报告导出**（阶段4） | 校核报告.docx | 汇总+分级问题清单（含双侧证据/条文依据）+签署栏 |
| **多值消歧**（阶段4） | 方案同属性多值 | 转"待人工确认"(一般)，不误报致命 |
| 危大识别（基坑/模板/脚手架阈值） | 3.1m/5.2m/6m/8.5m/30m 用例 | 危大/超规模分级全对 |

### 质量基线：24/24 测试通过

### 端到端演示（CLI）

```bash
py -m app.cli drawing  ../data/施工图纸/自制样例/sample_beam_plan.dxf  -o d.json
py -m app.cli plan     ../data/施工方案/自制样例/sample_formwork_plan_13.docx -o p.json
py -m app.cli check    d.json p.json --rag     # → 结论/致命2/一般/提示 + 条文依据
```

## 设计约定

- **每条参数必须带证据**（文档/页码/章节/bbox/原文），无证据不入库；
- **规则优先、LLM 兜底**：规则命中不耗 API；LLM 值必须回溯原文（防幻觉校验），conf=0.85/0.8 标记来源；
- 数值非法（超范围）直接丢弃，宁可漏抽不可错抽；
- LLM 客户端：OpenAI 兼容（阿里云百炼 .env 配置），`enable_thinking=False` 提速，JSON 截断自动修复；
- Python ≥3.8（当前 3.8.8），依赖见 requirements.txt。

## 路线图（对应 plan/05 里程碑）

- 阶段5：FastAPI 服务 + Vue3 前端（上传/PDF高亮定位/校核面板/报告预览）
- 阶段6：评测完善 + 技术报告 + 演示视频 + Docker 打包
