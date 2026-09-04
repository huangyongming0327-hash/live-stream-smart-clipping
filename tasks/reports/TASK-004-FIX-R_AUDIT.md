# TASK-004-FIX-R AUDIT｜爆点候选容错独立审核

## 1. 审核对象与边界

- 仓库：`huangyongming0327-hash/live-stream-smart-clipping`
- PR：`#10`
- 分支：`task/TASK-004-FIX-candidate-tolerance`
- PR base：`3f92d235b151cd67a6164e250da0883ac4e81a14`
- 实现审核基线 HEAD：`5c8d200a78ab5e02e0895ce65a53e2f4032c0cc6`
- 审核日期：2026-09-05（Asia/Shanghai）
- 审核方式：逐行复核生产代码与测试、对比完整 PR diff、运行 TASK-004 专项与完整 source-only、使用独立内存探针覆盖修复边界和生产 HTTP 请求计数、核读 latest-head Actions 状态与关键日志。
- 审核过程未调用 ASR，未读取或公开真实字幕、候选文本、API Key、本地媒体或本地分析文件。

指定的 `TASK-004-FIX-R_爆点候选容错独立审核_Codex指令.md` 没有出现在当前工作区、常见上传目录、PR 树或远端分支中，因此不宣称已读到该附件。本审核对用户当前指令中明确列出的 15 项要求逐项执行，并完整读取了仓库内 `tasks/TASK-004-FIX.md`、`tasks/TASK-004.md` 及相关 RESULT 作为对照。

## 2. 审核结论

- 总分：**82/100**
- 审核结论：**不通过，需要 TASK-004-FIX2**
- 阻断问题：**1 个**
- 用户实际遇到的两个 candidate 错误：**已独立复现并确认关闭**
- PR 状态：必须继续保持 Draft；不得 Ready、merge 或 auto-merge
- TASK-008：继续禁止执行

修复正确实现了“首次严格、唯一一次 repair、repair 后仅丢弃单个坏 candidate”的主体逻辑，且 JSON、topics 和 candidates 容器等硬错误仍然失败。但“任何场景每窗口最多 2 次模型/API 请求，绝不出现第 3 次”在生产 HTTP 客户端上不成立，属于明确验收条件的阻断性偏差。

## 3. 评分

| 维度 | 得分 | 满分 | 审核说明 |
|---|---:|---:|---|
| candidate 容错主体 | 30 | 30 | 首次严格，repair 后单项丢弃，全坏时空数组成功 |
| 结构与最终 schema 严格性 | 20 | 20 | JSON、顶层、topics、容器、3 个上限仍为硬错误，最终仍调用 `validate_analysis` |
| 每窗口请求上限 | 0 | 15 | 生产客户端内部传输重试可使一个窗口出现第 3 甚至第 4 个 HTTP POST |
| state、恢复与三版本 | 15 | 15 | 路径未被破坏，过滤后保存/恢复及 current+2 history 测试通过 |
| 测试与回归证据 | 12 | 15 | 42 项专项与完整 source-only 全绿；现有“无第 3 次”测试未组合真实客户端重试 |
| 范围和安全边界 | 5 | 5 | 无 ASR/字幕/review/export/启动器/TASK-008 实现变更 |
| **总分** | **82** | **100** | **不通过：存在 1 个明确阻断** |

## 4. 阻断问题

### B-1｜[P1] 生产 HTTP 重试可越过每窗口 2 次模型请求上限

`run_analysis` 在每窗口最多调用两次 `client.analyze_window`：第一次在首次分析，第二次在严格校验失败后 repair。这一层没有第三次调用。

但 `OpenAICompatibleClient._send_with_retry` 对每次 `analyze_window` 都允许两个物理 HTTP 尝试，并且 `request_count` 每次 `urlopen` 前加 1。两层组合后，单窗口最多可发出 4 个真实模型 POST，与任务明确规定的“最多 2 次 API 请求：首次请求加唯一一次 repair”冲突。

独立生产客户端探针复现：

1. 第 1 个 POST 成功返回坏 JSON；
2. repair 的第 2 个 POST 超时；
3. `_send_with_retry` 自动发出第 3 个 POST 并成功；
4. 窗口最终成功，`AnalysisResult.request_count == 3`。

另一个探针以“首次超时→重试返回坏 JSON→repair 超时→重试成功”复现了 `request_count == 4`。因此“任何场景”和“绝不出现第 3 次”两条均未满足。

现有新测试使用 `FakeClient`，其每次 `analyze_window` 只增加一次计数，无法暴露生产客户端内部重试。仓库既有 `test_http_client_retries_timeout_once_and_sends_only_subtitle_fields` 反而证明单次 `analyze_window` 可计为两次 HTTP 请求。

修复要求：在不增加第 3 次模型请求的前提下明确并实现单窗口的全局 HTTP 尝试预算，并用真实 `OpenAICompatibleClient` + 受控 `urlopen` 的组合测试证明所有分支都不会出现第 3 个 POST。本审核不代为修改实现或测试。

## 5. 15 项硬性要求逐项结果

| # | 要求 | 结果 | 独立证据 |
|---:|---|---|---|
| 1 | 首次模型响应仍严格校验 | 通过 | 首次只调用 `parse_model_response`；混合合法+过短 candidate 的首次响应触发 repair，未直接容错 |
| 2 | 首次失败后只能 repair 一次 | 通过（业务层） | 控制流只有两次 `analyze_window`；repair 结果失败后直接抛错 |
| 3 | repair 后时长、跨 topic、quote、score/risk、字段错误只丢弃该项 | 通过 | 独立探针覆盖短/长时长、跨 topic、quote、6 个正向 score + risk、缺/多字段、空标题、未知 segment、非对象，共16类均只丢弃坏项 |
| 4 | repair 后 candidate 全坏时窗口仍成功且 `candidates=[]` | 通过 | 专项测试与独立两个用户错误探针均确认 |
| 5 | repair 后 JSON、topics、重叠、未知 segment、candidates 容器和 >3 仍失败 | 通过 | 独立 8 类硬错误探针均在第 2 次后失败，不生成 current |
| 6 | 任何场景每窗口最多 2 次模型请求 | **失败** | 生产 HTTP 探针复现 3 和 4 个 POST，见 B-1 |
| 7 | 绝不出现第 3 次模型请求 | **失败** | 生产 HTTP 探针明确观察到第 3 个 POST |
| 8 | 不自动延长、缩短、移动或改写坏 candidate | 通过 | repair parser 仅校验并 `continue`，无任何边界或文本改写；坏项完整消失 |
| 9 | 最终保留项仍通过原严格 schema | 通过 | 单项复用 `validate_model_payload`，state 恢复再验证，构建和 staging 发布前后调用 `validate_analysis` |
| 10 | state 保存/恢复/最近 3 版本不破坏 | 通过 | 过滤后窗口 state 保存与下窗口恢复测试通过；既有恢复和 current+2 history 测试通过；发布代码未改 |
| 11 | 单独复现并关闭两个用户实际错误 | 通过 | 时长错误和跨 topic 错误分别独立运行；首次严格拒绝，repair 后丢弃坏项、空 candidates 成功发布 |
| 12 | 不重跑 ASR | 通过 | 未调用 transcribe、未载入 ASR 模型；source-only 只运行源码级测试 |
| 13 | 不修改字幕烧录、review/export、Windows 启动器 | 通过 | PR 生产变更仅限 `analysis/pipeline.py` 和 `analysis/schema.py` |
| 14 | 不执行 TASK-008 | 通过 | 无 TASK-008 文件、命令、实现或测试执行 |
| 15 | 完整 source-only 和 latest-head Actions 0 failed | 通过（实现基线） | 本地 source-only 三阶段退出码均为 0；实现 HEAD 的 Actions Run `33893565127` 三项均 SUCCESS。审核提交后的 latest-head 仍须等待并在最终 PR_HANDOFF 中确认 |

## 6. 用户实际两个错误的独立复现

### 6.1 `candidate 时长必须为 15—180 秒`

- 首次响应只含一个 10 秒 candidate；
- 严格 parser 拒绝并把 `15—180` 错误传入唯一 repair；
- repair 再返回该坏 candidate；
- repaired parser 丢弃该项，窗口成功，最终 `candidates=[]`；
- 总业务调用数为 2，输出通过 `validate_analysis`。

结论：用户遇到的该 candidate 错误已关闭；不再使整个窗口失败，也没有被自动延长。

### 6.2 `candidate 必须完整属于一个 topic`

- topics 分别覆盖 segment `1—10` 和 `11—20`；
- 首次 candidate 从 `10` 跨到 `11`，严格 parser 拒绝并触发唯一 repair；
- repair 再返回该跨 topic candidate；
- repaired parser 丢弃该项，窗口成功，最终 `candidates=[]`；
- 输出通过 `validate_analysis`。

结论：用户遇到的该 candidate 错误已关闭；没有移动边界、改 topic 或强行关联。

## 7. 实现正确性复核

### 7.1 首次严格与唯一 repair

`pipeline.run_analysis` 的首次响应仍调用原有 `parse_model_response`，该函数解析 JSON 后对整包执行 `validate_model_payload`。只有捕获到首次 `ModelResponseError` 才会调用一次 repair。repair parser 再失败会立即转成 `AnalysisError`，业务层不存在第三次 repair 或新的循环。

### 7.2 repair 后的严格边界

`parse_repaired_model_response` 先严格要求：

- 顶层必须且只能是 `topics` 和 `candidates`；
- 两个容器必须是数组；
- candidates 不得超过 3 个；
- 全部 topics 使用原 `validate_model_payload` 整体校验。

只有这些硬条件成立后，才把每个 candidate 与已验证 topics 组合，再次调用同一个 `validate_model_payload`。单项失败仅 `continue`，不改写原始边界、topic、quote、分数或文本。

### 7.3 state、恢复、严格发布与三版本

- 每个窗口的过滤后结果追加到 state，再通过原子 JSON 写入保存；
- 恢复时仍对已完成窗口调用原严格 `validate_model_payload`；
- 总结果构建后、staging 写入后均调用 `validate_analysis`；
- 发布和回滚代码在本 PR 中未改；
- 连续 5 次发布后仍为 1 个 current + 2 个 history。

## 8. 测试与 Actions 证据

### 8.1 本地专项

```text
python -m pytest -q tests/test_semantic_analysis.py
42 passed, 0 failed
```

新增测试证明 candidate 容错、硬错误、两次业务调用和过滤后 state 恢复。但对“不存在第 3 次”的证据仅使用无内部重试的 `FakeClient`，因此证据不充分，并已被生产客户端组合探针反证。

### 8.2 独立内存探针

- 16 类 repair candidate 错误：均只丢弃坏项，保留合法项；
- 8 类 repair 硬错误：均失败，不发布 current；
- 2 个用户实际错误：均独立复现并关闭；
- 保留的 candidate 和最终结果：通过严格 `validate_analysis`；
- 生产 HTTP 计数：分别复现 3 个和 4 个 POST，因此请求上限失败。

探针仅使用合成 timeline、受控响应和内存 monkeypatch，不调用真实 API，不调用 ASR，不落盘保留临时产物。

### 8.3 本地完整 source-only

```text
base-schema-media: 245 passed, 1 deselected, 0 failed
asr-experiments:   91 passed, 2 deselected, 1 existing warning, 0 failed
pip check:         No broken requirements found.
SOURCE_ONLY_RESULT.status=passed
三个 stage exit_code 均为 0
```

`asr-experiments` 中的唯一 warning 为 Python 3.13 计划移除 `audioop` 的既有 deprecation warning，不是测试失败，也没有执行真实 ASR 推理。

### 8.4 实现 HEAD Actions

- Run：`33893565127`
- Head SHA：`5c8d200a78ab5e02e0895ce65a53e2f4032c0cc6`
- `repository-safety`：SUCCESS
- `lightweight-tests`：SUCCESS（245 passed / 1 deselected；91 passed / 2 deselected / 1 warning；`pip check` 通过）
- `task-report-gate`：SUCCESS
- failed jobs：0

审核报告提交会生成新的 latest-head Actions。只有待该三项全部 SUCCESS 后才可运行 `Get-PRHandoff.ps1`；Actions 全绿不会解除 B-1 的审核阻断。

## 9. 变更范围与禁止项

PR 相对 base 只包含：

- `src/liveclip/analysis/pipeline.py`
- `src/liveclip/analysis/schema.py`
- `tests/test_semantic_analysis.py`
- `tasks/TASK-004-FIX.md`
- `tasks/reports/TASK-004-FIX_RESULT.md`
- `docs/CURRENT_STATUS.md`

未发现 ASR、字幕烧录、review/export、Windows 启动器或 TASK-008 实现变更。审核本身除本文件外未改动实现、测试、RESULT、`CURRENT_STATUS.md` 或其他既有文档。

## 10. 最终决定与后续边界

1. repair 后坏 candidate 的逐项容错：**通过**
2. repair 后整体硬错误继续失败：**通过**
3. 全坏 candidate 时空数组成功：**通过**
4. 最终 schema、state、恢复和最近 3 版本：**通过**
5. 用户实际遇到的两个错误：**已关闭**
6. 任何场景每窗口最多 2 次模型/API 请求：**失败**
7. 是否允许 Ready 或合并：**否**
8. 审核结论：**82/100，不通过，需要 TASK-004-FIX2**

必须先在同一 Draft PR 中修复 B-1，补充生产客户端组合测试，然后重新执行独立审核。在此之前：

- 保持 Draft；
- 不得 Ready；
- 不得 merge 或 auto-merge；
- 不得执行 TASK-008。
