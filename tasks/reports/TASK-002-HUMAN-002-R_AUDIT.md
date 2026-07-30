# TASK-002-HUMAN-002-R AUDIT｜ASR人工结果分析独立审核与质量评分

- 审核结论：需要TASK-002-HUMAN-002-FIX
- 总分：84/100
- 阻断问题：有（1项）
- 审核对象：PR #4
- PR URL：`https://github.com/huangyongming0327-hash/live-stream-smart-clipping/pull/4`
- 被审核 latest head：`ca4b9913241250d9b217d02f42c37fbb3883320d`
- 分支：`task/TASK-002-HUMAN-002-result-analysis`
- 审核日期：2026-07-30（Asia/Shanghai）

## 1. 结论

从原始完成版JSON独立严格解析和重算后，真实manifest字节SHA、20/20完成性、三模型精确键集合、胜出/severity/错误标签统计、质量分、排名和高置信规则均与本地分析JSON、RESULT和公开报告一致：

- Paraformer：92.58；
- SenseVoice：49.00；
- Faster-Whisper：40.00；
- 排名：Paraformer、SenseVoice、Faster-Whisper；
- 主模型：Paraformer；
- 备用模型：SenseVoice；
- `decision_status=confirmed_mvp_baseline`；
- `decision_confidence=high`。

原始JSON前后SHA-256一致，真实manifest字节SHA精确匹配，tracked tree和PR diff未包含原始JSON、用户原文、逐窗口文本、`local-data/`、真实本机路径、媒体、模型或TASK-003代码。Paraformer约5.979 GiB峰值RSS的高资源成本与SenseVoice约490.44 MiB峰值RSS的低资源备用路线表达清楚。

但是，指令要求专项验证的输出阶段竞态触发了阻断：`run_analysis()`在最后一次输入SHA复核之前已经把三个本地结果和两个公开结果写入稳定目标。临时副本实测中，在输出阶段并发改变完成版JSON后，函数虽抛出`ReviewValidationError`，五个结果文件仍全部保留，并继续声明输入“前后保持一致”。这些包含可公开提交的正式文档，不是仅供失败任务使用的临时文件；既有发布器也不会重新读取原始JSON验证，因此可能继续被当作成功结果发布。

最终建议：**需要TASK-002-HUMAN-002-FIX，PR保持Draft并继续禁止TASK-003**。

## 2. 100分制评分

| 维度 | 得分 | 满分 | 说明 |
|---|---:|---:|---|
| 需求实现程度 | 24 | 25 | 静态输入下的强制门禁、统计、决策和脱敏交付完整；输出阶段输入变化保护未闭环 |
| 正确性与稳定性 | 13 | 20 | 独立重算完全一致，但竞态失败会留下错误标注为成功的稳定输出 |
| 测试与验证质量 | 12 | 15 | 30项专项、source-only和Actions均通过；未覆盖关键竞态，若干负面变体只由本审核补测 |
| 代码简洁与可维护性 | 11 | 15 | 精确算法清楚，但单个1055行模块同时承担校验、聚合、决策、渲染和多文件发布 |
| 性能与资源影响 | 10 | 10 | 分析仅处理20窗口小JSON；主/备用模型资源边界和重新评估条件清楚 |
| 安全与任务边界 | 10 | 10 | 原始JSON、用户文本、local-data、媒体、模型、真实路径和TASK-003均未进入Git |
| 文档与可追溯性 | 4 | 5 | RESULT、公开报告、哈希和公式充分；RESULT中的“PR尚待创建/Actions尚待完成”已落后于当前状态 |
| 总分 | **84** | **100** | **存在阻断，不能按“有条件通过”放行** |

## 3. 阻断问题

### B-1｜最终输入完整性检查发生在稳定输出发布之后

`experiments/asr/human_review/result_analysis.py`的`run_analysis()`先在约1031—1050行依次写入：

1. `asr-human-review-analysis.json`；
2. `asr-human-review-analysis.md`；
3. `asr-production-baseline.json`；
4. 公开人工结果报告；
5. 公开生产基线报告。

之后才在约1052—1054行重新计算完成版JSON SHA并拒绝变化。五次单文件写入各自是原子的，但整个结果集合不是事务性的，最终复核失败也不回滚或隔离已发布文件。

本审核仅使用D盘临时目录和原始输入副本模拟竞态：

```text
exception=ReviewValidationError: completed review JSON changed while outputs were written
output_count=5
outputs_exist=[true,true,true,true,true]
published_integrity_claim=true
recorded_after_sha_equals_before=true
actual_review_changed=true
public_result_claims_unchanged=true
```

因此失败后留下的本地分析JSON仍写有`source_integrity.unchanged=true`，公开报告仍写有“分析前后保持一致”。`analyze_results.py`不会输出`RESULT_ANALYSIS=status=passed`，这能提示当前进程失败，但不能阻止随后独立调用发布器提交已经存在的公开文档。

这是任务指令明确要求阻断的情况：结果可被误当作成功结果继续发布。修复应保证所有稳定目标只在最终复核确认输入未变化后才可见；同时应对完成版JSON和真实manifest执行最终复核，并增加竞态回归测试。具体实现方式留给FIX任务，本审核不修改实现。

## 4. 重要问题

### I-1｜测试未覆盖发布阶段竞态和部分严格JSON负面变体

现有30项专项覆盖manifest错误、20/20、额外模型键、窗口异常、非法severity/标签、tie、all_unusable、排名、三档置信度、脱敏、确定性和常规输入哈希保护，但没有在输出写入期间改变输入，也没有单独覆盖缺模型键、NaN和Infinity。

本审核对实际实现补做13项负面矩阵，以下全部被拒绝：

- ExtraModel；
- 缺模型键；
- 重复窗口；
- 未知窗口；
- `completed=false`；
- 19/20；
- 布尔severity；
- 重复标签；
- 未知标签；
- 错manifest；
- 重复JSON对象键；
- NaN；
- Infinity。

这些补测证明门禁实现正确，但B-1需要正式回归测试防止再次出现。

### I-2｜`result_analysis.py`职责过多，已影响发布边界的可测试性

文件约1055行，包含严格JSON解析、manifest验证、审核结构验证、Fraction聚合、排序、置信度、两个公开Markdown渲染、本地JSON构建和多文件编排。核心算法本身直接、确定且没有不必要的大型依赖，但职责集中使“先渲染/暂存、最终复核、再发布”的生命周期不够显式，也让竞态测试难以注入。

建议后续按验证、指标、决策、渲染和发布编排划分内部职责；文件长度本身不构成失败，本项扣分来自已经出现的输出生命周期缺陷和相应测试困难。

## 5. 一般问题与建议

### G-1｜RESULT的PR/Actions状态已过时

`tasks/reports/TASK-002-HUMAN-002_RESULT.md`仍写“Draft PR尚待创建及三项Actions完成”，而被审核head实际已有Open Draft PR，三项Actions run `30481812436`均成功。该段可解释为实现提交前的时间点快照，不影响统计或安全结论，但降低当前交接的可追溯性。按本次只读边界不修改RESULT。

### G-2｜全体窗口均难辨认时会安全失败，但缺少专门测试

`analyze_validated_rows()`对清晰子集调用`_calculate_subset()`；若20个窗口全部`audio_hard_to_hear=true`，空子集会抛出`ReviewValidationError`，不会除零或产生模型决策。该行为安全，但没有专项测试或公开错误说明。可进入backlog，不阻断当前静态20窗口结果。

## 6. 开始前状态与PR

- 公开工作副本：`<PUBLIC_WORKTREE>`；
- 当前分支：`task/TASK-002-HUMAN-002-result-analysis`；
- 本地HEAD：`ca4b9913241250d9b217d02f42c37fbb3883320d`；
- PR #4 head：`ca4b9913241250d9b217d02f42c37fbb3883320d`；
- 本地相对upstream：`+0/-0`；
- 开始时工作区和暂存区干净；
- origin fetch/push均为`huangyongming0327-hash/live-stream-smart-clipping`；
- PR状态：Open、Draft、未合并、auto-merge关闭、mergeable；
- base：`master`，head分支与任务指令一致；
- `local-data/`命中`.gitignore`；
- tracked tree及PR diff均未发现TASK-003实现。

PR共有9个变更文件：两个公开ASR报告、CURRENT_STATUS、DECISIONS、两个分析实现文件、一个专项测试文件、任务说明和RESULT。已完整读取全部diff及任务要求的相关文件。

## 7. 原始完成版JSON保护

本报告只使用占位符`<LOCAL_COMPLETED_REVIEW_JSON>`，不记录真实桌面路径。

| 时点 | 大小 | 修改时间UTC | SHA-256 |
|---|---:|---|---|
| 审核开始 | 11,041 bytes | `2026-07-29T18:18:47.990994+00:00` | `160964ef19b136947663270e6dd401ea801884518a9364c47327ce2158698aef` |
| 审核结束前复核 | 11,041 bytes | `2026-07-29T18:18:47.990994+00:00` | `160964ef19b136947663270e6dd401ea801884518a9364c47327ce2158698aef` |

结论：大小、修改时间和SHA-256前后一致，且SHA-256与指令预期值一致。所有并发和负面测试只使用内存对象或临时副本，没有写入原始JSON。

## 8. 独立manifest门禁

- 真实`review-manifest.json`大小：7,053 bytes；
- 直接读取文件字节并计算SHA-256：
  `25e7d0a7c116b00b895eea0d5b67aa0ad62ff562c9d8c640685909867a9abf7b`；
- 完成版JSON声明：
  `25e7d0a7c116b00b895eea0d5b67aa0ad62ff562c9d8c640685909867a9abf7b`；
- 独立比较：精确匹配；
- 与任务预期SHA-256：精确匹配。

错manifest在任何统计、排名或公开结果写入之前被拒绝；现有专项测试也确认错manifest时输出目录不存在。B-1是输入在已经通过首轮门禁后、输出阶段发生并发变化的另一条路径。

## 9. 严格结构验证

独立校验未导入`result_analysis.py`，确认：

- 顶层键集合精确；
- `schema_version=1.0`；
- `review_type=asr_human_listening_review`；
- `completed=true`；
- `completed_window_count=20`；
- `total_window_count=20`；
- `windows`长度20；
- 20个窗口ID唯一且全部`reviewed=true`；
- 窗口集合和start/end与真实manifest精确一致；
- `best_candidate`全部合法；
- `severity`和`error_tags`的模型键恰好为SenseVoice、Paraformer、Faster-Whisper；
- severity均为非布尔整数0—3；
- 错误标签均合法且同一模型内不重复；
- 严格JSON解析拒绝重复对象键、NaN和Infinity。

实现级补充负面矩阵与独立负面矩阵均拒绝全部13类变体，20/20和模型键门禁不可绕过。

## 10. 独立统计重算

独立脚本直接从原始完成版JSON重算，没有导入或调用`result_analysis.py`。

窗口级结果：

- Paraformer明确胜出18；
- SenseVoice明确胜出2；
- Faster-Whisper明确胜出0；
- `audio_hard_to_hear=0`；
- 清晰音频子集20；
- `tie=0`；
- `tie_inconsistent=0`；
- `all_unusable=0`；
- 实际听写填写数0；
- 备注填写数0。

severity：

| 模型 | severity 0/1/2/3 | 平均 | 中位数 | 可用率 | 明显问题率 | 严重失败率 |
|---|---|---:|---:|---:|---:|---:|
| Paraformer | 15/5/0/0 | 0.25 | 0.00 | 100.00% | 0.00% | 0.00% |
| SenseVoice | 5/12/3/0 | 0.90 | 1.00 | 85.00% | 15.00% | 0.00% |
| Faster-Whisper | 4/9/6/1 | 1.20 | 1.00 | 65.00% | 35.00% | 5.00% |

错误标签数量逐字段与本地分析JSON、公开报告和RESULT一致：

| 错误类型 | SenseVoice | Paraformer | Faster-Whisper |
|---|---:|---:|---:|
| 漏字/漏词 | 3 | 3 | 4 |
| 多字/幻觉 | 8 | 0 | 2 |
| 错字/替换 | 3 | 1 | 7 |
| 人名/品牌/专名 | 0 | 0 | 4 |
| 英文 | 2 | 0 | 1 |
| 数字 | 0 | 0 | 0 |
| 标点/可读性 | 1 | 1 | 15 |
| 非中文异常字符 | 2 | 0 | 0 |
| 切点/分段 | 0 | 0 | 2 |
| 其他 | 0 | 0 | 0 |

没有难辨认窗口，因此清晰音频子集的上述全部字段与全量结果一致。

## 11. 质量分独立重算

使用`Fraction`保存精确值，并用`Decimal`的`ROUND_HALF_UP`公开显示两位：

```text
winner_score = 胜出积分 / 窗口数 × 100
severity_quality_score = mean((3 - severity) / 3) × 100
reliability_score = (1 - severity_3_count / 窗口数) × 100
aggregate_quality_score = 0.45 × winner_score + 0.35 × severity_quality_score + 0.20 × reliability_score
```

| 模型 | winner | severity quality | reliability | aggregate |
|---|---:|---:|---:|---:|
| Paraformer | 90.00 | 91.67 | 100.00 | **92.58** |
| SenseVoice | 10.00 | 70.00 | 100.00 | **49.00** |
| Faster-Whisper | 0.00 | 60.00 | 95.00 | **40.00** |

本地分析JSON中的精确分数、未舍入值、公开两位显示、公开报告和RESULT逐字段一致。公开材料明确说明这些是确定性人工质量分，不是CER、WER或通用准确率。

## 12. 排名、置信度与主/备用模型

排序依次使用：

1. aggregate降序；
2. mean severity升序；
3. severity 3数量升序；
4. winner points降序。

全量与清晰音频子集排名均为：

1. Paraformer；
2. SenseVoice；
3. Faster-Whisper。

Paraformer领先SenseVoice 43.58分。高置信条件全部成立：

- 领先不少于8分；
- 平均severity不更差；
- severity 3数量不更多；
- 胜出积分不更低；
- 清晰音频子集第一名不冲突。

独立合成规则检查确认：

- 领先8且方向一致、子集不冲突：high；
- 领先3且方向一致、子集不冲突：medium；
- 领先不足3：low；
- 即使领先20但清晰子集冲突：low。

因此`primary_model=paraformer`、`fallback_model=sensevoice`、`decision_status=confirmed_mvp_baseline`和`decision_confidence=high`合理。

## 13. 资源影响与生产边界

人工质量主证据支持Paraformer：20窗口明确胜出18次，聚合分92.58，平均severity 0.25，没有severity 2或3。

既有技术报告的次级工程证据为：

- Paraformer热RTF 0.04827、峰值RSS约5.979 GiB、环境加模型约3.23 GiB；
- SenseVoice热RTF 0.02449、峰值RSS约490.44 MiB、环境加模型约344.50 MiB；
- Faster-Whisper热RTF 0.22376、峰值RSS约655.27 MiB，并提供完整词级时间戳。

公开生产基线明确标记Paraformer资源成本高、SenseVoice资源成本最低，并把SenseVoice保留为备用模型。结合普通笔记本、电池供电和约6 GiB峰值RSS，SenseVoice作为低资源路线合理且必要。本审核不实现自动回退、不写TASK-003配置，也不重新运行任何ASR模型。

## 14. 并发输入变化边界

静态单用户流程下，分析开始、统计后和审核结束前的原始JSON哈希一致。实现也在统计后执行一次SHA复核。

问题发生在稳定输出发布期间：

```text
统计后SHA复核通过
→ 五个稳定结果依次写入
→ 输入副本发生变化
→ 最终SHA复核失败
→ 五个结果仍保留且声明unchanged=true
```

由于两个目标位于`docs/`并可由后续发布器提交，本情况不能降级为“失败任务只留下临时输出”。详见B-1。

## 15. 代码简洁性与可维护性

优点：

- 严格JSON解析拒绝重复键和非有限常量；
- manifest使用真实文件字节SHA；
- 审核和模型键采用精确集合；
- Fraction/Decimal保证公式、排序和显示确定；
- tie、tie_inconsistent、all_unusable和可判定分母逻辑清楚；
- 空清晰子集安全失败而不除零；
- 单文件写入使用临时文件和原子替换；
- 标准化行只保留用户文本是否填写的布尔值，不复制内容；
- 排名和置信度规则可单测。

不足：

- `result_analysis.py`集中五类职责；
- 两套子集和两个Markdown渲染有较多重复编排；
- 多文件输出没有明确的暂存/验证/发布阶段；
- B-1表明职责集中已经影响稳定发布正确性。

结论：不是因为文件长而失败；扣分来自实际暴露的生命周期缺陷和测试维护成本。

## 16. 隐私、Git与任务边界

检查PR全部9个文件、tracked tree、文件名和敏感模式，结果：

- `local-data/`被`.gitignore`忽略；
- tracked tree不含原始完成版JSON；
- tracked tree不含`review-data.json`或真实manifest；
- tracked tree不含WAV或其他媒体；
- PR不含用户实际听写、备注或逐窗口候选文本；
- PR不含真实桌面路径、用户名、邮箱、IP、token、API key或私钥；
- PR不含模型、ASR环境、虚拟环境、runtime、cache或大型二进制；
- PR不含TASK-003代码；
- tracked safety scan：145 files、145 text files、0 issue；
- `git diff --check`通过；
- 未创建新PR、未推master、未force push、未Ready、未merge、未启用auto-merge；
- 未运行ASR、未调用云端或收费API、未下载模型、未安装依赖。

公开JSON哈希只用于完整性追溯，没有发现通过哈希旁路公开用户原文。

## 17. 本地测试

首次直接运行`Invoke-SourceOnlyTests.ps1`时，当前系统Python没有pytest，基础阶段在测试收集前以`No module named pytest`退出。任务禁止安装依赖，因此未安装或修改环境；改为在当前进程PATH前置项目既有D盘虚拟环境后重跑。

有效source-only结果：

```text
base-schema-media: 110 passed, 1 deselected, 0 failed, exit 0
asr-experiments: 86 passed, 2 deselected, 1 warning, 0 failed, exit 0
pip check: No broken requirements found, exit 0
SOURCE_ONLY_RESULT.status=passed
```

warning为既有`audioop`弃用提示。

结果分析专项单独运行：

```text
30 passed in 0.87s
```

实现级13项补充负面矩阵全部按预期拒绝。竞态模拟按预期触发非零异常，但同时复现B-1的五个误导性残留输出。

## 18. GitHub Actions

被审核head `ca4b9913241250d9b217d02f42c37fbb3883320d`对应最新PR Actions run `30481812436`，不是旧head结果：

- `repository-safety`：COMPLETED / SUCCESS；
- `lightweight-tests`：COMPLETED / SUCCESS；
- `task-report-gate`：COMPLETED / SUCCESS。

三项required jobs均真实执行，没有skipped。已完整读取`lightweight-tests`日志，确认：

```text
base-schema-media: 110 passed, 1 deselected, 0 failed, exit 0
asr-experiments: 86 passed, 2 deselected, 1 warning, 0 failed, exit 0
pip check: No broken requirements found, exit 0
SOURCE_ONLY_RESULT.status=passed
```

完整日志未发现真实pytest FAILED/ERROR；三个阶段exit code均为0。`repository-safety`日志显示145个tracked文本文件、0 issue；`task-report-gate`真实找到1个任务报告。审核报告上传后的新head仍须重新等待和读取三项Actions，本段不以旧run替代上传后复核。

## 19. 最终建议

审核结论：需要TASK-002-HUMAN-002-FIX。

总分：84/100。

阻断问题：有，B-1。

PR #4应保持Draft，不应标记Ready，不具备手动合并资格。FIX任务应只修复多文件发布前的最终输入完整性门禁并增加竞态回归；修复后重新执行独立审核。当前继续禁止TASK-003。
