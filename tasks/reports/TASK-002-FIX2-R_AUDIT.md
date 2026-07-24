# TASK-002-FIX2-R｜最终定向独立复核与质量评分

- 复核日期：2026-07-23（Asia/Shanghai）
- 项目：`<PROJECT_ROOT>`
- 复核范围：仅 Paraformer 来源顺序、结构化排除/SRT 抑制、399 段与人工审核包回归、测试/代码/文档/安全边界
- 唯一正式写入：本报告；定向探针、回归重建和既有测试只在 `runtime/` 产生允许的临时产物或日志
- 明确未执行：三套完整全长模型实验、SenseVoice/Faster-Whisper 推理、TASK-003、下载/安装/上传、云端 ASR/收费 API、Git commit/tag/remote/push

## 1. 审核结论

**结论：通过。**

**总分：100/100；等级：通过。**

独立逐行检查与动态探针确认，TASK-002-FIX2 已在 Paraformer 来源层补齐 `sentence_info` 条目间及多个 raw item 间的单调校验。倒序、end 回退和跨 raw 回退条目均在进入公共排序前结构化排除；比较基准始终是上一个已接受有效段，异常后可以恢复。部分有效只保留真实时间段，全部不可用会保留失败产物并抑制正常 SRT，正常空结果和 20 秒静音不会误报 unavailable。

现有 cold/warm 399 段、SRT、TXT、metrics、20 窗口人工审核包、原媒体、模型、环境和锁文件均无回归。37 项 ASR 实验测试、148 项基础测试、18 项媒体验证全部通过，0 failed、0 skipped。没有发现停止规则定义的真实阻断项。

根据停止规则，TASK-002 技术实验阶段可以正式结束；下一阶段仅进入人工准确率审核。本结论不宣布准确率冠军，也不确定最终生产模型。

## 2. 七维评分

| 维度 | 满分 | 得分 | 扣分原因 | 支撑证据 |
|---|---:|---:|---|---|
| 需求实现程度 | 25 | 25 | 无扣分 | 四类来源顺序/失败语义探针全部符合；399 段与审核包无回归。 |
| 正确性与稳定性 | 20 | 20 | 无扣分 | 倒序、end 回退、跨 raw、异常后恢复、全不可用和正常空结果均得到预期结构化结果；正式 cold/warm 重建逐字节一致。 |
| 测试与验证质量 | 15 | 15 | 无扣分 | ASR 37 passed、基础 148 passed、媒体 18 passed，均 0 failed/0 skipped；六类 FIX2 行为和 399 段字节回归有真实测试覆盖。 |
| 代码简洁与可维护性 | 15 | 15 | 无扣分 | 修复集中在 `paraformer.py`，`common.py` 未变；同一辅助函数和同一“上一个已接受范围”游标覆盖 sentence/top-level/cross-raw。 |
| 性能与资源影响 | 10 | 10 | 无扣分 | 新校验为单次线性扫描；30 秒输出与既有结果逐字段一致，未引入模型、环境或全长实验开销。 |
| 安全与任务边界 | 10 | 10 | 无扣分 | 未下载、安装、上传、联网回退或运行其他候选/全长实验；媒体、模型、环境、正式结果和 Git 基线不变。 |
| 文档与可追溯性 | 5 | 5 | 无扣分 | 当前状态、决策、模型报告、FIX2 任务/结果与代码和测试一致；历史 FIX 过宽表述已由 FIX-R/FIX2 当前文档纠正。 |
| **总分** | **100** | **100** | **无扣分** | **通过。** |

## 3. 阻断问题

**无。**

未发现 sentence_info/跨 raw 非单调进入正常时间轴、end 回退不可追溯、全部无可用时间轴仍生成正常 SRT、399 段或审核包回归、关键测试失败/跳过、受保护文件变化、基础 `.venv` 污染、上传/云端回退、TASK-003 或报告不真实等阻断项。

## 4. 重要问题

**无。**

## 5. 一般建议

**无需要触发 FIX3 的建议。** 公共层保留通用排序、人工准确率未完成、CER/WER 未计算、CAM++ 未运行、`audioop` 弃用警告、供电性能波动和未来 Python 3.13 兼容均按本次停止规则保留为非阻断背景，不扩大任务范围。

## 6. sentence_info 倒序

独立调用当前 `_build_paraformer_unified()`，输入 `1000—2000 ms` 的“后句”后再输入 `100—500 ms` 的“前句”，结果：

- 只保留 `1.0—2.0` 的“后句”；“前句”未进入 segment；
- `timeline_status=partial`；
- warning 为 `PARAFORMER_UNTIMED_TEXT_EXCLUDED`；
- error 为 `PARAFORMER_TIMESTAMP_INVALID`；
- issue 精确包含 `raw_index=0`、`sentence_index=1`、`start=0.1`、`end=0.5`、`previous_start=1.0`、`previous_end=2.0`、`reason=timestamp_non_monotonic`、`raw_text_preserved=true` 和 `timestamp_unit=seconds`；
- SRT 只有“后句”，不含“前句”。

该异常在 `paraformer.py` 来源层排除，不会被 `common.py` 的排序洗正。

## 7. end 回退

输入第一句 `0—2000 ms`、第二句 `1000—1500 ms`，结果：

- 只保留第一句；第二句在 Paraformer 来源层结构化排除；
- `timeline_status=partial`；
- issue 为 `timestamp_non_monotonic`，并保留当前 `1.0—1.5` 与前序 `0.0—2.0`、raw/sentence 索引和 raw 可追溯标记；
- 写入临时产物成功，raw/unified 中均有结构化记录；
- SRT 不含第二句，未依赖公共层裸 `ValueError` 才失败。

## 8. 跨 raw 倒序

输入 raw 0 的 `1.0—2.0`“后段”，再输入 raw 1 的 `0.1—0.5`“前段”，结果：

- 只保留“后段”，SRT 不含“前段”；
- `timeline_status=partial`；
- warning/error 分别为 `PARAFORMER_UNTIMED_TEXT_EXCLUDED` / `PARAFORMER_TIMESTAMP_INVALID`；
- issue 为 `raw_index=1`、`sentence_index=0`，并保留当前/前序秒值、`timestamp_non_monotonic` 和 `raw_text_preserved=true`。

## 9. 异常后恢复

输入“正常一” `1.0—2.0`、异常段 `0.1—0.5`、随后“正常二” `2.0—2.5`，结果只保留正常一和正常二。异常 issue 的比较基准仍为正常一的 `1.0—2.0`，证明被排除条目没有推进游标，也没有永久阻断后续正常段。所有保留时间与模型输入一致，没有排序重分配或猜测。

## 10. 全部不可用

使用顶层非单调时间数组 `[[1000,2000],[100,500]]` 的文本输入，结果：

- 0 segment；`timeline_status=unavailable`；
- warning/error 为既有 `PARAFORMER_UNTIMED_TEXT_EXCLUDED` / `PARAFORMER_TIMESTAMP_INVALID`，reason 为 `timestamp_non_monotonic`；
- 临时目录保留 `raw.json`、`unified.json`、`metrics.json`、`transcript.txt`；
- `metrics.success=false`；
- 不存在 `transcript.srt`；
- `write_run_artifacts()` 在保存失败产物后抛出既有 `TimelineUnavailableError`；
- 没有生成伪造时间轴。

定向产物目录：`runtime/temp/asr/TASK-002-FIX2-R-targeted-20260723-020141/`。

## 11. 正常空结果

空 raw 的直接探针得到 0 segment、`warnings=[]`、`errors=[]`，统一结果不含 `timeline_status`；写产物不抛候选失败，`metrics.success=true`，空 SRT 只是正常空结果。

真实 20 秒静音探针同样为 0 segment、0 warning、0 error、无 unavailable，`hallucination_detected=false`、`nonempty_segment_count=0`。静音没有幻觉，也没有误报候选失败。

## 12. 399 段正式结果回归

完整读取 cold/warm raw、unified、SRT、TXT、metrics，并用当前实现分别在新的 D 盘临时目录重新转换。结果：

- cold/warm raw 均为 1 个顶层 item、399 条 `sentence_info`，模型原始顺序单调；
- 两者均为 399 segments、4,288 字符、语音覆盖 `696.7499999999995` 秒（显示 696.75 秒）；
- 首段 `0.11—0.35`，末段 `824.59—827.66`；
- 每个 segment 的 start/end/text 与 raw 逐条对应，warnings/errors 为空；
- cold/warm 的 raw、unified、SRT、TXT 彼此相同；
- 重新生成的 raw/unified/SRT/TXT/metrics 均与各自正式文件逐字节一致；正式结果目录未改写。

| 文件 | cold SHA-256 | warm SHA-256 | 结果 |
|---|---|---|---|
| raw | `5AB6963BC641A89A9A182CC6642D67A5EA12CCCC47FC0CAE6679AE23E82575C2` | 同 cold | 一致 |
| unified | `9D1593D19481E48E987A70A5642B323C55AE07698354BB4CACCD155605294EE1` | 同 cold | 命中预期 |
| SRT | `6FD4ED953AACA956B8F8CC076C44C2907FE8D7F124795E290E4DAAB1EDDEDE37` | 同 cold | 命中预期 |
| TXT | `E77ADEFF8A1E8269A046576634BDDC4B976498A79B61C99EE2F95D8F26FC47CB` | 同 cold | 命中预期 |
| metrics | `7CD70243A128026FA29E1B7F6E852B4378F06B92C38D5E21782BC9BD7B48A82D` | `B97A44E16B88E6990A6A253EED0C9708E9873CE97007BACB7296DFD8D025A3E3` | 各自逐字节一致 |

回归产物目录：`runtime/temp/asr/TASK-002-FIX2-R-regression-20260723-020211/`。

## 13. 人工审核包

| 文件 | 字节数 | SHA-256 | 结果 |
|---|---:|---|---|
| `项目/ASR基准/output/人工审核对比.csv` | 22,253 | `3A31CEA90B97BBF7DFF032627E0B344A26EF09490964D3E37F7CE78ECED7421B` | 命中预期，未变化 |
| `项目/ASR基准/output/人工审核对比.md` | 24,407 | `4077FFE5834902B9B6B28F45DA0CE8CF3F28E0A12BCB3EE92292E2D71E2EE504` | 命中预期，未变化 |

完整读取及内存重建确认：CSV 为 20 个数据窗口、8 列；Markdown 为 20 个窗口、60 个候选小节；使用三个正式 warm unified 和统一 WAV 调用 `build_windows()` 后，20 行窗口时间、标签、分歧分及三候选文字全部精确一致。文件仍明确“准确率排名待人工审核”，没有准确率冠军或最终生产模型结论。

## 14. 代码简洁性与可维护性

- `paraformer.py` SHA-256 为 `9CB783C5F2894DD198EECB64C844090DE0079791CB7DE412BC7F7B49F2B32EB3`；修复集中于该适配器。
- `common.py` SHA-256 仍为 `1D1D4D6228AF7EB4754C309B0F987CE067E70523F175961474CD6D3282CD6208`，与 FIX2 前一致。
- `_source_order_issue_details()` 是 sentence_info、顶层 timestamp 内部和跨 raw 的统一单调比较逻辑。
- `previous_accepted_range` 只在 segment 被接受后推进，职责和恢复语义清晰。
- warning/error、partial/unavailable 和失败产物均复用既有体系，没有第二套状态或错误码。
- 未发现明显重复、死代码、过度抽象或无关大范围重构。
- 生产适配器未硬编码 399、正式哈希或固定样本时长；`827.690688` 只存在于固定样本 benchmark 编排器和测试。
- SenseVoice 与 Faster-Whisper adapter 哈希分别保持 `26FD77B8...14A5B48`、`CFD7C2D9...F388CF`；正式 `src/liveclip` 与 Git HEAD 无差异。

## 15. 测试质量

| 检查 | 通过 | 失败 | 跳过 | 结果 |
|---|---:|---:|---:|---|
| `experiments/asr/tests` | 37 | 0 | 0 | 0.33 秒；仅 1 条既有 `audioop` 弃用 warning |
| `tools/Run-Tests.ps1 -ra --durations=10` | 148 | 0 | 0 | pytest 27.30 秒；脚本内 pip check 通过 |
| `tools/Validate-Media.ps1` | 18 | 0 | 0 | 能力检查、合成链路、同步与关键集成通过；`TRIM_VALID=True`、`BURN_VALID=True` |

逐行检查 `test_paraformer.py` 确认真实覆盖 sentence_info 倒序、end 回退、跨 raw 倒序、异常后恢复、全不可用、正常空结果、部分有效、失败产物/SRT 抑制及 cold/warm 399 段字节回归。37 项不是用跳过或预设结果得到；实际执行为 0 failed、0 skipped。

## 16. Paraformer 30 秒离线与 20 秒静音探针

只加载一次 D 盘本地 Paraformer/FSMN-VAD/CT-Punc，并在同一个 `offline_network_guard(True)` 中依次处理 30 秒 probe 和 20 秒静音；没有读取 827.69 秒完整音频。

| 探针 | SHA-256 | 推理秒 | segments | warnings/errors/status | 与既有结果 |
|---|---|---:|---:|---|---|
| 30 秒真实音频 | `756E854A01DD7786D5D8702E35DBEE6265EF6EAAE8DA241FF630EA59BBF9EDBF` | 2.399 | 18 | 0 / 0 / 无 | unified 逐字段一致 |
| 20 秒静音 | `F2C955578877C05BEA043B1561D21FF3D529EC82BFE46F98E6516B0E0383BB38` | 0.049 | 0 | 0 / 0 / 无 | unified 逐字段一致 |

模型加载约 32.996 秒；不将加载波动用于横向性能结论。三个模型路径均为 D 盘绝对路径，`disable_update=True`、`trust_remote_code=False`、CPU-only；socket guard 覆盖加载和两次推理。FunASR 的通用 “download models from model hub” 文案后实际读取三个本地权重，守卫未出现联网回退或下载证据。

探针产物目录：`runtime/temp/asr/TASK-002-FIX2-R-short-20260723-020303/`。

## 17. 基础、媒体、环境和 lock

| 环境 | freeze 行数 | freeze SHA-256 | pip check | 与 lock |
|---|---:|---|---|---|
| 基础 `.venv` | 12 | `D229DCA2B2B1A55B88896C5C28E25B16053DB180FAF1E4772872AC7BEAB414DB` | 通过 | 审计前后完全一致 |
| sherpa-onnx | 5 | `C669450E3FB69C0D1A324C9E90D7C20DD3A8152E3326C3909BF2222C770E9733` | 通过 | 5 行有序逐行一致 |
| funasr | 86 | `DB7982738C5A0556AF1212688359CB6B9CD7C5ABE55820DC3E2F649FD5707B03` | 通过 | 86 行有序逐行一致 |
| faster-whisper | 27 | `DB9470C8F285427D9BEFBD7664A76C2FC1C61EED0648496900774248C8121171` | 通过 | 27 行有序逐行一致 |

四个环境均为 `No broken requirements found.`。三个 ASR freeze 中名称含 CUDA/NVIDIA 的包为 0；FunASR 实测 `torch=2.11.0+cpu`、`torch.version.cuda=None`、`torch.cuda.is_available()=False`，CTranslate2 CUDA device count 为 0。没有执行 install/uninstall/update。

媒体验证同时通过项目本地 FFmpeg 强制能力、合成端到端流程、17 项同步单元测试和 1 项关键 FFmpeg 集成测试；系统 PATH 未修改。

## 18. 文档一致性

完整核对 `CURRENT_STATUS.md`、`DECISIONS.md`、`ASR_MODEL_COMPARISON_REPORT.md`、`TASK-002-FIX2.md`、`TASK-002-FIX2_RESULT.md` 与实际代码/测试，以下叙述一致：

- FIX-R 为 79/100，原因是 sentence_info 条目间和跨 raw 来源顺序漏检；
- FIX2 在 Paraformer 来源层补齐单调校验，公共排序不再掩盖该来源异常；
- 比较基准是上一个已接受有效段，异常后允许恢复；
- 正常 399 段和人工审核包不受影响；
- 人工准确率、CER/WER 和最终生产模型仍待审核；
- 未执行 TASK-003，文档在本次复核前保持“等待 FIX2-R”。

历史 FIX 文档的过宽表述已由 FIX-R 审计、当前状态和 FIX2 文档明确纠正，按指令不要求改写历史报告。

## 19. 安全与任务边界

- 原 MP4、统一 WAV、五个模型主权重、正式 Paraformer 结果和人工审核包哈希前后不变；
- 没有删除、覆盖或上传视频、音频、字幕、审核包或结果；
- 没有调用云端 ASR、收费 API、OpenAI API 或远端回退；
- 没有下载/更新模型，没有安装/更新/删除依赖；
- 没有修改系统/用户 PATH、永久环境变量或电源计划；
- 没有运行 SenseVoice、Faster-Whisper 或任何完整全长 ASR；
- 没有安装 CUDA、GPU PyTorch 或 NVIDIA 包，基础 `.venv` 未污染；
- 没有执行 TASK-003，没有生成正式 `timeline.json`，正式 `src/liveclip` 无差异；
- 没有创建 commit、tag、remote 或 push；staged 文件为 0；
- 正式 Paraformer 结果的时间戳保持 2026-07-19，未被本次重写。

源码检索未发现 HTTP endpoint、上传函数、云端 SDK 或失败后云端 ASR 路径；仅发现离线 socket guard 和 benchmark 主动移除常见 token 环境变量。

## 20. Git 基线与工作区

审计开始与结束均为：

- HEAD：`59c1d895a92d9b8319e04dd1d7fa933ef894c1a7`；
- branch：`master`；
- tag at HEAD：`baseline-task-001`；
- remote：无；staged：空；
- 既有工作区：`.gitignore`、`docs/CURRENT_STATUS.md`、`docs/DECISIONS.md` 为已修改，TASK-002/FIX/FIX2 文档和 `experiments/` 为未跟踪；这些均为本次开始前状态。

完成后除新增本报告和被 Git 忽略的允许 `runtime/` 临时产物/日志外，Git 状态与审计前一致。

## 21. 文件哈希变化

以下对象在审计前和全部测试/探针完成后相同：

| 对象 | SHA-256 | 变化 |
|---|---|---|
| `paraformer.py` | `9CB783C5F2894DD198EECB64C844090DE0079791CB7DE412BC7F7B49F2B32EB3` | 无 |
| `common.py` | `1D1D4D6228AF7EB4754C309B0F987CE067E70523F175961474CD6D3282CD6208` | 无 |
| Paraformer warm unified | `9D1593D19481E48E987A70A5642B323C55AE07698354BB4CACCD155605294EE1` | 无 |
| Paraformer warm SRT | `6FD4ED953AACA956B8F8CC076C44C2907FE8D7F124795E290E4DAAB1EDDEDE37` | 无 |
| Paraformer warm TXT | `E77ADEFF8A1E8269A046576634BDDC4B976498A79B61C99EE2F95D8F26FC47CB` | 无 |
| 人工审核 Markdown | `4077FFE5834902B9B6B28F45DA0CE8CF3F28E0A12BCB3EE92292E2D71E2EE504` | 无 |
| 人工审核 CSV | `3A31CEA90B97BBF7DFF032627E0B344A26EF09490964D3E37F7CE78ECED7421B` | 无 |
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

基础 `.venv` 的 12 行 freeze 及三个 ASR 环境的 5/86/27 行 freeze 在审计前后完全一致。

## 22. 最终建议

**技术实验通过，进入人工准确率审核**

停止 TASK-002 技术实验阶段，不建议 TASK-002-FIX3，不执行 TASK-003。后续只应按单独任务完成人工审核闭环；在该闭环完成前，不宣布准确率冠军或最终生产模型。
