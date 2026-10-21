# CHANGELOG

本仓从 v0.1.1 开始记录变更。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

## [0.1.1] — 2026-10-22

### 修复

- **安装态不可用（v0.1.0 的发布物缺陷）**：`wheel` 只含 Python 包，`data/`、`code/knowledge/`、
  `code/backend/static/` 都没进去。`pip install`（非 editable）之后：
  - `app.cli compliance` → `FileNotFoundError`（读不到 `危大工程范围清单.json`）
  - `KB()` → `chunks=0` 且**静默**返回空检索结果 → `--rag` 一条条文都挂不上却不报错
  - Web 服务能起，但 `GET /` 无 `index.html`、`/static/*` 全 404

  修法三件：
  1. 新增 `code/backend/app/resources.py`：资产定位统一走"**包内 `app/_data` 优先 → 仓库布局回退**"，
     两条都没有时抛 `AssetMissing`（带已尝试路径 + 修复办法），**不再静默降级**。
  2. 新增 `setup.py` 的 `build_py` 钩子：构建时把四类资产复制进 `app/_data/`，经 `package-data`
     打进 wheel 与 sdist；缺任一资产直接构建失败（不允许"悄悄少装"）。
  3. `rag.py::KB()` / `weida.py::load_list()` / `server.py` 的静态目录全部改用该解析；
     Web 首页在静态资源缺失时返回 **503 + 明确说明**，而不是空白 404。

- **`--rag` 的预检只看配置、不看资产**：现在同时校验知识库可用，缺资产时返回 `2` 并给出指引
  （此前只会在装态下"配置齐全但知识库为空"时静默挂 0 条条文）。

### 新增

- `app.cli selftest` 子命令：逐项报告四类资产（包内/仓库/缺失）+ 三个功能探针
  （阈值清单可读 / 知识库可加载 / Web 首页存在），退出码 `0` 全好、`1` 有缺失。
  这是针对"装完不知道能不能用"的直接对策。
- `code/backend/tests/test_packaging.py`（12 条，其中 2 条标 `packaging`）：
  - 快的 10 条：资源解析顺序、缺失时抛 `AssetMissing`、`KB()` 不静默为空、
    `selftest` 正/负控、`index.html` 引用的静态文件确实存在。
  - 慢的 2 条（`-m packaging`）：**真构建 wheel → 断言四类资产在包里 → 装进临时 venv →
    在仓库外跑 `selftest` 与 `compliance`**，并断言资产来自"包内"而非仓库回退。
    构建前会清理 `app/_data`，防止陈旧产物掩盖构建钩子失效。
- CI `package` job 增加三步装态验证：wheel 资产断言、临时 venv 内仓库外 `selftest`、
  从装好的包跑 `compliance` 并断言有判定结果。
- `construction-check selftest` 控制台入口（README 快速开始已写入）。

### 变更

- 版本 `0.1.0` → `0.1.1`。
- 测试 55 → **67**（新增 12 条打包/装态测试；现有 55 条零修改、零跳过、零删除）。
- README 的「安装形态」一节改写：不再用"按源码仓分发"为装态缺陷免责，改为
  说明 wheel/sdist 都自带资产，并给出打包实测命令。

### 未变

- 数据资产内容零改动：`kb_weida.json` 的 chunks/vectors 逐项未变，
  `危大工程范围清单.json` 的 op/value 阈值一个未动（`bench_consistency` 仍 7/7、15/15、误报 0）。
- 三个基准门槛与执行方式未变（`bench_drawings` F1 ≥ 0.95、`bench_consistency` 全中、
  `bench_rag` top1 命中且 0.55 ≤ score ≤ 0.85）。

## [0.1.0] — 2026-10-21

首次发布。详见 `plan/RELEASE-v0.1.0.md`。

- 修 P0：CLI `run`/`drawing`/`plan` 由"恒 exit 0"改为 `0/1/2`，节点失败/无产物/空参数卡判失败。
- 两个基准脚本加退出码门；新增离线检索门 `bench_rag.py`。
- RAG 依据收紧：只给「危大合规」类挂条文 + `min_score` 0.3 → 0.55。
- 新增 CI（3.10/3.12 × ubuntu-24.04/windows-latest + package）、`pyproject.toml`、`MANIFEST.in`。
- README 自述对齐（`876→873` 并写种子、检索区间改实测值），新增自指门禁。
- 修 Windows 控制台代码页导致的 `UnicodeEncodeError`（`app/console.py`）。
