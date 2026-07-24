# TASK-002-FIX2 完成报告｜Paraformer 非单调时间轴修复

## 1. 任务状态

- 状态：**本地实现与验证完成，等待 TASK-002-FIX2-R 独立定向复核与质量评分**。
- 完成日期：2026-07-23（Asia/Shanghai）。
- Git 保持为 `master` / `59c1d895a92d9b8319e04dd1d7fa933ef894c1a7` / `baseline-task-001`；remote 为空，没有 commit、tag 或 push。
- 本次只修复 Paraformer `sentence_info` 条目间、多个 raw item 间的非单调来源顺序及结构化排除；未执行 TASK-003。

## 2. FIX-R 阻断逐项修复

1. sentence_info 倒序：当前异常条目在 Paraformer 提取层排除，不再进入公共排序或正常 SRT。
2. sentence_info end 回退：按 `end >= previous_end` 校验并生成结构化 issue，不再依赖公共 `ValueError` 才失败。
3. 跨 raw 倒序：使用贯穿 raw item 的上一个已接受范围校验，异常 raw/sentence 索引可追溯。
4. 公共排序：`common.py` 保持不变；Paraformer 异常在进入公共层前已排除，排序不再掩盖本来源异常。
5. 测试缺口：新增六类行为测试，并保留原缺失、格式、有限性、逆序、越界、部分时间及 399 段回归。

## 3. sentence_info 单调校验

每个有文本条目先执行数值类型与有限性、`start >= 0`、`end > start`、`end <= audio_duration` 校验；通过后再与上一个已接受有效段比较：

```text
current.start >= previous.start
current.end   >= previous.end
```

任一条件失败时只排除当前条目。正常条目保持模型原始顺序和边界，不排序、不重分配、不按文本猜测时间。

## 4. 跨 raw 单调校验

`previous_accepted_range` 跨 raw item 保持。当前 raw 的首个有时间候选以及其后条目都复用同一个来源顺序辅助函数；被排除的范围不会推进比较基准。后续条目因此仍可相对上一个已接受段独立恢复。

## 5. 结构化错误示例

sentence_info 从 `1.0—2.0` 秒回退到 `0.1—0.5` 秒时：

```json
{
  "raw_index": 0,
  "reason": "timestamp_non_monotonic",
  "raw_text_preserved": true,
  "sentence_index": 1,
  "start": 0.1,
  "end": 0.5,
  "previous_start": 1.0,
  "previous_end": 2.0,
  "timestamp_unit": "seconds"
}
```

该 entry 位于既有 `PARAFORMER_TIMESTAMP_INVALID` error 中；warning 仍为 `PARAFORMER_UNTIMED_TEXT_EXCLUDED`。没有引入第二套错误命名。

## 6. 部分有效与全部不可用

- 部分有效：只保留真实有效段，异常段不进入 SRT；`timeline_status=partial`，warning/error 包含排除数量、raw 索引及 entries。
- 异常后恢复：后续范围与上一个已接受段比较；测试中的“正常一、倒序、正常二”最终保留两个正常段。
- 全部不可用：顶层非单调时间数组产生 0 segment、`timeline_status=unavailable`；raw/unified/TXT/metrics 先保留，`metrics.success=false`，不生成正常 SRT，随后抛出既有 `TimelineUnavailableError`。

## 7. 正常空结果

直接测试 Paraformer 空 raw：0 segment、warnings/errors 为空、不包含 `timeline_status`，写产物不抛候选失败；空 SRT 属于正常空结果。真实 20 秒静音探针也得到 0 segment、0 warning/error、无 unavailable。

## 8. 399 段正式结果回归

cold/warm 既有 raw 均为 1 个顶层 item、399 条 sentence_info。测试只在 pytest 临时目录重建产物，没有改写 `runtime/asr-benchmark/results/paraformer`：

- 399 segments；4,288 字符；覆盖 696.75 秒；首段 `0.11—0.35`，末段 `824.59—827.66`。
- start/end/text 与正式统一结果一致；warnings/errors 为空。
- unified、SRT、TXT 逐字节一致。

| 文件 | cold SHA-256 | warm SHA-256 |
|---|---|---|
| raw | `5AB6963BC641A89A9A182CC6642D67A5EA12CCCC47FC0CAE6679AE23E82575C2` | 同 cold |
| unified | `9D1593D19481E48E987A70A5642B323C55AE07698354BB4CACCD155605294EE1` | 同 cold |
| SRT | `6FD4ED953AACA956B8F8CC076C44C2907FE8D7F124795E290E4DAAB1EDDEDE37` | 同 cold |
| TXT | `E77ADEFF8A1E8269A046576634BDDC4B976498A79B61C99EE2F95D8F26FC47CB` | 同 cold |
| metrics | `7CD70243A128026FA29E1B7F6E852B4378F06B92C38D5E21782BC9BD7B48A82D` | `B97A44E16B88E6990A6A253EED0C9708E9873CE97007BACB7296DFD8D025A3E3` |

## 9. 人工审核包

| 文件 | 字节数 | SHA-256 | 结果 |
|---|---:|---|---|
| `项目/ASR基准/output/人工审核对比.csv` | 22,253 | `3A31CEA90B97BBF7DFF032627E0B344A26EF09490964D3E37F7CE78ECED7421B` | 前后不变 |
| `项目/ASR基准/output/人工审核对比.md` | 24,407 | `4077FFE5834902B9B6B28F45DA0CE8CF3F28E0A12BCB3EE92292E2D71E2EE504` | 前后不变 |

CSV 仍为 20 个窗口、8 列；Markdown 仍为 20 个窗口、每窗 3 个候选。人工准确率审核尚未完成。

## 10. 新增测试与 ASR 结果

`test_paraformer.py` 新增 6 项：

1. sentence_info 倒序只保留第一条且 SRT 不含异常条目；
2. end 回退结构化排除并保留 raw/unified 追溯；
3. 跨 raw 倒序排除且 `raw_index` 正确；
4. 异常后按上一个已接受段恢复；
5. 全不可用时保留失败产物并抑制 SRT；
6. 正常空结果不误报 unavailable。

最终 `experiments/asr/tests`：**37 passed、0 failed、0 skipped**，0.31 秒；仅有既有 `audioop` Python 3.13 弃用 warning。

## 11. Paraformer 短探针

产物位于 `runtime/temp/asr/TASK-002-FIX2-20260723-013923/`。只使用本地 Paraformer/FSMN-VAD/CT-Punc，未运行完整 827.69 秒音频。

| 探针 | 输入 SHA-256 | 推理秒 | segments | warnings/errors/status | 离线 |
|---|---|---:|---:|---|---|
| 30 秒真实音频 | `756E854A01DD7786D5D8702E35DBEE6265EF6EAAE8DA241FF630EA59BBF9EDBF` | 3.154 | 18 | 0 / 0 / 无 | socket guard 通过 |
| 20 秒静音 | `F2C955578877C05BEA043B1561D21FF3D529EC82BFE46F98E6516B0E0383BB38` | 0.274 | 0 | 0 / 0 / 无 | socket guard 通过 |

模型均从 D 盘绝对路径加载，`trust_remote_code: False`。FunASR 通用日志出现 “download models from model hub” 文案，但 socket guard 未触发失败，随后日志明确读取三个本地权重；没有下载或远端回退证据。

## 12. 基础与媒体验证

- `tools/Run-Tests.ps1 -ra --durations=10`：**148 passed、0 failed、0 skipped**，pytest 39.71 秒；脚本内 pip check 通过。
- `tools/Validate-Media.ps1`：能力检查、合成端到端流程及同步/集成测试全部通过，**18 passed**；`TRIM_VALID=True`、`BURN_VALID=True`。
- 基础 `.venv` 独立 `pip check`：`No broken requirements found.`

## 13. 环境与 lock

| 环境 | freeze 行数 | pip check | 与基线/lock 有序逐行比较 |
|---|---:|---|---|
| 基础 `.venv` | 12 | 通过 | 与修复前基线完全一致 |
| sherpa-onnx | 5 | 通过 | 与 lock 完全一致 |
| funasr | 86 | 通过 | 与 lock 完全一致 |
| faster-whisper | 27 | 通过 | 与 lock 完全一致 |

三个 ASR freeze 中名称含 CUDA/NVIDIA 的包均为 0；FunASR 为 `torch 2.11.0+cpu`、`torch.version.cuda=None`、`cuda_available=False`。未执行 install/uninstall/update。

## 14. 代码简洁性

- 生产修改只在 `paraformer.py` 增加一个来源顺序详情辅助函数和一个跨条目“上一个已接受范围”游标；sentence_info、顶层 timestamp 内部及跨 raw 共用同一比较逻辑。
- 复用既有 issue 聚合、错误码、partial/unavailable 与产物失败语义。
- `common.py` 无修改，SHA-256 仍为 `1D1D4D6228AF7EB4754C309B0F987CE067E70523F175961474CD6D3282CD6208`。
- `paraformer.py` SHA-256 从 `65EE6A5F9A7DADCAA128492D0AF7EE893D35470C7ABDDEA9E75470A6E64247DF` 变为 `9CB783C5F2894DD198EECB64C844090DE0079791CB7DE412BC7F7B49F2B32EB3`。
- 未硬编码 399、样本时长或文件哈希到生产逻辑。

## 15. 修改文件

- `experiments/asr/adapters/paraformer.py`
- `experiments/asr/tests/test_paraformer.py`
- `docs/CURRENT_STATUS.md`
- `docs/DECISIONS.md`
- `docs/ASR_MODEL_COMPARISON_REPORT.md`
- `tasks/TASK-002-FIX2.md`
- `tasks/reports/TASK-002-FIX2_RESULT.md`

未修改 `common.py`、SenseVoice/Faster-Whisper 适配器、正式 `src/liveclip`、锁文件、正式结果或人工审核包。

## 16. 安全边界

以下受保护对象前后哈希一致：

| 对象 | SHA-256 |
|---|---|
| 原 MP4 | `DA2CD4041C7FB59A1DFC08C80B0358C28DBBDC59608A469EB1A0A8AC63694BFF` |
| 统一 WAV | `9625C4ED1A2A501DE580BB7713ABEC3F964B93EFFFE6AF3735F719964B4E0CEA` |
| SenseVoice 主权重 | `C71F0CE00BEC95B07744E116345E33D8CBBE08CEF896382CF907BF4B51A2CD51` |
| Paraformer 主权重 | `3D491689244EC5DFBF9170EF3827C358AA10F1F20E42A7C59E15E688647946D1` |
| FSMN-VAD 主权重 | `B3BE75BE477F0780277F3BAE0FE489F48718F585F3A6E45D7DD1FBB1A4255FC5` |
| CT-Punc 主权重 | `7176CAE922A872E130E6B88AEF9A1153581711BAF79C9124C7C95BE383CD6F81` |
| Faster-Whisper 主权重 | `3E305921506D8872816023E4C273E75D2419FB89B24DA97B4FE7BCE14170D671` |

- 未下载/更新模型，未安装/更新依赖，未上传视频、音频、字幕或结果。
- 未调用云端 ASR、收费 API 或 OpenAI API；未运行 SenseVoice/Faster-Whisper 或三套完整全长实验。
- 未修改系统/用户 PATH 或永久环境变量；未安装 CUDA/NVIDIA；未污染基础 `.venv`。
- 未执行 TASK-003，未生成正式 `timeline.json`，未创建 commit、tag、remote 或 push。

## 17. 文档修正

- `CURRENT_STATUS.md` 记录 FIX-R 79/100 不通过、FIX2 本地完成并等待 FIX2-R；原“31 项覆盖全部非单调”的过宽表述已限定为顶层 timestamp 数组内部场景。
- `DECISIONS.md` 增加 Paraformer 来源顺序必须在适配器层校验、与上一个已接受段比较、正常空结果不属于 unavailable 的决策。
- 模型对比报告补充 FIX-R 漏检、FIX2 策略、399 段无影响及人工准确率仍待审核。
- 历史 `TASK-002-FIX.md` 和 `TASK-002-FIX_RESULT.md` 按允许修改清单未改写；其过宽表述由 FIX-R 审计、本任务文件和当前状态明确纠正。

## 18. 已知限制

- 人工准确率、CER/WER、漏句、重复、专名和标点质量仍待审核；不宣布准确率冠军或最终生产模型。
- CAM++、`audioop` 弃用和供电性能差异属于后续记录，不阻塞本次修复。
- 公共层仍保留通用排序；本任务通过 Paraformer 来源层排除保证异常不会进入该排序，不大范围改写其他候选。

## 19. 下一步

下一步仅建议执行一次 **TASK-002-FIX2-R｜定向独立复核与质量评分**，只核对来源单调性、结构化排除、399 段/审核包无回归、测试、代码简洁性、文档和安全边界。完成后停止，不执行 TASK-003。

## 20. 回滚方法

如用户以后明确要求回滚，只撤销第 15 节列出的 FIX2 增量，并可移除被忽略的 `runtime/temp/asr/TASK-002-FIX2-20260723-013923/` 短探针产物。必须保留原 MP4、统一 WAV、全部模型、三个 ASR 环境、既有 399 段正式结果、人工审核包、基础 `.venv`、项目 FFmpeg 和正式 `src/liveclip`；不得使用覆盖现有未提交工作的破坏性 Git 命令。
