# TASK-002-FIX 完成报告｜Paraformer 时间戳回退修复

## 1. 任务状态

- 状态：**本地实现与验证完成，等待 TASK-002-FIX-R 独立定向只读复核**。
- 完成日期：2026-07-23（Asia/Shanghai）。
- Git 基线保持为 `master` / `59c1d895a92d9b8319e04dd1d7fa933ef894c1a7` / `baseline-task-001`；remote 为空，staged 文件为 0。
- 本次只修复 Paraformer 缺失或异常时间戳时伪造整段音频范围的问题；未执行 TASK-003。

## 2. 原阻断问题修复

原 `_segments_from_result([{"text": "测试文本"}], 827.690688)` 会生成 `start=0.0, end=827.690688`。修复后该输入生成 0 个 segment，不再用完整音频、字符长度、平均分配、相邻结果或任何无模型证据的信息猜测时间轴。

`experiments/asr/adapters/paraformer.py` SHA-256 从 `D73F785193D4A6F1FC0BA0E14561B6F196D0AC9FE064B53E0EB312901B351AF8` 变为 `65EE6A5F9A7DADCAA128492D0AF7EE893D35470C7ABDDEA9E75470A6E64247DF`。

## 3. 新回退行为

- `sentence_info` 或顶层 `timestamp` 只有在格式正确、数值有限、`end > start`、顺序单调且不超出音频边界时才生成 segment。
- 全部文本无可用时间轴时，统一结果标记 `timeline_status=unavailable`；raw/unified/TXT/metrics 写入后候选以 `TimelineUnavailableError` 失败退出，`metrics.success=false`，不生成正常 SRT。
- 部分缺失时标记 `timeline_status=partial`；有真实时间证据的 segment 正常保留，无时间条目不进入 SRT，并记录全部异常索引。
- 静音等“没有文本且没有错误”的正常空结果不被误判为时间轴失败。

## 4. 无时间戳结构化错误

统一结果使用以下机器可读项：

- warning：`PARAFORMER_UNTIMED_TEXT_EXCLUDED`；包含 `timeline_status`、`untimed_text_count`、`raw_indices`、`raw_text_preserved=true` 和逐条 `entries`。
- error：缺失、`None` 或空列表使用 `PARAFORMER_TIMESTAMP_MISSING`；格式错误、非有限值、逆序、非单调或越界使用 `PARAFORMER_TIMESTAMP_INVALID`。
- 每条 entry 保留 `raw_index`、原因以及适用时的 `sentence_index`；原始文本继续完整保留在 raw JSON，可由索引追溯。

## 5. 正常 399 段回归

对既有 Paraformer cold/warm raw 重新转换并写入 pytest 临时目录，结果如下：

- cold 与 warm 均为 399 个 segment、4,288 字符、696.75 秒语音覆盖；start/end/text 全部一致。
- unified、SRT、TXT 均与对应原文件逐字节一致；cold/warm 本身也一致。
- raw SHA-256：`5AB6963BC641A89A9A182CC6642D67A5EA12CCCC47FC0CAE6679AE23E82575C2`。
- unified SHA-256：`9D1593D19481E48E987A70A5642B323C55AE07698354BB4CACCD155605294EE1`。
- SRT SHA-256：`6FD4ED953AACA956B8F8CC076C44C2907FE8D7F124795E290E4DAAB1EDDEDE37`。
- TXT SHA-256：`E77ADEFF8A1E8269A046576634BDDC4B976498A79B61C99EE2F95D8F26FC47CB`。

既有 `runtime/asr-benchmark/results/paraformer` 产物未改写。

## 6. 人工审核包哈希

| 文件 | 字节数 | SHA-256 | 结果 |
|---|---:|---|---|
| `项目/ASR基准/output/人工审核对比.csv` | 22,253 | `3A31CEA90B97BBF7DFF032627E0B344A26EF09490964D3E37F7CE78ECED7421B` | 前后不变 |
| `项目/ASR基准/output/人工审核对比.md` | 24,407 | `4077FFE5834902B9B6B28F45DA0CE8CF3F28E0A12BCB3EE92292E2D71E2EE504` | 前后不变 |

现有 20 个审核窗口及其文本未修改；人工准确率审核仍未完成。

## 7. 新增测试

新增 `experiments/asr/tests/test_paraformer.py`，共 19 项，覆盖：

- 顶层 timestamp 字段不存在、`None`、空列表、格式错误、非有限值、逆序、非单调和越界；
- `sentence_info` 的时间字段缺失、`None`、格式错误、非有限值、逆序和越界；
- 无时间文本不产生 `0—827.690688` 或其他伪造 segment；raw 可追溯、候选失败且不生成 SRT；
- 部分有时间/部分无时间时只输出真实时间段，并记录数量和原始索引；
- 有真实顶层 timestamp 的合法回退；
- cold/warm 399 段 unified、SRT、TXT 逐字节回归与覆盖率回归。

完整 `experiments/asr/tests`：**31 passed、0 failed、0 skipped**；仅保留既有 `audioop` Python 3.13 弃用警告。

## 8. 基础与媒体验证

- `tools/Run-Tests.ps1 -ra --durations=10`：**148 passed、0 failed、0 skipped**，pytest 36.93 秒；脚本内 `pip check` 通过。
- `tools/Validate-Media.ps1`：能力检查、合成媒体端到端流程及强制同步/集成测试全部通过，**18 passed**；`TRIM_VALID=True`、`BURN_VALID=True`。
- `.venv/Scripts/python.exe -m pip check`：`No broken requirements found.`；freeze 仍为任务前相同的 12 行。

## 9. Paraformer 短离线探针

只运行 Paraformer 短探针，没有运行任何候选的完整全长实验。产物位于 `runtime/temp/asr/TASK-002-FIX-20260723-003642/`。

| 探针 | segment | 时间范围 | errors/warnings | socket guard | 与既有结果 |
|---|---:|---|---|---|---|
| 30 秒真实音频 | 18 | 0.11—30.0 秒，全部有限、正序、界内 | 0 / 0 | `socket connections blocked` | 18 个 segment 逐字段一致 |
| 20 秒静音 | 0 | 无 segment | 0 / 0 | `socket connections blocked` | 与既有静音结果一致 |

两次均记录 `local_model_load=true`，模型路径为 D 盘本地绝对路径；30 秒转写阶段约 3.446 秒。FunASR 的通用 “download models from model hub” 日志后紧接 D 盘权重加载记录，离线 socket guard 未触发网络连接错误。

## 10. 环境与 lock

| 环境 | freeze 行数 | `pip check` | 与 lock 有序逐行比较 |
|---|---:|---|---|
| 基础 `.venv` | 12 | 通过 | 任务前后相同 |
| sherpa-onnx | 5 | 通过 | 完全一致 |
| funasr | 86 | 通过 | 完全一致 |
| faster-whisper | 27 | 通过 | 完全一致 |

未安装、卸载或更新依赖；未安装 CUDA、GPU PyTorch 或 NVIDIA 包。

## 11. 修改文件

- `experiments/asr/adapters/paraformer.py`
- `experiments/asr/common.py`
- `experiments/asr/tests/test_paraformer.py`
- `docs/CURRENT_STATUS.md`
- `docs/DECISIONS.md`
- `docs/ASR_MODEL_COMPARISON_REPORT.md`
- `tasks/TASK-002-FIX.md`
- `tasks/reports/TASK-002-FIX_RESULT.md`

未修改 SenseVoice、Faster-Whisper、`experiments/asr/adapters/base.py` 或正式 `src/liveclip`；`src/liveclip` Git diff 为空。

## 12. 安全边界

以下关键哈希前后不变：

| 对象 | SHA-256 |
|---|---|
| 原 MP4 | `DA2CD4041C7FB59A1DFC08C80B0358C28DBBDC59608A469EB1A0A8AC63694BFF` |
| 统一 WAV | `9625C4ED1A2A501DE580BB7713ABEC3F964B93EFFFE6AF3735F719964B4E0CEA` |
| SenseVoice 主权重 | `C71F0CE00BEC95B07744E116345E33D8CBBE08CEF896382CF907BF4B51A2CD51` |
| Paraformer 主权重 | `3D491689244EC5DFBF9170EF3827C358AA10F1F20E42A7C59E15E688647946D1` |
| FSMN-VAD 主权重 | `B3BE75BE477F0780277F3BAE0FE489F48718F585F3A6E45D7DD1FBB1A4255FC5` |
| CT-Punc 主权重 | `7176CAE922A872E130E6B88AEF9A1153581711BAF79C9124C7C95BE383CD6F81` |
| Faster-Whisper 主权重 | `3E305921506D8872816023E4C273E75D2419FB89B24DA97B4FE7BCE14170D671` |

- 未下载或更新模型，未安装或更新依赖，未上传视频、音频、字幕或结果。
- 未调用云端 ASR、收费 API 或 OpenAI API；未写入 API key。
- 未修改系统/用户 PATH、永久环境变量或电源计划；探针只设置子进程环境。
- 未运行 SenseVoice/Faster-Whisper，未重跑三套完整全长实验。
- 未执行 TASK-003，未发现正式 `timeline.json`，未创建 commit、tag、remote 或 push。

## 13. 性能波动文档说明

原 TASK-002 实验在接通电源时运行；TASK-002-R 复跑在电池供电时运行。复跑中 SenseVoice RTF 约增加 36.6%，Paraformer RTF 约增加 41.8%，Faster-Whisper 峰值 RSS 约增加 27.8%；三候选仍完成全长转写且输出逐字段一致。

供电状态与背景负载同时变化，不能把波动解释为单一确定因果。后续横向性能比较必须固定电源状态、Windows 电源模式、背景 CPU 负载、线程数、候选顺序和候选间冷却时间。本修复不要求也没有重跑接电全量实验。

## 14. 已知限制

- 人工准确率审核、CER/WER、漏句、重复、专名和标点质量仍未完成；本次修复不改变任何候选的准确率结论。
- CAM++ 未运行、`audioop` 弃用警告及供电性能差异仍是记录项，不阻塞本次时间戳契约修复。
- `timeline_status` 和结构化 warning/error 是本实验统一输出的异常路径扩展，尚未进入正式 `src/liveclip` 数据契约；本任务明确不执行该后续集成。

## 15. 下一步

下一步仅建议执行一次 **TASK-002-FIX-R 定向只读复核**，只检查：无时间戳不再伪造、既有 399 段无回归、测试/文档一致以及安全边界保持。完成后停止；不执行 TASK-003，不宣布准确率冠军或最终生产模型。

## 16. 回滚方法

如用户以后明确要求回滚，应只撤销本报告第 11 节列出的 TASK-002-FIX 代码/文档增量，并可删除被忽略的 `runtime/temp/asr/TASK-002-FIX-20260723-003642/` 短探针产物。回滚必须保留原 MP4、统一 WAV、全部模型、三个 ASR 环境、既有 TASK-002 结果、人工审核包、基础 `.venv`、项目 FFmpeg 和正式 `src/liveclip`；不得使用会覆盖工作区既有未提交内容的破坏性 Git 命令。
