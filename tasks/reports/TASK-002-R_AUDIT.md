# TASK-002-R｜本地 ASR 模型对比独立只读复核报告

- 复核日期：2026-07-21（Asia/Shanghai）
- 项目：`<PROJECT_ROOT>`
- 复核范围：TASK-002 的源码、测试、锁文件、环境、模型、媒体、日志、既有结果、人工审核包和项目文档
- 唯一正式写入：本报告；测试与复跑另在 `runtime/` 留下允许的日志和临时结果
- 准确率边界：本轮没有人工参考字幕，不计算 CER/WER，不判断任何候选的真实文本准确率

## 1. 审核结论

**结论：需要 TASK-002-FIX。**

三候选的官方来源、独立 D 盘环境、锁文件、CPU/离线配置、现有结果、静音结果和人工审核包总体可信。三项 30 秒离线探针和三项完整暖跑均成功；复跑的 segment 内容与原暖跑逐字段完全一致；基础 148 项、媒体验证 18 项和 ASR 实验 12 项测试全部通过；没有发现上传、云端 ASR、收费 API、CUDA/NVIDIA 依赖、基础环境污染、正式源码修改或伪造准确率。

不能直接判为“技术实验通过”的原因是 `experiments/asr/adapters/paraformer.py::_segments_from_result()` 在 FunASR 返回非空文本、但同时缺失 `sentence_info` 和 `timestamp` 时，会构造 `start=0.0, end=完整音频时长` 的 segment。该行为把未知时间范围写成确定的全长时间轴，违反本复核的硬性要求“统一输出不伪造缺失字段”。既有 Paraformer 结果均含真实 `sentence_info`，因此已生成的 399 段结果未受影响；但代码契约本身不满足通过条件。

复跑还显示供电和系统负载变化会显著影响性能：本次全程电池供电，SenseVoice/Paraformer 的 RTF 分别比报告高 36.6%/41.8%，Faster-Whisper 的峰值 RSS 比报告高 27.8%，超过建议波动线；三者仍处于相同数量级，输出完全一致。这是需要保留的复现限制，不是准确率或结果真实性证据。

## 2. 阻断问题

未发现数据上传、云端回退、样本损坏、来源完全不可追溯、基础环境污染、GPU 依赖、核心测试失败或现有输出时间轴无效等安全/数据阻断问题。

但“技术实验通过”被第 3 节 I-01 阻断：输出契约要求明确禁止伪造未知时间字段，而当前 Paraformer 回退路径可生成伪造的全长时间轴。该问题必须在独立 `TASK-002-FIX` 中修复和回归后再判通过。

## 3. 重要问题

### I-01｜Paraformer 缺失时间戳时伪造整段音频范围

- 证据位置：`experiments/asr/adapters/paraformer.py` 的 `_segments_from_result()`。
- 触发条件：`item["text"]` 非空，`sentence_info` 为空，`timestamp` 为空。
- 只读复现输入：`[{"text": "x"}]`，音频时长 `827.690688`。
- 实际返回：一个文本为 `x`、范围为 `0.0—827.690688` 的 segment，`words=[]`。
- 影响：未知切点被表达成确定切点；后续 SRT、人工审核或切片逻辑会把它当作真实时间轴。
- 现有产物影响：无。现有 full warm/cold 的 raw 均有 `sentence_info`，统一结果的 399 段均可回溯到原始句级毫秒边界。
- 修复验收建议：无时间戳时不得创建带确定起止时间的 segment；应明确失败或以不进入时间轴的结构保留文本，并新增对应回归测试。

### I-02｜电池供电复跑有三项指标越过建议波动线

| 候选 | 越线指标 | 报告值 | 本次值 | 相对变化 | 其他证据 |
|---|---|---:|---:|---:|---|
| SenseVoice | RTF | 0.024492 | 0.033453 | +36.6% | 输出 172 段逐字段一致；RSS +0.5% |
| Paraformer | RTF | 0.048272 | 0.068442 | +41.8% | 输出 399 段逐字段一致；RSS -2.3% |
| Faster-Whisper | 峰值 RSS | 655.27 MiB | 837.41 MiB | +27.8% | RTF +22.7%，仍在 ±25% 内；297 段/3033 words 一致 |

原报告采样的 `power_plugged=true`、电量 100%；本次三项复跑均为 `power_plugged=false`，电量约 95% 降至 89%。Paraformer 本次平均系统 CPU 50.92%，原暖跑为 39.14%。供电和背景负载与偏差同时出现，可合理解释部分波动，但本复核不把相关性写成已证明的单一因果。由于三候选全部完成、结果精确一致、速度仍远快于/接近实时且处于同一数量级，此项不构成性能造假或单独的不通过条件。

## 4. 一般建议

1. 为每个 ModelScope 模型保留下载时的官方 model ID、revision、文件清单、字节数、服务端摘要（若官方提供）和本地 SHA-256 清单。当前官方 revision 端点和主文件字节数可核对，但本地目录未保留 `.mv`/下载清单；不影响本次来源判定，却降低以后重建证据链的便利性。
2. `offline_network_guard()` 当前按指令拦截 `socket.socket.connect` 与 `socket.create_connection`；若后续把它作为通用“无网络”安全边界，应覆盖 `connect_ex`、UDP `sendto` 和 DNS，或配合系统级出站审计。当前源码没有 endpoint、上传逻辑或云端回退，三项离线探针也未触发连接。
3. 人工审核窗口的 RMS 计算使用 Python 3.12 已弃用的 `audioop`；本次仅产生一条弃用警告，Python 3.13 前应替换并保持窗口选择回归测试。
4. 后续性能报告应同时固定并记录供电状态、系统电源模式和背景 CPU；不要用电池与接电数据直接比较并给出过窄阈值。

## 5. Git 与任务边界

| 项目 | 开始与结束复核 |
|---|---|
| HEAD | `59c1d895a92d9b8319e04dd1d7fa933ef894c1a7` |
| branch | `master` |
| tag at HEAD | `baseline-task-001` |
| remote | 无 |
| 新 commit/tag/push | 无 |
| `src/liveclip` diff | 空；41 个正式源码文件未产生 Git 差异 |
| 正式 `timeline.json` | 未发现 |
| TASK-003 | 未执行 |

开始时工作区为：`.gitignore`、`docs/CURRENT_STATUS.md`、`docs/DECISIONS.md` 已修改；`docs/ASR_DEPENDENCY_PLAN.md`、`docs/ASR_MODEL_COMPARISON_REPORT.md`、`experiments/`、`tasks/TASK-002.md`、`tasks/reports/TASK-002_RESULT.md` 未跟踪。结束时这些既有状态未被本复核改变，只新增未跟踪的本报告。

`git ls-files --others --exclude-standard` 在写报告前仅列出 5 个 `.md`、17 个 `.py`、3 个 `.txt`，合计均为 TASK-002 文档、源码、测试和锁文件；最大文件 18,648 bytes。未发现媒体、模型、环境、缓存或其他二进制进入 Git 候选。

## 6. 输入和哈希

| 文件 | 字节数 | SHA-256 | 结果 |
|---|---:|---|---|
| `项目/ASR基准/input/benchmark.mp4` | 418,420,241 | `DA2CD4041C7FB59A1DFC08C80B0358C28DBBDC59608A469EB1A0A8AC63694BFF` | 与报告一致，复核前后不变 |
| `runtime/asr-benchmark/input/benchmark-16k-mono.wav` | 26,486,180 | `9625C4ED1A2A501DE580BB7713ABEC3F964B93EFFFE6AF3735F719964B4E0CEA` | 与报告一致，复核前后不变 |

`ffprobe`/WAV 头重算结果：PCM s16le、16,000 Hz、单声道、13,243,051 frames、`827.6906875` 秒（报告显示 `827.690688` 秒）。MP4 为 H.264 1080×1920 + AAC 48 kHz stereo，容器时长 `827.766313` 秒。

用项目本地 `tools/ffmpeg/bin/ffmpeg.exe` 直接把 MP4 音轨解码为 16 kHz、mono、PCM s16le，并通过 `-f hash` 只计算 PCM 数据哈希，得到 `6C31E913DFB52CAA7CC5D1CCFADDDE9C50D64E9D0C6FA56C9C38032023DF31BE`；读取统一 WAV 的 PCM frames 得到相同哈希。这证明统一 WAV 与项目本地 FFmpeg 的确定性提取结果在 PCM 层一致，且未写入新的媒体文件。

三个候选 cold/warm 的 `input_sha256` 均为统一 WAV 哈希；offline 均为同一个 30 秒 probe 哈希。项目中未发现 reference/gold/ground-truth SRT、TXT、VTT 或 JSON，因此没有运行 CER/WER。

## 7. 三候选来源、许可证和版本

### SenseVoice

- 运行时实测 `sherpa-onnx==1.13.4`，官方 PyPI 提供 Windows CPython 3.12 x64 wheel，运行时许可证为 Apache-2.0：[PyPI 1.13.4](https://pypi.org/project/sherpa-onnx/1.13.4/)。
- 模型为 sherpa-onnx 官方 `sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17`；官方说明它由 `iic/SenseVoiceSmall` 转换，并列出同名归档和文件：[官方预训练模型页](https://k2-fsa.github.io/sherpa/onnx/sense-voice/pretrained.html)。
- GitHub 官方 release API 返回归档字节数 `163,002,883`、digest `sha256:7d1efa...d347e`；本地归档字节数和 SHA-256 完全相同：[官方 ASR release](https://github.com/k2-fsa/sherpa-onnx/releases/tag/asr-models)。主权重 `model.int8.onnx` SHA-256 为 `C71F0CE00BEC95B07744E116345E33D8CBBE08CEF896382CF907BF4B51A2CD51`。
- 许可证披露没有把运行时代码许可证与模型权重许可证混淆：运行时为 Apache-2.0；本地模型 README 指向 FunASR 模型许可证。
- 不采用 GGUF 的理由属实：所核对的官方 `runtime-llamacpp-v0.1.7` SenseVoice README 把 `timestamps` 列在 Roadmap，而不是现成功能：[官方 GGUF README](https://github.com/modelscope/FunASR/tree/runtime-llamacpp-v0.1.7/runtime/llama.cpp/sensevoice)。本轮改用 sherpa-onnx + Silero VAD 获得真实 VAD 段边界是合理替代。

### Paraformer

- 实测 FunASR `1.3.22`；官方 tag 对应 commit `38e421467397671b828523bafd5582682599c5cf`，代码许可证为 MIT：[v1.3.22 tag](https://github.com/modelscope/FunASR/tree/v1.3.22)、[commit](https://github.com/modelscope/FunASR/commit/38e421467397671b828523bafd5582682599c5cf)。
- 三模型均为 ModelScope `iic` 官方条目、模型卡为 Apache-2.0：[`SeACo Paraformer`](https://modelscope.cn/models/iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch)、[`FSMN-VAD`](https://modelscope.cn/models/iic/speech_fsmn_vad_zh-cn-16k-common-pytorch)、[`CT-Punc`](https://modelscope.cn/models/iic/punc_ct-transformer_cn-en-common-vocab471067-large)。代码 MIT 与模型 Apache-2.0 在文档中已分开披露。
- 对官方只读 revision 文件端点执行 HEAD：Paraformer `v2.0.9` 返回 200、`989,763,045` bytes；FSMN `v2.0.4` 返回 200、`1,721,366` bytes；CT-Punc `v2.0.4` 返回 200、`1,125,507,622` bytes。三者与本地主权重字节数完全相同。主权重 SHA-256 依次为 `3D491689244EC5DFBF9170EF3827C358AA10F1F20E42A7C59E15E688647946D1`、`B3BE75BE477F0780277F3BAE0FE489F48718F585F3A6E45D7DD1FBB1A4255FC5`、`7176CAE922A872E130E6B88AEF9A1153581711BAF79C9124C7C95BE383CD6F81`。
- 实测 `torch==2.11.0+cpu`、`torchaudio==2.11.0+cpu`，`torch.version.cuda is None`、`torch.cuda.is_available()==False`；这是一组官方列出的 CPU 配对：[PyTorch previous versions](https://pytorch.org/get-started/previous-versions/)。环境无 `nvidia-*`、CUDA package 或 GPU wheel。
- 运行时传入三个 D 盘本地绝对目录，`device="cpu"`、`disable_update=True`，源码没有 `trust_remote_code=True`。FunASR 日志虽打印通用文案 `download models from model hub: ms`，随后明确加载 D 盘路径且没有 URL/网络错误；该文案本身不是网络请求证据。

### Faster-Whisper

- 实测 `faster-whisper==1.2.1`、`ctranslate2==4.8.1`；对应官方 release 存在：[faster-whisper v1.2.1](https://github.com/SYSTRAN/faster-whisper/releases/tag/v1.2.1)、[CTranslate2 v4.8.1](https://github.com/OpenNMT/CTranslate2/releases/tag/v4.8.1)。
- 模型为 `Systran/faster-whisper-small`，本地 cache 元数据逐文件记录 revision `536b0662742c02347bc0e980a01041f333bce120`；官方 revision 树存在且许可证为 MIT：[固定 revision](https://huggingface.co/Systran/faster-whisper-small/tree/536b0662742c02347bc0e980a01041f333bce120)。
- `model.bin` SHA-256 为 `3E305921506D8872816023E4C273E75D2419FB89B24DA97B4FE7BCE14170D671`，与本地 cache tree 元数据记录一致。
- 适配器固定 `device="cpu"`、`compute_type="int8"`；CTranslate2 报告 CUDA device count 为 0，环境无 NVIDIA/CUDA package。

### 锁定结果

| 环境 | `pip freeze --all` 行数 | lock 行数 | 有序逐行比较 | `pip check` |
|---|---:|---:|---|---|
| sherpa-onnx | 5 | 5 | 完全一致 | 通过 |
| funasr | 86 | 86 | 完全一致 | 通过 |
| faster-whisper | 27 | 27 | 完全一致 | 通过 |

## 8. 环境、模型和 D 盘隔离

- 三个虚拟环境的 `sys.prefix` 均在 `<PROJECT_ROOT>\runtime\asr-envs\...`；`base_prefix` 指向 C 盘系统 Python 只表示 venv 的解释器来源，不表示包、环境或模型安装到 C 盘。
- 模型均在 `<PROJECT_ROOT>\模型\asr\`；模型运行时/归档在 `tools/asr/`；缓存、临时结果和日志均在项目 `runtime/`。
- `.venv` 复核前后都是下列 12 行：`annotated-types==0.7.0`、`colorama==0.4.6`、`iniconfig==2.3.0`、`packaging==26.2`、`pip==25.0.1`、`pluggy==1.6.0`、`pydantic==2.13.4`、`pydantic_core==2.46.4`、`Pygments==2.20.0`、`pytest==8.4.2`、`typing-inspection==0.4.2`、`typing_extensions==4.16.0`。
- `requirements-dev.lock.txt` 与上述应用依赖逐行一致；唯一额外行是 `pip==25.0.1`，因为使用的是 `freeze --all`，而开发 lock 不锁 pip。该行复核前后相同，不是本任务污染。
- 系统 Python 的 ASR/ML 包筛选为空，`pip list --user` 为空；没有全局或 user 安装痕迹。
- 常见 C 盘目录 `~/.cache/huggingface`、`~/.cache/modelscope`、`~/.cache/torch`、`AppData/Local/modelscope`、`AppData/Roaming/modelscope` 均不存在，未发现明确属于 TASK-002 的 C 盘大型模型/缓存。

| 内容 | 大小 |
|---|---:|
| sherpa-onnx 环境 | 114.52 MiB |
| funasr 环境 | 1,223.73 MiB |
| faster-whisper 环境 | 277.28 MiB |
| SenseVoice 模型目录 | 229.98 MiB |
| Paraformer 模型目录 | 952.66 MiB |
| FSMN-VAD 模型目录 | 3.84 MiB |
| CT-Punc 模型目录 | 1,131.80 MiB |
| Faster-Whisper small 模型目录 | 463.69 MiB |
| `runtime/asr-cache` | 194.34 MiB |
| `runtime/cache/asr` | 342.44 MiB |
| 原结果目录 | 4.57 MiB |
| 本次临时审计产物 | 2.37 MiB |

复核结束时 D 盘可用约 598.45 GiB。模型缓存仅发现一个空的 `runtime/asr-cache/modelscope/.lock/` 目录；没有 `.incomplete`、`.partial`、`.part` 或残留临时模型文件。

## 9. 输出契约

对原 cold、warm、offline、smoke 的 raw JSON、统一 JSON、SRT、TXT、metrics、resource JSONL、静音产物和热词产物做了完整结构读取。原有成功结果均满足：

- JSON 数字有限；segment/word 时间有限、单调且不越界；`errors=[]`；
- SenseVoice 与 Paraformer 的 `words=[]`，没有伪造 word timestamp；Faster-Whisper 有 3,033 个可回溯的真实 word timestamp；
- 所有 `speaker` 均为 `null`，没有伪造说话人；
- SenseVoice raw 保留 `language`、`emotion`、`event`；通用 `Speech` 不被错误当作非语音事件写入 `events`，情绪字段保留；
- SRT 时间按毫秒四舍五入并与 JSON 一致；TXT 是统一 segment 文本逐行连接，没有额外改写；
- 每个统一 segment 均可回溯到对应 raw 记录；资源汇总值可由每一行 JSONL 重新计算；
- 候选由独立 adapter/独立环境/独立进程运行，orchestrator 对候选异常逐项隔离；
- 无参考字幕调用 CER/WER 会抛出 `ReferenceRequiredError`。

使用固定随机种子 `20260721`，每候选随机抽查 20 个 segment；抽样 ID 如下，全部通过 raw/JSON/SRT/TXT/边界一致性校验：

- SenseVoice：`seg-0002, 0025, 0033, 0045, 0048, 0054, 0062, 0071, 0097, 0100, 0102, 0104, 0114, 0120, 0143, 0149, 0154, 0155, 0157, 0163`。
- Paraformer：`seg-0005, 0007, 0043, 0083, 0088, 0089, 0097, 0137, 0147, 0171, 0189, 0204, 0216, 0252, 0267, 0271, 0299, 0306, 0308, 0355`。
- Faster-Whisper：`seg-0003, 0017, 0024, 0025, 0026, 0058, 0081, 0100, 0136, 0146, 0182, 0184, 0186, 0221, 0240, 0244, 0258, 0274, 0284, 0295`。

现有产物的输出契约正确；但实现层的 Paraformer 无时间戳回退违反“不伪造缺失字段”，详见 I-01。

## 10. 性能数据重算

重算定义：`RTF = full_transcription_seconds / 827.690688`；峰值 RSS、平均/峰值进程 CPU 直接从全部 0.5 秒 JSONL 采样重算；覆盖率为所有 segment `(end-start)` 之和除以音频时长。Windows 进程 CPU 百分比按逻辑核累加，因此四线程任务可高于 100%。

| 候选 | 跑次 | 加载 s | 全量推理 s | RTF | 峰值 RSS | 平均/峰值 CPU | segments | words | 语音覆盖 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SenseVoice | cold | 1.474495 | 19.942004 | 0.024093546 | 490.46 MiB | 310.58% / 412.5% | 172 | 0 | 693.404 s / 83.77574% |
| SenseVoice | warm | 1.590657 | 20.271782 | 0.024491977 | 490.44 MiB | 321.17% / 412.5% | 172 | 0 | 693.404 s / 83.77574% |
| Paraformer | cold | 17.737480 | 39.577581 | 0.047816873 | 5.973 GiB | 310.48% / 412.5% | 399 | 0 | 696.750 s / 84.18000% |
| Paraformer | warm | 17.822387 | 39.954317 | 0.048272039 | 5.979 GiB | 310.77% / 412.5% | 399 | 0 | 696.750 s / 84.18000% |
| Faster-Whisper | cold | 1.062515 | 188.372781 | 0.227588377 | 995.91 MiB | 386.48% / 415.6% | 297 | 3,033 | 709.490 s / 85.71922% |
| Faster-Whisper | warm | 0.829679 | 185.203767 | 0.223759636 | 655.27 MiB | 388.14% / 415.6% | 297 | 3,033 | 709.490 s / 85.71922% |

全部重算值与 `ASR_MODEL_COMPARISON_REPORT.md`、`TASK-002_RESULT.md` 一致，差异仅为显示舍入。原报告没有把外层进程退出时间混入 RTF。

## 11. 三候选独立复跑

临时结果：`runtime/temp/asr/TASK-002-R-20260721-192810/`。按 SenseVoice → 等待 20 秒 → Paraformer → 等待 20 秒 → Faster-Whisper 严格串行；每个进程使用同一 WAV、CPU、4 线程、Below Normal、`CUDA_VISIBLE_DEVICES=-1`，并开启 HF/Transformers/ModelScope 离线变量。未并行运行模型，也未修改电源计划。

| 候选 | 加载 s | 全量推理 s | 本次 RTF | 相对报告 | 本次峰值 RSS | 相对报告 | 输出 | 静音 |
|---|---:|---:|---:|---:|---:|---:|---|---|
| SenseVoice | 1.709674 | 27.688397 | 0.033452590 | +36.6% | 492.77 MiB | +0.5% | 172 段，与原暖跑逐字段一致 | 0 段 |
| Paraformer | 25.608070 | 56.648904 | 0.068442118 | +41.8% | 5.841 GiB | -2.3% | 399 段，与原暖跑逐字段一致 | 0 段 |
| Faster-Whisper | 1.052794 | 227.316132 | 0.274638986 | +22.7% | 837.41 MiB | +27.8% | 297 段/3,033 words，与原暖跑逐字段一致 | 0 段 |

三候选都成功、输出非空、`errors=[]`、时间轴有效、静音无幻觉；满足“至少两个候选完整复跑成功”。本次性能偏差按 I-02 保留，不用额外重跑覆盖。

## 12. 离线与无上传

同一临时审计目录下对每候选运行 30 秒 probe；模型加载和转写均处于 `offline_network_guard`，模型为 D 盘绝对路径。

| 候选 | 进程退出 | 加载 s | 30 秒 probe s | segments | `errors` | socket guard |
|---|---:|---:|---:|---:|---:|---|
| SenseVoice | 0 | 2.023544 | 3.649300 | 5 | 0 | 已启用 |
| Paraformer | 0 | 24.824756 | 3.039715 | 18 | 0 | 已启用 |
| Faster-Whisper | 0 | 1.514386 | 6.128260 | 4 | 0 | 已启用 |

源码检索只发现离线 guard 的 `socket` 使用和 `benchmark.py` 主动移除 API token 环境变量；未发现 HTTP endpoint、上传函数、OpenAI/Azure SDK、收费服务、失败时云端回退或实际密钥。六份本次 adapter 日志均无 URL、Traceback 或失败；Paraformer 日志明确列出本地 D 盘模型路径和 `trust_remote_code: False`。因此在本代码路径和本次动态探针范围内，没有上传或云端 ASR 证据。

## 13. 静音和稳定性

- 原 warm：三候选 20 秒静音均为 0 segment、空文本、`hallucination_detected=false`。
- 本次 warm：三候选再次均为 0 segment、空文本、`hallucination_detected=false`。
- 原 cold 与 warm 的规范化 segment 内容对每个候选完全一致；本次 warm segment 又与原 warm 完全一致。
- 原 cold/warm/offline/smoke 及本次 offline/warm 的成功统一结果均为 `errors=[]`。
- 本次离线 probe 分别输出 5/18/4 个非空 segment，时间边界有效。

稳定性和静音要求通过。

## 14. 人工审核包

| 文件 | 字节数 | SHA-256 |
|---|---:|---|
| `项目/ASR基准/output/人工审核对比.csv` | 22,253 | `3A31CEA90B97BBF7DFF032627E0B344A26EF09490964D3E37F7CE78ECED7421B` |
| `项目/ASR基准/output/人工审核对比.md` | 24,407 | `4077FFE5834902B9B6B28F45DA0CE8CF3F28E0A12BCB3EE92292E2D71E2EE504` |

- CSV 为 8 列、20 个数据窗口，无空单元格；窗口编号 1—20。
- Markdown 有 20 个二级窗口标题和 60 个三级候选标题。
- CSV 的窗口、时间、标签、分歧分和三候选文本可由三个原 warm `unified.json` 使用 `build_windows()` 在内存中完全重建；Markdown 与 CSV 的全部窗口编号、时间和候选名一致。
- 覆盖开头/前段/中间/后段/结尾、5 个高分歧窗口、2 个英文/中英检查窗口、2 个笑声/掌声人工检查窗口、低音量、高能量/噪声、短句、长句和 2 个均匀补充窗口。
- “候选分歧分”是文本相似度差异，不被表述为正确率；文件首部明确写明准确率待人工审核。
- 未根据文本语义宣布哪个候选真实正确；不自然词只能在后续对照原音频时判断。

人工审核包通过。

## 15. 测试与回归

| 检查 | 通过 | 失败 | 跳过 | 关键耗时/结果 |
|---|---:|---:|---:|---|
| `tools/Run-Tests.ps1 -ra --durations=10` | 148 | 0 | 0 | pytest 36.69 s；完整脚本 38.8 s；随后 `pip check` 通过 |
| `tools/Validate-Media.ps1` | 18 | 0 | 0 | 完整脚本 9.6 s；能力检查、合成媒体链路、A/V sync 与集成测试通过 |
| 基础 `.venv` 独立 `pip check` | 1 | 0 | 0 | `No broken requirements found.` |
| `experiments/asr/tests` | 12 | 0 | 0 | pytest 0.10 s；完整脚本 2.7 s；1 条 `audioop` 弃用警告 |
| 三个 ASR 环境 `pip check` | 3 | 0 | 0 | 全部 `No broken requirements found.` |
| 三个 ASR lock 有序逐行比较 | 3 | 0 | 0 | 5/86/27 行全部一致 |

基础项目、媒体链路和实验测试无回归。

## 16. 文档一致性

`TASK-002_RESULT.md`、`ASR_MODEL_COMPARISON_REPORT.md`、`ASR_DEPENDENCY_PLAN.md`、`CURRENT_STATUS.md`、`DECISIONS.md` 与既有 metrics/文件在以下方面一致：

- 明确不存在参考字幕，没有 CER/WER 或准确率总排名；
- SenseVoice 只是低资源暂定候选；
- Paraformer 只是待人工验证的中文准确率挑战者；
- Faster-Whisper 只是词级时间戳/多语言备用；
- CAM++ 因没有足够客观证据确认明显多说话人而未下载，文档没有把自动人数当真值；
- SenseVoice 的情绪/事件只作模型输出观察，文档明确不当作真值；
- 未执行 TASK-003，未生成正式 timeline。

文档中的原性能表、文件路径和模型角色均与现状一致。唯一实质性矛盾是文档称统一输出“不伪造缺失字段”，而 Paraformer 的异常回退路径仍会伪造全长时间范围；现有正常结果不受影响，但需由 TASK-002-FIX 消除。

## 17. 安全边界

| 检查项 | 结果 |
|---|---|
| 上传样本或结果 | 未发现代码、日志或动态探针证据 |
| 云端 ASR / 收费 API | 未发现 endpoint、SDK 或回退 |
| API Key | 未发现实际密钥；orchestrator 主动移除常见 token 变量 |
| CUDA/NVIDIA/GPU PyTorch | 无；FunASR 为 `+cpu`，CUDA 不可用 |
| 基础 `.venv` 污染 | 无；复核前后包清单一致 |
| 大型内容位置 | 环境、模型、缓存、样本、结果均在 D 盘 |
| Git ignore | MP4、审核输出、runtime WAV/环境/缓存、模型、`tools/asr` 均经 `git check-ignore -v` 命中 |
| 原 MP4/WAV/模型变化 | 关键哈希复核前后相同 |
| commit/remote/push | 无 |
| TASK-003 / 正式源码 | 未执行；`src/liveclip` 无 diff |

本复核没有下载或更新模型/依赖，没有上传音视频/字幕/结果，没有调用云端 ASR、收费 API 或 OpenAI API，没有修改系统 PATH、电源计划、实验代码、文档、模型、环境或既有结果。

## 18. 文件哈希变化

以下关键哈希在复核开始和结束一致：

| 对象 | 开始 SHA-256 | 结束 SHA-256 | 变化 |
|---|---|---|---|
| 原 MP4 | `DA2CD404...63694BFF` | `DA2CD404...63694BFF` | 无 |
| 统一 WAV | `9625C4ED...B4E0CEA` | `9625C4ED...B4E0CEA` | 无 |
| SenseVoice 主权重 | `C71F0CE0...51A2CD51` | `C71F0CE0...51A2CD51` | 无 |
| Paraformer 主权重 | `3D491689...647946D1` | `3D491689...647946D1` | 无 |
| FSMN-VAD 主权重 | `B3BE75BE...1A4255FC5` | `B3BE75BE...1A4255FC5` | 无 |
| CT-Punc 主权重 | `7176CAE9...83CD6F81` | `7176CAE9...83CD6F81` | 无 |
| Faster-Whisper 主权重 | `3E305921...14170D671` | `3E305921...14170D671` | 无 |
| SenseVoice 发布归档 | `7D1EFA21...83DFD347E` | `7D1EFA21...83DFD347E` | 无 |
| Silero VAD | `9E2449E1...09CBB1FD6` | `9E2449E1...09CBB1FD6` | 无 |
| FFmpeg 安装标记 | `7D624C12...EE1EC2353` | `7D624C12...EE1EC2353` | 无 |
| ffmpeg.exe | `AD8F211B...247B5942E` | `AD8F211B...247B5942E` | 无 |
| ffprobe.exe | `9DF3B0B5...084A55015` | `9DF3B0B5...084A55015` | 无 |

Machine PATH 开始/结束哈希均为 `015EE9C6...6A5030B8`，User PATH 均为 `3DD925D5...C5E30E98`，两者无变化。Process PATH 在恢复后的 Codex Desktop 会话中发生变化：临时 `codex-arg0...` 目录及 Codex 应用版本目录从旧会话项切换为当前会话项；这是每次工具进程注入的会话级路径，Machine/User PATH 均未变化，本复核也没有执行 PATH 写入。

基础 `.venv` 的 12 行 freeze 清单前后完全一致；三个 ASR 环境与各自 lock 的 5/86/27 行在结束时仍逐行一致。Git HEAD、branch、tag、remote 和既有工作区状态未变；正式写入只新增 `tasks/reports/TASK-002-R_AUDIT.md`，另有允许保留的 `runtime/temp/asr/TASK-002-R-20260721-192810/` 复核产物。

## 19. 最终建议

**需要 TASK-002-FIX**

FIX 范围应只处理 Paraformer 无时间戳回退的伪造范围，并增加回归测试；同时在接电、相同背景负载下复核性能波动说明。完成独立修复复核前，不把 TASK-002 标记为技术实验通过；仍不得执行 TASK-003，也不得根据当前文本直接给出准确率排名。
