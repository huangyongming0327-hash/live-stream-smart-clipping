# TASK-002-FIX-R｜Paraformer 时间戳修复独立只读复核与质量评分

- 复核日期：2026-07-23（Asia/Shanghai）
- 项目：`<PROJECT_ROOT>`
- 复核范围：仅 TASK-002-FIX 的实现、测试、既有结果、短离线探针、环境、锁文件、安全边界和文档一致性
- 唯一正式写入：本报告；测试仅在 `runtime/` 留下允许的临时产物和日志
- 未运行三套完整全长模型实验；未执行 TASK-003；未下载、安装、上传、调用云端 ASR/收费 API 或创建 Git 提交

## 1. 审核结论

**结论：不通过。**

**总分：79/100；等级：需要小范围修复。**

原 TASK-002-R 阻断的“文本无时间戳时伪造 `0—827.690688` 整段范围”已经修复。缺失、`None`、空列表、格式错误、非有限值、逆序和越界等单项异常均会被排除；全部无时间轴时会保留 raw/unified/metrics/TXT、标记 `timeline_status=unavailable`、以失败退出且不生成正常 SRT；部分缺失也能只保留有证据的段。既有 cold/warm 399 段、SRT、TXT、人工审核包、媒体、模型和环境均无回归。

但本次独立探针发现当前实现没有校验 `sentence_info` 条目之间的单调顺序。输入先给 `1000—2000 ms`、后给 `100—500 ms` 时，两个条目都进入 `segments`，没有 warning/error 或 `timeline_status`；随后 `common.py` 将它们按时间排序，统一校验通过并生成正常 SRT。该行为违反指令中“非单调和 sentence_info 时间异常不得进入可用时间轴”的明确要求，也说明现有 31 项测试并未覆盖其报告所声称的全部非单调场景。

因此最终建议只能是：**需要 TASK-002-FIX2**。

## 2. 七维评分

| 维度 | 满分 | 得分 | 扣分原因与证据 |
|---|---:|---:|---|
| 需求实现程度 | 25 | 20 | 原整段伪时间戳、全无时间、部分时间、失败/SRT 语义和 399 段回归均实现；扣 5 分：`sentence_info` 非单调顺序仍被接受并进入正常 SRT。 |
| 正确性与稳定性 | 20 | 14 | 常见缺失/无效值处理正确，真实 399 段稳定；扣 6 分：非单调条目可被静默重排为“有效”，结束时间回退场景则到通用校验才整体抛错，未形成 Paraformer 结构化排除记录。 |
| 测试与验证质量 | 15 | 11 | 31/31 实验测试、148/148 基础测试、18/18 媒体测试均通过；扣 4 分：测试仅覆盖同一顶层 `timestamp` 数组内的非单调，没有覆盖 `sentence_info` 条目间/多个 raw 条目间的非单调，也没有直接单测 Paraformer 正常空结果的 `timeline_status` 语义。 |
| 代码简洁与可维护性 | 15 | 11 | 修复集中在 `paraformer.py` 与必要的产物写入边界，错误码总体统一；扣 4 分：顶层 timestamp 有局部单调校验，sentence_info 却复用单段校验后依赖公共排序，职责分裂使异常被掩盖；通用校验失败路径也无法复用结构化 issue。 |
| 性能与资源影响 | 10 | 10 | 修复为线性轻量校验；399 段字节级回归通过；30 秒探针 3.229 秒、18 段，未发现时间戳修复引入可见资源或输出回归。未把本次加载时间用于横向性能结论。 |
| 安全与任务边界 | 10 | 10 | 未下载/安装/上传/联网回退，未运行全长三模型，模型、环境、原媒体和正式结果不变；无 CUDA/NVIDIA 包；无 TASK-003、commit、remote 或 push。 |
| 文档与可追溯性 | 5 | 3 | 原阻断、供电差异、399 段和人工审核待办说明一致；扣 2 分：`CURRENT_STATUS.md`、`TASK-002-FIX.md`、`TASK-002-FIX_RESULT.md` 把“非单调已覆盖/均被拒绝”写成完成事实，与独立探针不一致。 |
| **总分** | **100** | **79** | **不通过；需要小范围修复。** |

## 3. 阻断问题

### B-01｜`sentence_info` 非单调顺序被静默排序并生成正常 SRT

证据位置：

- `experiments/asr/adapters/paraformer.py:167` 的 `_segments_from_result()`；
- `experiments/asr/adapters/paraformer.py:176-210` 对每条 sentence 只做单段有限性、正序和边界检查，没有保存/比较前一条时间；
- `experiments/asr/common.py:118` 的 `build_unified_result()` 在校验前按 `(start, end)` 排序。

独立只读探针：

```python
[{"text": "测试文本", "sentence_info": [
    {"text": "后句", "start": 1000, "end": 2000},
    {"text": "前句", "start": 100, "end": 500},
]}]
```

实际结果：

- `_segments_from_result()` 返回 2 个 segment，原顺序为 `1.0—2.0`、`0.1—0.5`；
- `timeline_status=None`，`warnings=[]`，`errors=[]`；
- `build_unified_result()` 将其静默改排为 `0.1—0.5`、`1.0—2.0`；
- `validate_unified_result()` 通过；
- `render_srt()` 返回非空正常 SRT。

同样地，两个 raw item 以 `1.0—2.0`、`0.1—0.5` 的非单调顺序输入也会被静默排序并接受。即使真实 FunASR 常见产物只有一个 raw item，单个 `sentence_info` 内的复现已经直接命中任务要求。

该问题不是原来的“伪造整段范围”，但它仍把任务明确规定为异常的时间轴当成正常时间轴发布，因此阻断本次通过。

## 4. 重要问题

### I-01｜结束时间回退只在通用校验处失败，缺少结构化追溯

独立输入 `0—2000 ms`、`1000—1500 ms` 的两个 sentence：

- Paraformer 提取层返回 2 个 segment、无 warning/error/status；
- 公共统一校验因第二段 `end` 回退而抛出 `ValueError: segments[1] timestamps are not monotonic`；
- `write_run_artifacts()` 在写 raw/unified 前先校验，因此新目录中不会得到任务要求的 raw 与结构化错误产物。

该路径没有生成 SRT，安全结果好于 B-01，但错误处理仍不符合“异常条目排除、原因和索引可追溯”的修复契约。

### I-02｜测试与完成报告对“非单调覆盖”的表述过宽

`test_paraformer.py` 的非单调用例只覆盖单个顶层 `timestamp` 数组内 `[[100, 200], [50, 300]]`；sentence_info 参数化测试覆盖缺失、None、类型、非有限、逆序和越界，没有覆盖条目之间的单调关系。`test_common.py` 只验证通用校验可拒绝结束时间回退，无法证明 Paraformer 会结构化排除并保留 raw。

因此 31 项全部通过是真实结果，但不能证明指令列出的全部异常均已满足。

## 5. 一般建议

1. FIX2 应在 Paraformer 提取层对 `sentence_info` 和跨 raw 的模型输出顺序做明确单调校验，不应依赖 `build_unified_result()` 的排序把异常变成正常。
2. 对非单调条目采用现有 `PARAFORMER_TIMESTAMP_INVALID`、`timestamp_non_monotonic`、raw/sentence 索引结构，保持错误码体系稳定。
3. 增加行为测试：sentence_info 倒序、end 回退、跨 raw 倒序、有效与非单调混合、全非单调不生成 SRT、正常空结果不误报。
4. 修复前不要把文档中的“所有非单调均已覆盖/拒绝”继续作为验收事实。

## 6. 原阻断问题复核

对当前实现实际调用：

```python
_segments_from_result([{"text": "测试文本"}], 827.690688)
```

结果：

- segment 数为 0；
- 不存在 `start=0.0, end=827.690688`；
- 没有按字符数、平均分配或相邻段推算时间；
- `timeline_status=unavailable`；
- warning 为 `PARAFORMER_UNTIMED_TEXT_EXCLUDED`；
- error 为 `PARAFORMER_TIMESTAMP_MISSING`；
- `untimed_text_count=1`、`raw_indices=[0]`、`raw_text_preserved=true`，entry 可追溯；
- 写产物时 raw/unified/metrics/TXT 先保存，`metrics.success=false`，不生成 `transcript.srt`，随后抛出 `TimelineUnavailableError` 使候选进程失败。

**原 TASK-002-R 的整段伪时间戳阻断已经修复。**

## 7. 无时间戳与异常行为

| 场景 | segments | status | 结构化结果 | SRT |
|---|---:|---|---|---|
| timestamp 缺失 | 0 | unavailable | MISSING + untimed warning | 不生成 |
| timestamp=None | 0 | unavailable | MISSING + untimed warning | 不生成 |
| timestamp=[] | 0 | unavailable | MISSING，reason=`timestamp_empty` | 不生成 |
| timestamp 类型错误 | 0 | unavailable | INVALID / invalid_format | 不生成 |
| 非有限值 | 0 | unavailable | INVALID / non_finite | 不生成 |
| `end <= start` | 0 | unavailable | INVALID / reversed | 不生成 |
| 顶层 timestamp 数组非单调 | 0 | unavailable | INVALID / non_monotonic | 不生成 |
| 越出音频范围 | 0 | unavailable | INVALID / out_of_bounds | 不生成 |
| sentence_info 单项缺失/None/类型/非有限/逆序/越界 | 0 | unavailable | MISSING 或 INVALID，含 sentence_index | 不生成 |
| sentence_info 条目顺序非单调 | 2 | 无 | **无 warning/error，静默排序** | **生成** |
| sentence_info end 回退 | 提取层为 2 | 无 | **通用校验整体抛错，无结构化 issue** | 不生成 |

说明：适配器真实路径会先经过 `_jsonable()`；非有限 float 会被转为 `null`，因此真实路径可能把该原因归类为 missing 而非 non_finite。文本仍保留，但测试直接调用提取函数时的原因分类与真实序列化路径并不完全相同。本项为一般精度问题，不单独阻断。

## 8. 部分时间轴行为

独立输入包含一个有效 `0.1—0.9` 段、一个缺失时间文本和一个逆序时间文本时：

- 只有有效段进入 segments 和 SRT；
- 原始时间没有重新分配；
- `timeline_status=partial`；
- warning 的 `untimed_text_count=2`、`raw_indices=[1,2]`；
- errors 同时包含 `PARAFORMER_TIMESTAMP_MISSING` 与 `PARAFORMER_TIMESTAMP_INVALID`；
- entries 保留索引和原因，无静默丢弃。

部分时间轴的常规缺失/无效行为通过；B-01/I-01 所述“段与段之间非单调”仍是例外。

## 9. 正常空结果

20 秒静音真实本地探针结果：0 segment，`warnings=[]`、`errors=[]`，没有 `timeline_status=unavailable`，未误报为时间轴失败。`_segments_from_result([], duration)` 的独立内存探针也得到相同语义。

现有自动测试只通过 `assess_silence(_result([]))` 间接覆盖空结果，没有直接锁定 Paraformer 的 `timeline_status` 行为；真实探针补充证明当前行为正确，但仍建议 FIX2 增加单元测试。

## 10. 既有 399 段回归

运行 `experiments/asr/tests` 时，cold 和 warm 两个参数化回归用例将既有 raw 重新转换到 pytest 的 D 盘临时目录，并逐字节比较正式结果。结果：

- cold/warm raw 均为 1 个顶层 item、399 条 `sentence_info`；
- cold/warm 均为 399 segments；
- start/end/text 与原统一结果完全一致；
- 字符数 4,288；
- 语音覆盖 `696.7499999999995` 秒（显示为 696.75 秒）；
- 首段 `0.11—0.35`，末段 `824.59—827.66`；
- warnings/errors 均为空；
- unified/SRT/TXT 与正式文件逐字节一致；
- `runtime/asr-benchmark/results/paraformer` 未被改写。

预期哈希全部命中：

| 文件 | cold SHA-256 | warm SHA-256 | 结果 |
|---|---|---|---|
| raw | `5AB6963BC641A89A9A182CC6642D67A5EA12CCCC47FC0CAE6679AE23E82575C2` | 同 cold | 一致 |
| unified | `9D1593D19481E48E987A70A5642B323C55AE07698354BB4CACCD155605294EE1` | 同 cold | 命中预期 |
| SRT | `6FD4ED953AACA956B8F8CC076C44C2907FE8D7F124795E290E4DAAB1EDDEDE37` | 同 cold | 命中预期 |
| TXT | `E77ADEFF8A1E8269A046576634BDDC4B976498A79B61C99EE2F95D8F26FC47CB` | 同 cold | 命中预期 |
| metrics | `7CD70243A128026FA29E1B7F6E852B4378F06B92C38D5E21782BC9BD7B48A82D` | `B97A44E16B88E6990A6A253EED0C9708E9873CE97007BACB7296DFD8D025A3E3` | 前后不变 |

## 11. 人工审核包保护

| 文件 | 字节数 | SHA-256 | 结果 |
|---|---:|---|---|
| `项目/ASR基准/output/人工审核对比.csv` | 22,253 | `3A31CEA90B97BBF7DFF032627E0B344A26EF09490964D3E37F7CE78ECED7421B` | 命中预期，未变化 |
| `项目/ASR基准/output/人工审核对比.md` | 24,407 | `4077FFE5834902B9B6B28F45DA0CE8CF3F28E0A12BCB3EE92292E2D71E2EE504` | 命中预期，未变化 |

完整读取结果：CSV 为 1 行表头加 20 个窗口，8 列；Markdown 有 20 个窗口和每窗 3 个候选。哈希与 TASK-002-R 接受的原包完全相同，因此三候选文字未改写。文件继续明确“准确率排名待人工审核”，没有加入伪造准确率、冠军或最终生产模型结论。

## 12. 代码简洁性与可维护性

优点：

- 修复主要集中在 `paraformer.py` 的提取/issue 构造和 `common.py` 的统一产物失败语义，没有修改正式 `src/liveclip`；
- `SegmentExtraction` 将 segments、warnings、errors、status 集中返回，结构清楚；
- `PARAFORMER_UNTIMED_TEXT_EXCLUDED`、`PARAFORMER_TIMESTAMP_MISSING`、`PARAFORMER_TIMESTAMP_INVALID` 命名稳定；
- 无 399、样本哈希或 827.690688 的生产适配器硬编码；固定时长只存在于固定样本 benchmark orchestrator 和回归测试。

维护风险：

- `_timestamp_range()` 自己维护前一 start/end，而 sentence_info 路径只调用 `_millisecond_range()`，造成同一契约两种校验层级；
- `build_unified_result()` 的通用排序位于来源异常检查之后，能够掩盖模型输出顺序异常；
- Paraformer issue 构造与通用最终校验之间没有结构化桥接，导致 I-01 只能得到裸 `ValueError`；
- `common.py` 的修改对于失败产物、SRT 抑制和候选失败语义是必要的，不属于无关扩张；问题在于来源顺序验证不应下放给它。

总体实现不算臃肿，但校验职责分裂已经产生实际漏检，故在可维护性维度实质扣分。

## 13. 测试质量与实际结果

| 检查 | 通过 | 失败 | 跳过 | 耗时/说明 |
|---|---:|---:|---:|---|
| `experiments/asr/tests` | 31 | 0 | 0 | pytest 0.24 秒；1 条既有 `audioop` 弃用警告 |
| `tools/Run-Tests.ps1 -ra --durations=10` | 148 | 0 | 0 | pytest 32.20 秒；完整命令约 33.7 秒；脚本内 pip check 通过 |
| `tools/Validate-Media.ps1` | 18 | 0 | 0 | 能力检查、合成链路、同步和集成测试通过；`TRIM_VALID=True`、`BURN_VALID=True` |
| 基础 `.venv` 独立 pip check | 1 | 0 | 0 | `No broken requirements found.` |
| 三个 ASR 环境 pip check | 3 | 0 | 0 | 全部 `No broken requirements found.` |

测试真实性通过：没有失败、跳过或伪造计数。覆盖质量不足之处见 B-01/I-01/I-02；“31 passed”不能替代缺失的 sentence_info 非单调行为测试。

## 14. Paraformer 30 秒离线与 20 秒静音探针

只加载本地 Paraformer/FSMN-VAD/CT-Punc 一次，只处理 30 秒 probe 和 20 秒静音，没有处理 827.69 秒完整音频。

| 探针 | SHA-256 | 推理耗时 | segments | 时间范围 | warnings/errors/status |
|---|---|---:|---:|---|---|
| 30 秒真实音频 | `756E854A01DD7786D5D8702E35DBEE6265EF6EAAE8DA241FF630EA59BBF9EDBF` | 3.229 秒 | 18 | 0.11—30.0 秒 | 0 / 0 / 无 |
| 20 秒静音 | `F2C955578877C05BEA043B1561D21FF3D529EC82BFE46F98E6516B0E0383BB38` | 0.105 秒 | 0 | 无 | 0 / 0 / 无 |

模型加载约 36.52 秒；本次不把加载波动用于横向性能判断。探针处于 `offline_network_guard(True)`，记录 `socket connections blocked`；三个模型均从 D 盘绝对路径加载，`trust_remote_code: False`。FunASR 打印通用 `download models from model hub: ms` 文案，但连接守卫未触发失败，紧随其后的日志均为本地权重路径，没有下载产物或远端回退证据。

## 15. 基础、媒体、环境和 lock

- 基础 `.venv` freeze 为 12 行，复核前后相同：`annotated-types`、`colorama`、`iniconfig`、`packaging`、`pip`、`pluggy`、`pydantic`、`pydantic_core`、`Pygments`、`pytest`、`typing-inspection`、`typing_extensions`；
- sherpa-onnx：freeze 5 行，lock 5 行，顺序和内容完全一致；
- funasr：freeze 86 行，lock 86 行，顺序和内容完全一致；
- faster-whisper：freeze 27 行，lock 27 行，顺序和内容完全一致；
- 三环境 freeze 均无包名包含 CUDA/NVIDIA；FunASR 实测 `torch 2.11.0+cpu`、`torch.version.cuda=None`、`torch.cuda.is_available()=False`；
- 四个环境 `pip check` 全部通过；未执行 pip install/uninstall/update。

## 16. Git、安全和任务边界

开始时：

- HEAD：`59c1d895a92d9b8319e04dd1d7fa933ef894c1a7`；
- branch：`master`；tag at HEAD：`baseline-task-001`；
- remote：无；staged：空；
- 工作区已有 `.gitignore`、`docs/CURRENT_STATUS.md`、`docs/DECISIONS.md` 修改，以及 TASK-002/FIX 的未跟踪文档、`experiments/`；这些都是本复核前状态。

结束时除新增本报告及允许的 `runtime/` 测试日志/临时产物外，上述状态不变。没有创建 commit、tag、remote 或 push。`src/liveclip` Git diff 为空；SenseVoice/Faster-Whisper 适配器哈希不变。

边界核验：

- 未删除、改写或上传原 MP4、WAV、字幕、审核包或结果；
- 未调用云端 ASR、收费 API、OpenAI API；未写 API key；
- 未下载或更新模型；未安装、更新或删除依赖；
- 未修改系统/用户 PATH、永久环境变量或电源计划；
- 未运行 SenseVoice/Faster-Whisper，也未运行任何全长 ASR；
- 未安装 CUDA、GPU PyTorch 或 NVIDIA 包；
- 未执行 TASK-003；项目正式位置没有 `timeline.json`；基础测试只在 `runtime/temp/pytest-*` 生成了允许的契约往返测试临时 `timeline.json`；
- 未修改正式 `src/liveclip`、SenseVoice 或 Faster-Whisper 适配器；
- 既有完整全长结果未改写。

## 17. 文档一致性

一致项：

- 修复范围只处理 Paraformer 时间戳契约；
- 既有 399 段和人工审核包不受影响；
- 人工准确率仍待审核，没有 CER/WER 或准确率冠军；
- TASK-002 原实验为接电，TASK-002-R 复跑为电池供电；文档没有把性能波动归因于单一因素；
- 尚未确定最终生产模型；
- 未执行 TASK-003；
- 文档仍把 TASK-002-FIX 标为等待本次独立复核。

不一致项：

- `CURRENT_STATUS.md`、`TASK-002-FIX.md`、`TASK-002-FIX_RESULT.md` 声称格式、有限性、正序、单调和边界校验已完整覆盖，且实验测试覆盖“非单调”；实际只覆盖顶层 timestamp 数组内部的非单调，未覆盖 sentence_info 条目间的单调性。

该不一致必须由 FIX2 的代码、测试和后续任务文档修正；本只读复核没有修改这些文件。

## 18. 文件哈希变化

以下受保护对象在动态测试/探针前后均一致；本报告为唯一正式新增文件。

| 对象 | SHA-256 | 变化 |
|---|---|---|
| `paraformer.py` | `65EE6A5F9A7DADCAA128492D0AF7EE893D35470C7ABDDEA9E75470A6E64247DF` | 无 |
| `common.py` | `1D1D4D6228AF7EB4754C309B0F987CE067E70523F175961474CD6D3282CD6208` | 无 |
| SenseVoice adapter | `26FD77B8804FA5548FDB5CC09926E4AD3D1F04381BC28CC1365C2AECF14A5B48` | 无 |
| Faster-Whisper adapter | `CFD7C2D99CBA326ED48774257034C7871CA812B46BABDBD2A1AB0EDB0EF388CF` | 无 |
| 原 MP4 | `DA2CD4041C7FB59A1DFC08C80B0358C28DBBDC59608A469EB1A0A8AC63694BFF` | 无 |
| 统一 WAV | `9625C4ED1A2A501DE580BB7713ABEC3F964B93EFFFE6AF3735F719964B4E0CEA` | 无 |
| SenseVoice 主权重 | `C71F0CE00BEC95B07744E116345E33D8CBBE08CEF896382CF907BF4B51A2CD51` | 无 |
| Paraformer 主权重 | `3D491689244EC5DFBF9170EF3827C358AA10F1F20E42A7C59E15E688647946D1` | 无 |
| FSMN-VAD 主权重 | `B3BE75BE477F0780277F3BAE0FE489F48718F585F3A6E45D7DD1FBB1A4255FC5` | 无 |
| CT-Punc 主权重 | `7176CAE922A872E130E6B88AEF9A1153581711BAF79C9124C7C95BE383CD6F81` | 无 |
| Faster-Whisper 主权重 | `3E305921506D8872816023E4C273E75D2419FB89B24DA97B4FE7BCE14170D671` | 无 |
| sherpa lock | `C669450E3FB69C0D1A324C9E90D7C20DD3A8152E3326C3909BF2222C770E9733` | 无 |
| funasr lock | `DB7982738C5A0556AF1212688359CB6B9CD7C5ABE55820DC3E2F649FD5707B03` | 无 |
| faster-whisper lock | `DB9470C8F285427D9BEFBD7664A76C2FC1C61EED0648496900774248C8121171` | 无 |

正式 Paraformer cold/warm raw/unified/SRT/TXT/metrics 的哈希见第 10 节，人工审核包见第 11 节，均未变化。基础 freeze 和三个 ASR freeze/lock 比较见第 15 节，均未变化。

## 19. 最终建议

**需要 TASK-002-FIX2**

FIX2 应保持最小范围：补齐 Paraformer 来源顺序的单调校验和结构化排除，增加 sentence_info/跨 raw/结束时间回退/正常空结果行为测试，并同步修正文档。修复前不得把 TASK-002-FIX 标记为独立复核通过；仍不执行 TASK-003，也不宣布准确率冠军或最终生产模型。
