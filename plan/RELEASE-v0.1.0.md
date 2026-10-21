# RELEASE-v0.1.0：construction-drawing-plan-checker 首次成版

> 起点：**从未发布**（无 tag / 无 Release / 无 `pyproject.toml` / 无 CI，单提交 `1d8dd37`，2026-09-26）。
> 本轮跃迁：**0 → v0.1.0**。执行日 **2026-10-21**。
> 交接物在 `update/`（4 个诊断文件 + 1 个更正文件）；执行方报告状态：**待复验**。
>
> **阅读提示（tag↔台账循环依赖）**：§一 ~ §二 + §三.3 属于 **tag 时点**内容，已随 tag 树发布。
> **§三.1 / §三.2 / §六 / §七-1 的 Release 与 CI 实测数字是在打 tag 之后补写的**，
> 因此它们只存在于 tag 之后的提交里，不在 tag 树内。
> 权威来源优先级：**GitHub Release 页面 / tag 消息 / `SHA256SUMS` 附件 → 本文件的 tag 后章节 → tag 树里的 tag 时点章节**。

---

## 一、决策记录（用户拍板 2026-10-21，未自行决定）

| 编号 | 决策点 | 选定 | 落地位置 |
|---|---|---|---|
| **DEC1** | Python floor 与 3.8 宣称 | **B：抬到 `>=3.10`** | `pyproject.toml` `requires-python`；CI 矩阵 `{3.10, 3.12} × {ubuntu, windows}`；README 徽章 `python-3.10%2B`；README 快速开始"环境要求" |
| **DEC2** | RAG 相关性怎么收紧 | **C+A：限定类别 + `min_score` 0.55** | `app/rules/engine.py`（`RAG_ELIGIBLE_TYPES`、`RAG_MIN_SCORE`）、`app/knowledge/rag.py`（`DEFAULT_MIN_SCORE`、`kb_search(min_score=)`）、`app/report/export.py`（"未检索到匹配条文"可见化） |
| **DEC3** | 基准脚本门槛 | **A：沿用 README 表里的门槛** | `tools/bench_drawings.py`（`MIN_F1 = 0.95`）、`tools/bench_consistency.py`（`MIN_WEIDA_RATE = 1.0`、`MAX_FALSE_FATAL = 0`）——两条都 `sys.exit(0/1)` |
| **DEC4** | v0.1.0 Release 形态 | **B：附 `git archive` 的 source zip** | 本文件 §三「Release」；`dist/` 由 CI 的 `package` job 产出（另附） |

---

## 二、tag 时点事实（这部分在打 tag 时定稿，tag 之后不得改写）

> 填写口径：只写**不变量**与**外部可复现的编号**；凡是"仓库内文件自身的 sha256"不写在这里（循环依赖），改记在 `.sha256` 附件与 tag 消息里。

| 项 | 值 |
|---|---|
| 出发点 HEAD | `1d8dd37d0206ebbd55eec73b642a9f986729ffb2`（单提交，2026-09-26） |
| 起点 tag / Release | 无 / 无 |
| 版本号 | `0.1.0`（`pyproject.toml`；**首次发布**，无旧 tag 需避让） |
| 包名 | `construction-drawing-plan-checker`（分发名）/ `app`（导入名） |
| requires-python | `>=3.10` |
| CI 文件 | `.github/workflows/ci.yml`（`test` 四腿 + `package` 一腿） |
| 测试数 | **55 项**（起点 26）：`test_cli_exit_codes.py` 13、`test_rag_relevance.py` 5、`test_self_reported_numbers.py` 11 为新增 |
| 基准（真门） | `bench_drawings.py 30 1` → TP 873 / FP 0 / FN 0，6 字段 F1 全 1.00；`bench_consistency.py 15 1` → 7/7 / 15/15 / 误报 0；`bench_rag.py` → 5/5 top1 命中（0.6514–0.8021） |
| 端到端 | `run ... --rag` → 致命 2 / 一般 0 / 提示 2；两份产物齐备；`R-C-001` 条文状态"不适用"、`R-W-000` 条文 score 0.8294 |

### tag 时点的提交

- tag 指向的提交：**`8b92e647ffcf1d3afd310f018b82acca17733021`**（= CI 绿的那个提交，run `39629831085`，5/5 job success，注解 0 条）
- tag 对象（annotated）：`4d23f43e85d7866088a9704d26f9be637e52c534`；剥离后 `^{}` → `8b92e64`
  验证：`git cat-file -t v0.1.0` → `tag`；`git rev-list -n1 v0.1.0` → `8b92e64…`
- tag 消息要点：首次发布；DEC1–DEC4 见本文件 §一；起点 `1d8dd37`；CI run id。

---

## 三、tag 后追加事实（追加提交 / Release 附件 / 复验记录）

### 3.1 Release（已建）

| 项 | 值 |
|---|---|
| Release URL | https://github.com/yuluo554/construction-drawing-plan-checker/releases/tag/v0.1.0 |
| tag | `v0.1.0`（annotated `4d23f43`，剥离 → `8b92e64`） |
| Release 标题 | `v0.1.0 — 首次发布：CLI 退出码 / RAG 相关性 / CI / 打包元数据` |
| draft / prerelease | false / false（Latest） |
| 附件 1（DEC4=B） | `construction-drawing-plan-checker-v0.1.0-source.zip` — **2,529,787 B**，sha256 `de250a979af712b5175cc3e4c12242a4a3912217ac63c0c38f9bff0d94827611`；GitHub 记录的 digest 与本地**逐字符相同** |
| 附件 2 | `SHA256SUMS` — 118 B，sha256 `d1cf2c18637fa34017d0ffe43c27cf2ab3ad24522fc96244b42edcd610951b67` |
| 附件来源 | `git archive --format=zip --prefix=construction-drawing-plan-checker-v0.1.0/ -o <zip> v0.1.0` |
| 可复算性（实测） | 独立重建两次 → `cmp` **BYTE-IDENTICAL**，两次 sha256 同为 `de250a97…` |
| 下载复验（实测） | `gh release download` 匿名取回两附件 → `sha256sum -c SHA256SUMS` → **OK** |

### 3.2 发布物自证（无 `.git` 的源码包，实测）

从 Release 真下载的 zip 解压后（155 条目 / 125 文件 / **无 `.git`**）：

| 检验 | 结果 |
|---|---|
| `pip install -e ".[dev]"` | rc=0 |
| `pytest -q` | **54 passed, 1 skipped**（skip 的是需要本机敏感 docx 的那条 `test_integration.py:68`，属正确跳过） |
| `bench_drawings.py 30 1` | rc=**0**（6 字段 F1 ≥ 0.95） |
| `bench_consistency.py 15 1` | rc=**0**（7/7、15/15、误报 0） |
| `bench_rag.py` | rc=**0**（5/5、0.6514–0.8021） |
| `app.cli run /nonexist.dxf /nonexist.docx` | rc=**2**（负控成立） |
| `bench_drawings.py 30 1 --min-f1 1.01` | rc=**1**（负控成立） |
| `bench_rag.py --min-top1 0.9` | rc=**1**（负控成立） |
| `app.cli run <有效对> -o /tmp/e2e-rel` | rc=**0**，结论`存在致命问题，须整改后实施｜致命2 一般0 提示2`，两份产物齐备 |
| `pyproject.toml` 版本 | `version = "0.1.0"` |

### 3.3 本批改动（提交）

| 提交 | 内容 |
|---|---|
| `3e079cb` | v0.1.0 首次发布主体（D1/D3/D4/D2/D5/D8/D6/D7 全部改动） |
| `7438f46` | 修 CI Windows 腿：控制台中文输出在非 UTF-8 代码页下抛 `UnicodeEncodeError`（新增 `app/console.py`，五个入口统一调用；3 条回归测试；测试计数口径禁止 `parametrize`） |
| `9990153` | CI 端到端步骤改单行（pwsh 不识别 `\` 续行） |
| `02ea1c8` | CI 产物断言改纯 ASCII 输出（中文文件名不能直接 print） |
| `8955b66` | CI 产物断言只打印"计数 + ASCII 转义名" + 工作流级 `PYTHONUTF8=1` |
| `8b92e64` | CI ubuntu 腿钉 `ubuntu-24.04`（消除 `ubuntu-latest` 迁移注解，注解归零） |

> 说明：CI 连红四轮，全部根因是**同一个产品缺陷**（Windows 控制台代码页）与**两处工作流书写问题**（pwsh 续行、日志打印中文）。
> 第 2 条（`app/console.py`）是**真实的产品修复**：开发者在中文 Windows 的 cmd 里跑 `py -m app.cli --help` 本来就会崩。
> 第 4/5 条只影响 CI 日志，不放松任何判据。

### 3.3 复验命令（任何人可跑）

```bash
# 1. tag 与 CI 一致性
git rev-list -n1 v0.1.0
gh run list --repo yuluo554/construction-drawing-plan-checker --limit 1 \
  --json databaseId,headSha,conclusion,createdAt

# 2. 附件可逐字节重建（在干净 clone 里）
git clone --branch v0.1.0 https://github.com/yuluo554/construction-drawing-plan-checker.git cdpc-tag
cd cdpc-tag
git archive --format=zip --prefix=construction-drawing-plan-checker-v0.1.0/ \
  -o /tmp/rebuilt.zip v0.1.0
sha256sum /tmp/rebuilt.zip   # 与 Release 附件逐字节比对

# 3. 从 tag 树跑自带的门与测试（无 API Key 也能跑）
py -3.12 -m venv /tmp/verify && /tmp/verify/Scripts/pip install -e ".[dev]"
pytest -q                                   # 期望 55 passed
cd code/backend
py tools/bench_drawings.py 30 1             # 期望 exit 0
py tools/bench_consistency.py 15 1          # 期望 exit 0
py tools/bench_rag.py                       # 期望 exit 0（离线，零 API）

# 4. 负控（每条都必须红）
py -m app.cli run /nonexist.dxf /nonexist.docx -o /tmp/o   ; echo $?   # 期望 2
py tools/bench_drawings.py 30 1 --min-f1 1.01              ; echo $?   # 期望 1
py tools/bench_rag.py --min-top1 0.9                       ; echo $?   # 期望 1
```

---

## 四、本批修改清单（逐文件 + 理由）

### 批次 1：退出码与失败可见性（D1 + D3）

| 文件 | 改动 | 理由 |
|---|---|---|
| `code/backend/app/cli.py` | `main()` 返回 int；`__main__` 用 `sys.exit(main())`；五个子命令分别返回 0/1/2；新增 `_require_files`（缺文件→2）、`_check_rag_config`（缺 embedding 配置→2，**在 check 之前**）、`_empty_parse_error`（解析 0 参数→1）；`run` 分支检查 `_trace` 的 `ok`、结果文件存在、两侧参数卡非空 | 修 D1：原本无任何 `return`/`sys.exit`，三子命令恒 exit 0；`--rag` 缺 Key 时崩在 check 却报成功且产物目录为空 |
| `code/backend/tools/bench_drawings.py` | 新增 `MIN_F1=0.95` 门槛、逐字段比对、`--min-f1` 开关、`main()` 返回码 + `sys.exit` | 修 D3 附项：基准原本无退出码门（F1 掉到 0.5 仍 exit 0） |
| `code/backend/tools/bench_consistency.py` | 新增 `MIN_WEIDA_RATE=1.0` / `MAX_FALSE_FATAL=0`、三项指标断言、`main()` 返回码 + `sys.exit` | 同上 |
| `code/backend/tests/test_cli_exit_codes.py`（新，13 条） | subprocess 断言：3 条缺文件→2、未知子命令→2、2 条坏输入→1、缺 Key `--rag`→2、正控→0、两个 bench 的正/负控、**3 条非 UTF-8 控制台**（`cli --help` / `bench_rag` / helper 单测） | 让 D1/D3 与跨平台编码有机器信号；**不 mock、不看 stdout**（本仓的原始缺陷正是"打印正常但 exit 0"） |
| `code/backend/app/console.py`（新） | `force_utf8_output()`：把 stdout/stderr `reconfigure` 成 UTF-8（`errors="replace"` 兜底） | **真实产品缺陷**：CI 的 windows 腿曾因 `py -m app.cli --help` 打印中文在 cp1252 控制台下抛 `UnicodeEncodeError` 而红；开发者在中文 Windows 的 cmd 里同样会崩 |

### 批次 2：RAG 依据相关性（D4）

| 文件 | 改动 | 理由 |
|---|---|---|
| `app/rules/engine.py` | 新增 `RAG_ELIGIBLE_TYPES=("危大合规",)`、`RAG_MIN_SCORE=0.55`；挂条文改为"级别==致命 **且** 类型在允许集合内 **且** 过门槛"；命中/未命中/不适用三种状态写入 `条文检索`；**修正** `kb_search(..., kb=kb, ...)`（原漏传 `kb`，导致测试注入的假 KB 被忽略、仍读真实索引） | 修 D4：原本对任意致命项无条件取 top-1，`R-C-001`（混凝土强度等级不一致）被挂上"超规模危大须专家论证"（score 0.3745） |
| `app/knowledge/rag.py` | `DEFAULT_MIN_SCORE=0.55`；`KB.search` 与 `kb_search` 默认值同步；`kb_search` 暴露 `min_score` 参数 | 门槛是"检索有效性"的一部分，默认值必须与 engine 一致，否则换个调用点又回到 0.3 |
| `app/report/export.py` | 无条文时不再留空：写"不适用（原因）"或"未检索到匹配条文（原因）" | 让"没挂上"与"忘了导出"可区分 |
| `tools/build_rag_probes.py`（新） | 生成 5 个标准查询的**查询向量** + 实测 top1 → `code/knowledge/rag_probes.json`（需 API Key，一次性） | 让"检索指标"可在**离线**状态复算（CI 无 Key） |
| `code/knowledge/rag_probes.json`（新） | 夹具：model / kb_chunks=55 / min_score=0.55 / 5 条 {query, query_vector(1024), expected_top1, source, path} | 不含任何密钥；只含查询编码 |
| `tools/bench_rag.py`（新） | 离线门：夹具与索引一致 → top1 命中预期 → `min_top1 ≤ score ≤ max_top1`；三项失败即 exit 1 | 把"top1 全命中"从自述变成门 |
| `tests/test_rag_relevance.py`（新） | 5 条：参数冲突不挂条文（且**不查**知识库）、危大合规挂条文且带门槛、低于门槛标"未检索到"、`rag_on=False` 不挂、门槛不得回退到 <0.5 | 用假 KB 验**挂载策略**，无需 API |

### 批次 3：CI 与版本元数据（D2 + D5 + D8）

| 文件 | 改动 | 理由 |
|---|---|---|
| `pyproject.toml`（新） | `version = "0.1.0"`、`requires-python = ">=3.10"`（DEC1=B）、PEP 639 `license = "MIT"` + `license-files`、`dependencies` 从 `requirements.txt` 搬且**去掉 pytest**（进 `dev` extra）、`[project.scripts] construction-check`、`package-dir = {"" = "code/backend"}`、`[tool.pytest.ini_options] testpaths = ["code/backend/tests"]` | 修 D5：原本无任何打包/版本元数据，不可安装、无版本号 |
| `MANIFEST.in`（新） | 让 **sdist 自足**：含 `code/backend/{app,static,tests,tools}`、`code/{knowledge,rules}`、`data/`；排除 `webdata` / 演示输出 / `*.pyc` / `.env` | 实测发现只打 Python 包的 sdist 里跑不起来（`tests/conftest` 与数据都缺、`static/` 缺导致 Web 500） |
| `.github/workflows/ci.yml`（新） | `test` job：`{ubuntu-24.04, windows-latest} × {3.10,3.12}`，步骤 = editable 装 → pytest → `--help` → **CLI 退出码门** → 三个 bench → 端到端（单行，pwsh 不认 `\` 续行）+ 产物存在性断言（纯 ASCII 输出）；`package` job：`python -m build` → 从 wheel 装 → `construction-check --help` → 上传 `dist/`；工作流级 `PYTHONUTF8=1` | 修 D2：原本 0 workflow、徽章是手写静态值 |
| `README.md` 徽章行 | `tests-26/26` 静态 badge → **动态 CI badge**；`python-3.8%2B` → `python-3.10%2B` | 修 D2/D8：徽章必须与实际一致 |
| `.gitignore` | 新增 `build/ dist/ *.egg-info/ .eggs/`、`update/` | 构建产物与交接物不入公开仓 |

### 批次 4：自述与数据台账（D3 + D6 + D7）

| 文件 | 改动 | 理由 |
|---|---|---|
| `README.md` | 评测表 `876 字段` → **`873 字段`** 并加 `seed 1`；新增种子差异说明（seed 2 → 867）；检索区间 `0.55–0.80` → **实测 `0.6514–0.8021`** 并给复现命令；测试数 `26` → **`55`**（两处）；快速开始改 `pip install -e ".[dev]"`；新增退出码约定段；目录结构补 `tests/tools/static/.github/pyproject/MANIFEST`；"环境要求"改 3.10+ | 修 D3（不可复现数字）+ G4 + G6 |
| `data/README.md` | 三行加"可重新生成"标注；**新增「解析产物（可重新生成，非原始数据）」一节**（给复现命令 + LLM 版非确定性说明）；TODO 六条各加**计划状态**（`无计划` / `v0.2 候选`） | 修 D7（台账读起来像"仓里有"，实际是产物）×更正 1；4.4 让 TODO 不再像"马上会做" |
| `data/法规标准/危大工程范围清单.json` | 新增 `_复核`：`reviewed_on` / `next_review_due = 2027-09-26` / `复核方式`；**op/value 阈值一个未动** | 修 D6（规范引用无复核日期）；纪律 ⑧ |
| `code/knowledge/kb_weida.json` | 新增 `_meta`：`generated_at` / `model_version` / `embedding_dim` / `chunks` / `vectors` / `builder` / `source`；**chunks 与 vectors 逐项未变**（备份对撞验证） | 修 D6（知识库无生成时间） |
| `tests/test_self_reported_numbers.py`（新，11 条） | 守 D3（README 不得再出现 876、873 必须与 seed 同行、两个 bench 必须有退出码门、检索区间必须与夹具一致）、测试数自指门（README 两处数字 = 实际收集数）、D7（台账路径必须存在或声明未入仓）、D6（复核元数据与 kb 元数据存在、阈值未被动过、向量 1024 维） | 让"改文档"也受门禁约束（**新增判据不得让历史仓变红**：本条只断言现状事实） |

---

## 五、负控清单（逐条实测结果）

环境：`C:\Users\ASUS\AppData\Local\Temp\cd-final\`（**全新 venv**，Python 3.12.10，`pip install -e ".[dev]"`）。
退出码一律**不用管道**取值（纪律 ③）。

| 编号 | 判据 | 实测 | 判定 |
|---|---|---|---|
| **NC1** | `run/drawing/plan` 缺文件 → 非 0；正控 → 0 | `run`=**2**、`drawing`=**2**、`plan`=**2**；正控(`run` 有效对，规则通道)=**0** | ✅ |
| **NC2** | 无 `.env` + `--rag` → 非 0，且**产物目录为空这一事实被明确报出** | `rc=**2**`；stderr 打印缺 `LLM_BASE_URL`/`LLM_API_KEY` + 两条可执行指引；`ls cd-nc2out` → **目录不存在**（起点是"exit 0 且目录为空"） | ✅ |
| **NC3** | bench 门槛提到 1.01 → 非 0；改回 → 0 | `bench_drawings.py 30 1`=**0**（PASS 6/6）；`--min-f1 1.01`=**1**（FAIL 6/6，逐字段列名）；`bench_consistency.py 15 1`=**0**（PASS 7/7、15/15、误报 0）；`bench_rag.py --min-top1 0.9`=**1** | ✅ |
| **NC4** | 参数冲突类不得挂危大条文；条文 score ≥ 阈值 | `R-C-001`（参数冲突）→ `条文=None`、`条文检索.状态=不适用`；`R-W-000`（危大合规）→ score **0.8294 ≥ 0.55**；"参数冲突类挂条文数 = 0"；"score<0.55 的致命项数 = 0" | ✅ |
| **NC5** | CI 存在且推送后 run `conclusion=success` | **tag 提交**：run `39629831085`（headSha `8b92e64…`）5/5 success、注解 **0**；**当前 main 头**：run `39633361382`（headSha `337e790…`）5/5 success、注解 **0**（见 §6.1） | ✅ |
| **NC6** | `pip install -e .` 成功；`python -m app.cli --help` = 0 | 全新 venv `INSTALL_RC=0`；`--help`=**0**；`version`→`0.1.0`；console script `construction-check --help`=**0** | ✅ |
| **NC7** | 恒定回归：端到端仍产两份文件、结论与汇总不变 | `rc=0`；`结论: 存在致命问题，须整改后实施 | 汇总: {致命2, 一般0, 提示2}`；5 节点全 OK；`校核结果.json` + `校核报告.docx` 齐备 | ✅ |
| **NC8** | 敏感文件不入仓 | 4.3 MB 敏感 docx：`--error-unmatch` → **NOT tracked**；`git check-ignore` → `.gitignore:29` 命中；磁盘 4,338,255 B（磁盘有、仓库无，与声明一致）。`.env` 入仓数=0；`.env.example` 入仓=1；`你需要做的操作/赛题`=**0** | ✅（**判据见更正 2**：不要按子串 `高支模` 计数） |
| **附加** | 坏输入不得静默成功（更正 5） | 坏 `bad.dxf`：`drawing`=**1**、`run`=**1**；坏 `bad.docx`：`plan`=**1**、`run`=**1** | ✅ |

### 破坏性负控（验证"门是真的"）

| 动作 | 结果 |
|---|---|
| README 数字改回 `876` / 测试数改回 `41` | `test_self_reported_numbers.py` → **4 failed**（两个字段数断言 + 两个测试数断言），改回后 **11 passed** |
| `--min-f1 1.01` | bench_drawings → exit **1** 并逐字段说明哪个字段低于门槛 |
| `--min-top1 0.9` | bench_rag → exit **1** 并说明"会被 engine 拒挂，检索形同失效" |
| `pip wheel` 只装 Python 包（sdist 缺 static 时） | Web 服务 `GET /` → **500**；补 `MANIFEST.in` 后 sdist 自足：**55 passed**（与 editable 一致） |

---

## 六、CI 与发布（实测）

### 6.1 最终绿的 run

**三个 run 需要区分**：tag 冻结在 `8b92e64`；之后还有两个收尾提交（只改文档与 `runs-on`），其 run 同样全绿。

| 用途 | run id | headSha | conclusion | job | annotations |
|---|---|---|---|---|---|
| **tag 指向的提交**（被 v0.1.0 冻结） | `39629831085` | `8b92e64…` | success | 5/5 | **0** |
| 文档留档提交（本文件 §三/§六 后补） | `39632537707` | `a32f959…` | success | 5/5 | 1（`package` 仍用 `ubuntu-latest`） |
| **最终收尾提交**（package 也钉 24.04） | **`39633361382`** | **`337e790…`** | **success** | **5/5** | **0** |

> `v0.1.0` 仍指向 `8b92e64`；后两个提交只改 `plan/RELEASE-v0.1.0.md` 与
> `.github/workflows/ci.yml` 的 `runs-on`/注释，**不改任何产品代码、测试或数据**。
> 因此"tag 树自带的门全过"与"当前 main 头 CI 零注解"两个事实分别由上面第 1、3 行成立。

命令（可复现）：

```bash
# A. tag 指向的提交（v0.1.0 冻结在这里）
gh api "repos/yuluo554/construction-drawing-plan-checker/actions/runs/39629831085/jobs" \
  --jq '.jobs[]|"\(.name) \(.conclusion)"'
for j in $(gh api "repos/yuluo554/construction-drawing-plan-checker/actions/runs/39629831085/jobs" --jq '.jobs[].id'); do
  gh api "repos/yuluo554/construction-drawing-plan-checker/check-runs/$j/annotations" --jq 'length'
done   # → 0 0 0 0 0

# B. 当前 main 头（最终收尾提交）
gh run list --repo yuluo554/construction-drawing-plan-checker --limit 1 \
  --json databaseId,headSha,conclusion,status
```

### 6.2 CI 的失败史与收尾（诚实登记：连红四轮，第 6 轮起绿，第 8 轮注解归零）

| 轮 | run id | 红在哪 | 根因 | 修法 |
|---|---|---|---|---|
| 1 | `39624627712` | windows 两腿：`CLI --help` | cp1252 stdout 打印中文 → `UnicodeEncodeError`（**真实产品缺陷**） | 新增 `app/console.py`，入口统一切 UTF-8；3 条回归测试 |
| 2 | `39626684190` | windows 两腿：`End-to-end run` | 反斜杠续行在 pwsh 下失效（`错误：输入文件不存在 -> \`） | 端到端步骤改单行 |
| 3 | `39627319665` | windows 两腿：`Assert e2e artifacts exist` | **产物其实齐备**，是断言步骤自己 print 中文崩了 | 断言改纯 ASCII |
| 4 | `39628143755` | windows 两腿：同上 | 仍打印了中文**文件名** | 只打印"计数 + ASCII 转义名"；工作流加 `PYTHONUTF8=1` |
| 5 | `39628959162` | — | — | ✅ 5/5 success，但残留 **3 条** `ubuntu-latest` 迁移注解 |
| 6 | `39629831085` | — | — | ✅ ubuntu 腿钉 `ubuntu-24.04` → 5/5 + 注解 0（**tag 指向此提交 `8b92e64`**） |
| 7 | `39632537707` | — | — | ✅ 5/5 success；但 `package` job 仍 `runs-on: ubuntu-latest` → 残留 **1 条**注解 |
| 8 | `39633361382` | — | — | ✅ `package` 也钉 `ubuntu-24.04` → **5/5 + 注解 0（当前 main 头）** |

### 6.3 发布

见 §3.1 / §3.2（Release 附件 sha256 三方一致、可逐字节重建、发布物自证全过）。

### 6.4 分支与推送通道

- 直接推 `main`（本仓此前只有 1 个提交、无 PR 工作流；单仓单人维护，无需 PR 往返）。
- **HTTPS 通道在本机不可用**（`git push https://…` → `Recv failure: Connection was reset`），
  改用 `ssh://git@ssh.github.com:443/yuluo554/construction-drawing-plan-checker.git`：
  `git push <ssh-url> main` 与 `git push <ssh-url> v0.1.0` 均成功。
  `origin` 仍保持 HTTPS 不变（未改仓库配置）。

---

## 七、已知缺口与残留（诚实登记，不当作已完成）

1. **3.10 腿未在本机实测，但已由 CI 实测通过**：本机只有 3.8.8 / 3.12.10。
   `>=3.10` 的 3.10 兼容性由 CI 覆盖：`test (ubuntu-24.04 / py3.10)` 与 `test (windows-latest / py3.10)` **均 success**（run `39629831085`）。
   3.12 另在本机三处实测（干净 venv、sdist 解压、Release 下载物解压）。
2. **whl 不含数据资产（有意为之）**：`pip install`（非 editable）后 `import app` 可用、`--help` 可用，但 `data/`、`code/knowledge/`、`code/rules/` 不在 wheel 里——本仓按"**源码仓**"形态分发（DEC4=B 的 source zip 即为此），已在 `pyproject.toml` 与 README 说明。**sdist 是自足的**（可跑全部测试与基准）。
3. **LLM 抽取指标（202 条 / 5 条幻觉拦截）仍未复核**：需 API Key 且属模型非确定性输出，本轮**未验证**（README 已标注"本轮未复核"）。
4. **`code/requirements.txt` 保留**：README 快速开始给出两条安装路径（`pip install -e ".[dev]"` 与 `-r ../requirements.txt`）。`requirements.txt` 里 pytest 仍在运行清单中（未动它，避免破坏既有用法）。
5. **Web UI 无自动化测试**：`test_server.py` 2 条只测 API 端点，前端 `static/` 无端到端测试（本轮范围外）。
6. **修复发现了诊断未列的一条**：坏文件静默成功（更正 5）——只修了 CLI 边界，未动解析器。
7. **tag 之后仍有 2 个收尾提交**（`a32f959` 文档留档、`337e790` 把 `package` job 也钉 24.04）。
   它们**不改产品代码/测试/数据**，但意味着 `v0.1.0..HEAD` 有 2 个提交。
   若复验要求"tag 树 = 当前 HEAD"，需要**移动 tag**（并同步 `gh release edit` 的说明文字）——
   **本批没有移动 tag**：`v0.1.0` 仍指向被 CI 验证过的 `8b92e64`，这是更保守的选择。
   "tag 树自带的门全过"已由**从 Release 真下载解压后复跑**证明（§3.2），不依赖 HEAD。

---

## 八、纪律自查

| 纪律 | 自查结果 |
|---|---|
| ① 不改测试/跳测试/删断言变绿 | 现有 26 条**零修改、零跳过、零删除**；新增 29 条（13+5+11），合计 **55**。`git diff` 对 `tests/` 现有 5 个文件**无改动**（`test_agent.py` / `test_consistency.py` / `test_integration.py` / `test_pingfa.py` / `test_server.py` 全未动）；Release 下载物里 54 passed + 1 skipped 的 skip 来自原有 `test_integration.py:68`（需本机敏感 docx），非本批新增跳过 |
| ② 不靠放宽口径变绿 | 门槛是**新增**的（原无门）；`min_score` 从 0.3 **收紧**到 0.55；未把任何门槛调低；未用 `try/except: return 0` 包裹 main（`run` 的 `try` 只包住 `run_pipeline` 调用，异常→`return 1`） |
| ③ 报"通过"贴汇总行 + 退出码，不用管道 | 见 §五（NC3 特意重测一次：带管道时 `$?` 取到的是 `tail` 的码） |
| ④ 干净环境复验 | 四处独立环境：`cd-final`（全新 venv，editable）、`cd-sdist-venv`/`cd-sd2-venv`（sdist 解压后）、`dl-verify/venv`（**Release 真下载件**解压后）。全部 55/55 或 54+1skip 通过 |
| ⑤ 写回执行记录、标「待复验」 | 本文件 + `update/执行记录.md` |
| ⑥ 不改 `update/` 已有 4 文件 | 未改；更正写在**新增**的 `update/更正与实测差异.md` |
| ⑦ 临时环境在 `%TEMP%`、仓库内无 `.venv` | 全部在 `C:\Users\ASUS\AppData\Local\Temp\`；`git status --porcelain` 只剩本批改动（+ `update/` 已 gitignore） |
| ⑧ 不改 `危大工程范围清单.json` 阈值 | 未动 op/value；只新增 `_复核`（`git diff` = 7 行新增）；`bench_consistency` 仍 15/15 |
| ⑨ 不改 `data/施工方案/自制样例/*.docx` 与 `data/施工图纸/自制样例/*` | 未动（`git status` 无这些路径） |
| ⑩ 不删 `code/.env`、不伪造 Key | `code/.env` 原样保留；缺 Key 的负控用**副本**验证，未伪造 |