# TASK-002｜本地字幕识别模型对比报告

- 执行日期：2026-07-20（Asia/Shanghai）
- 项目：`<PROJECT_ROOT>`
- Git 基线：`master` / `59c1d895a92d9b8319e04dd1d7fa933ef894c1a7` / `baseline-task-001`
- 实验范围：仅 Windows 本地 CPU ASR 模型对比；未执行 TASK-003

## 1. 结论先行

三条路线均完成冷跑、热跑、20 秒静音和断网守卫短探针，并且冷/热均成功覆盖完整 827.691 秒统一 WAV。技术结论如下：

1. **低资源暂定首选：SenseVoiceSmall（sherpa-onnx INT8）**。热跑 RTF 0.0245，峰值 RSS 490 MiB，环境加模型约 345 MiB；速度和资源占用最好，并保留情绪标签。代价是时间戳只有 VAD 语音片段边界，没有字/词级时间戳。
2. **中文生产准确率候选：Paraformer + FSMN-VAD + CT-Punc**。热跑 RTF 0.0483，句级时间戳和中文标点完整，支持热词；但峰值 RSS 约 5.98 GiB，环境加模型约 3.23 GiB。本轮无人工参考，只有人工审核后才能判断其中文准确率收益是否足以抵消资源成本。
3. **词级时间戳备用：Faster-Whisper small CPU int8**。提供 3,033 个词级时间戳，热加载最快（0.830 秒），热跑峰值 RSS 655 MiB；但热跑 RTF 0.2238，是 SenseVoice 的约 9.1 倍、Paraformer 的约 4.6 倍，并且本样本输出未带标点。

> 准确率排名待人工审核，当前只比较技术性能、输出完整性和候选分歧。

因此本报告不计算 CER/WER、不提供准确率总排名，也不宣布最终生产模型。当前工程建议是先用 SenseVoiceSmall 作为低资源默认候选，同时完成人工审核；若 Paraformer 在真实直播文字准确率、漏句和标点上有明显优势，再考虑以其作为中文生产基线。需要细粒度词时间戳或更广语言覆盖时保留 Faster-Whisper。

## 2. 样本与统一输入

参考字幕 `reference.srt` / `reference.txt` 均不存在。

| 项目 | 值 |
|---|---|
| 原始样本 | `项目\ASR基准\input\benchmark.mp4` |
| 原始大小 | 418,420,241 bytes |
| 原始 SHA-256 | `DA2CD4041C7FB59A1DFC08C80B0358C28DBBDC59608A469EB1A0A8AC63694BFF` |
| 原始时长/流 | 827.766313 秒；AAC 48 kHz 双声道；H.264 1080×1920 |
| 统一 WAV | `runtime\asr-benchmark\input\benchmark-16k-mono.wav` |
| WAV 规格 | PCM s16le、16 kHz、单声道、827.690688 秒、26,486,180 bytes |
| WAV SHA-256 | `9625C4ED1A2A501DE580BB7713ABEC3F964B93EFFFE6AF3735F719964B4E0CEA` |
| 30 秒探针 SHA-256 | `756E854A01DD7786D5D8702E35DBEE6265EF6EAAE8DA241FF630EA59BBF9EDBF` |
| 20 秒静音 SHA-256 | `F2C955578877C05BEA043B1561D21FF3D529EC82BFE46F98E6516B0E0383BB38` |

原始 MP4 在实验前后哈希一致，没有修改或删除。三候选使用同一个 WAV，候选及其冷/热运行均不并行。

## 3. 机器、执行生命周期与计量口径

- Windows 11 家庭版中文版 10.0.26200；AMD Ryzen 7 8845HS，8 核 16 线程；物理内存约 23.29 GiB。
- Python 3.12.10；项目 FFmpeg/ffprobe 8.1.2。
- 统一限制：CPU、4 线程、Below Normal；每 0.5 秒采样一次资源；执行期间接通电源。
- 每候选生命周期：新进程加载 → 30 秒预热 → 完整冷跑 → 退出 → 等待 25 秒 → 新进程加载 → 完整热跑 → 20 秒静音 → 可选固定探针 → 退出 → 新进程断网守卫 30 秒复测。
- “热跑”指第二个全新进程在 OS 文件缓存可能已热的情况下运行，不表示模型常驻内存。
- CPU 百分比按进程跨逻辑核累计，因此四线程工作负载可超过 100%。
- 时间覆盖率是有效语音时间段合并长度除以音频时长，是 VAD/分段覆盖证据，不是文字准确率。

## 4. 来源、许可证、版本、revision 与哈希

| 候选/组件 | 官方来源与许可证 | 固定版本/revision | 关键本地 SHA-256 |
|---|---|---|---|
| SenseVoice 运行时 | `k2-fsa/sherpa-onnx`，Apache-2.0 | `sherpa-onnx==1.13.4` | wheel 版本由锁文件固定 |
| SenseVoice INT8 模型 | sherpa-onnx 官方 ASR release；权重许可按归档内指向的 FunASR Model License | `2024-07-17-int8` | `model.int8.onnx`: `C71F0CE00BEC95B07744E116345E33D8CBBE08CEF896382CF907BF4B51A2CD51` |
| SenseVoice 发布归档 | `k2-fsa/sherpa-onnx/releases/download/asr-models/...tar.bz2` | `2024-07-17` | `7D1EFA2138A65B0B488DF37F8B89E3D91A60676E416F515B952358D83DFD347E`；与发布方 digest 一致 |
| Silero VAD | sherpa-onnx 官方 ASR release | release asset | `9E2449E1087496D8D4CABA907F23E0BD3F78D91FA552479BB9C23AC09CBB1FD6`；与发布方 digest 一致 |
| FunASR 运行时 | `modelscope/FunASR`，代码 MIT | `funasr==1.3.22`；tag commit `38e421b0c49963a6f46ae2ebbaa24bc5168cc707` | 依赖见实际锁文件 |
| SeACo Paraformer | ModelScope `iic` 官方模型卡，Apache-2.0 | `v2.0.9` | `model.pt`: `3D491689244EC5DFBF9170EF3827C358AA10F1F20E42A7C59E15E688647946D1` |
| FSMN-VAD | ModelScope `iic` 官方模型卡，Apache-2.0 | `v2.0.4` | `model.pt`: `B3BE75BE477F0780277F3BAE0FE489F48718F585F3A6E45D7DD1FBB1A4255FC5` |
| CT-Punc | ModelScope `iic` 官方模型卡，Apache-2.0 | `v2.0.4` | `model.pt`: `7176CAE922A872E130E6B88AEF9A1153581711BAF79C9124C7C95BE383CD6F81` |
| Faster-Whisper 运行时 | `SYSTRAN/faster-whisper`，MIT | `faster-whisper==1.2.1`；`ctranslate2==4.8.1` | 依赖见实际锁文件 |
| Faster-Whisper small | `Systran/faster-whisper-small`，MIT | commit `536b0662742c02347bc0e980a01041f333bce120` | `model.bin`: `3E305921506D8872816023E4C273E75D2419FB89B24DA97B4FE7BCE14170D671`；与发布方 LFS SHA 一致 |

主要来源：

- `https://github.com/k2-fsa/sherpa-onnx` 与 `https://k2-fsa.github.io/sherpa/onnx/sense-voice/pretrained.html`
- `https://github.com/modelscope/FunASR/tree/v1.3.22`
- `https://modelscope.cn/models/iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch`
- `https://modelscope.cn/models/iic/speech_fsmn_vad_zh-cn-16k-common-pytorch`
- `https://modelscope.cn/models/iic/punc_ct-transformer_cn-en-common-vocab471067-large`
- `https://github.com/SYSTRAN/faster-whisper` 与 `https://huggingface.co/Systran/faster-whisper-small/tree/536b0662742c02347bc0e980a01041f333bce120`

官方 GGUF 路线没有下载：FunASR `runtime-llamacpp-v0.1.7` 的 SenseVoice README 把 timestamps 列为 Roadmap，不能满足最低时间轴要求，故按任务允许的替代条件使用 sherpa-onnx INT8。

## 5. 模型、环境与缓存大小

| 候选 | 独立环境 | 模型 | 环境+模型 |
|---|---:|---:|---:|
| SenseVoice | 114.52 MiB | 229.98 MiB | 344.50 MiB |
| Paraformer + VAD + Punc | 1,223.73 MiB | 2,088.30 MiB | 3,312.03 MiB（3.23 GiB） |
| Faster-Whisper | 277.28 MiB | 463.69 MiB | 740.97 MiB |

附加 D 盘缓存：`runtime\asr-cache` 194.34 MiB，`runtime\cache\asr` 342.44 MiB。完整运行结果约 4.57 MiB，人工审核包约 45.57 KiB。以上均在 D 盘；结束时 D 盘仍有约 600.03 GiB 可用。

## 6. 冷/热速度、RTF、CPU 与内存

| 候选 | 冷加载 s | 冷全长 s | 冷 RTF | 热加载 s | 热全长 s | 热 RTF |
|---|---:|---:|---:|---:|---:|---:|
| SenseVoice | 1.474 | 19.942 | 0.02409 | 1.591 | 20.272 | 0.02449 |
| Paraformer | 17.737 | 39.578 | 0.04782 | 17.822 | 39.954 | 0.04827 |
| Faster-Whisper | 1.063 | 188.373 | 0.22759 | 0.830 | 185.204 | 0.22376 |

| 候选 | 冷平均/峰值 CPU | 热平均/峰值 CPU | 冷峰值 RSS | 热峰值 RSS |
|---|---:|---:|---:|---:|
| SenseVoice | 310.6% / 412.5% | 321.2% / 412.5% | 490.46 MiB | 490.44 MiB |
| Paraformer | 310.5% / 412.5% | 310.8% / 412.5% | 5.973 GiB | 5.979 GiB |
| Faster-Whisper | 386.5% / 415.6% | 388.1% / 415.6% | 995.91 MiB | 655.27 MiB |

全部 RTF < 1，均快于实时。SenseVoice 最快且最轻；Paraformer 速度仍适合离线处理，但 6 GiB 级峰值内存对低配笔记本不友好；Faster-Whisper 内存可接受但吞吐显著更慢。

TASK-002 原实验在接通电源时执行；TASK-002-R 独立复跑在电池供电时执行。复跑中 SenseVoice RTF 约增加 36.6%，Paraformer RTF 约增加 41.8%，Faster-Whisper 峰值 RSS 约增加 27.8%；三候选仍完成全长转写，且输出与原暖跑逐字段一致。供电状态与背景 CPU 负载同时变化，因此这些波动不能解释为单一确定因果，也不覆盖上表原始数据。后续横向性能比较必须固定并记录电源状态、Windows 电源模式、背景 CPU 负载、线程数、候选顺序和候选间冷却时间。

## 7. 输出、时间戳和分段能力

| 候选 | 热跑字符数 | segment | 有效 segment 时间戳 | word 时间戳 | 合并语音覆盖 | 首末时间 | 冷/热一致 |
|---|---:|---:|---:|---:|---:|---|---|
| SenseVoice | 4,279 | 172 | 172/172（100%） | 0 | 693.404 s / 83.776% | 1.062–826.694 s | 完全一致 |
| Paraformer | 4,288 | 399 | 399/399（100%） | 0 | 696.750 s / 84.180% | 0.110–827.660 s | 完全一致 |
| Faster-Whisper | 3,811 | 297 | 297/297（100%） | 3,033（100%） | 709.490 s / 85.719% | 0.000–826.360 s | 完全一致 |

- SenseVoice 时间边界来自 Silero VAD 的语音片段，适合字幕片段但不适合逐词精确对齐。
- Paraformer 使用 `sentence_info` 句级边界，粒度最细到句，不伪造 word 时间戳。
- Faster-Whisper 提供真实词级时间戳，是后续精细切片/字幕高亮最有利的路线。
- 三候选统一 JSON 都通过有限数、单调、边界和非空结果校验；每个成功运行都有 raw JSON、统一 JSON、SRT、TXT、metrics 与 0.5 秒资源样本。

### TASK-002-FIX 输出契约修复

TASK-002-R 发现 Paraformer 的异常回退会在文本非空但 `sentence_info` 与 `timestamp` 均不可用时伪造 `0—完整音频时长`。TASK-002-FIX 已移除该行为，并覆盖单项时间有效性及顶层 `timestamp` 数组内部单调性；缺失或异常时间字段以包含数量、raw 索引和原因的结构化 warning/error 保留，原始文本继续存在 raw JSON 中。此前“全部非单调已覆盖”的表述过宽：FIX-R 以 79/100 判定不通过，因为 sentence_info 条目之间及多个 raw item 之间的来源顺序仍可被公共层静默排序。

若全部文本均无可用时间轴，结果标记 `timeline_status=unavailable`，候选失败且不生成正常 SRT；若仅部分缺失，则只输出有真实时间证据的 segment，并标记 `timeline_status=partial`，不会静默丢弃异常索引。既有 Paraformer cold/warm raw 都含 399 条真实 `sentence_info`；修复后重建的 399 个 segment、start/end、text、SRT、TXT、segment 数和 696.75 秒语音覆盖率与原产物逐字节一致，原 warm unified SHA-256 仍为 `9D1593D19481E48E987A70A5642B323C55AE07698354BB4CACCD155605294EE1`。现有人工审核窗口文本不受影响。

### TASK-002-FIX2 来源顺序修复

FIX2 在 Paraformer 适配器进入公共层前，对 sentence_info 和跨 raw 的原始出现顺序统一校验：当前 `start`、`end` 均不得早于上一个已接受有效段。非单调条目使用 `PARAFORMER_TIMESTAMP_INVALID` / `timestamp_non_monotonic` 排除，issue 保留 raw/sentence 索引、当前/前序秒值和 `raw_text_preserved=true`；排除后续条目仍与上一个已接受段比较。部分有效结果只发布真实段并标记 `partial`，全部不可用结果保持既有失败/SRT 抑制语义，正常空结果不误报。

FIX2 的 ASR 实验测试为 37 passed，新增 sentence_info 倒序、end 回退、跨 raw 倒序、异常后恢复、全不可用和正常空结果覆盖。既有 cold/warm 399 段、4,288 字符、696.75 秒覆盖及 unified/SRT/TXT 逐字节不变；30 秒本地离线探针仍为 18 段，20 秒静音仍为 0 段，两次 socket guard 均通过。人工准确率仍待审核，本修复不改变候选角色或最终生产选型状态。

## 8. 静音、离线与输出稳定性

| 候选 | 20 秒静音 | 离线本地加载 | 30 秒断网探针 | 最终错误数组 |
|---|---|---|---|---|
| SenseVoice | 0 segment，无幻觉 | 成功 | 成功；socket 连接被守卫禁止 | 空 |
| Paraformer | 0 segment，无幻觉 | 成功 | 成功；socket 连接被守卫禁止 | 空 |
| Faster-Whisper | 0 segment，无幻觉 | 成功 | 成功；socket 连接被守卫禁止 | 空 |

推理进程同时设置 `HF_HUB_OFFLINE=1`、`TRANSFORMERS_OFFLINE=1`、`MODELSCOPE_OFFLINE=1`，所有模型以 D 盘绝对路径加载。断网复测进一步猴补丁拦截 socket connect；三候选均未尝试回退网络。

## 9. 中文、中英混合、标点、热词和事件

| 候选 | 英文/混合观察 | 标点数量 | 事件/情绪 | 热词 |
|---|---|---:|---|---|
| SenseVoice | 保留 `hello`，另有 `the.`；需人工确认 | 431 | 172 段均标记 Speech；情绪：Neutral 93、Angry 40、Happy 27、Unknown 11、Surprised 1 | 不支持本轮热词接口 |
| Paraformer | 保留 `hello`；需人工确认 | 399 | 无事件/情绪输出 | 固定词 `直播 智能切片 人工智能 AI` 仅运行一次 |
| Faster-Whisper | 输出 `emc`；是否为正确英文待人工确认 | 0 | 无事件/情绪输出 | 本轮不提供热词 |

Paraformer 热词探针与无热词 30 秒基线在去除标点后完全一致，四个热词均未出现在该 30 秒音频输出中。因此只能确认热词调用路径可执行，不能据此证明热词召回改善。SenseVoice 没有输出 Laugh/Applause 等非语音事件，只有 Speech；人工审核包保留两个人工检查窗口，不把情绪标签或自动事件当真值。

## 10. 说话人探针

未下载 CAM++、未运行说话人探针。现有自动转写包含对话语气，但没有足够客观证据确认音频中存在清晰的两个以上真实说话人；按任务规则，只有样本明显多说话人时才运行该可选探针。此跳过不算失败，也不把自动人数当真值。Faster-Whisper 如后续需要 diarization，仍需独立方案。

## 11. 人工审核与准确率状态

因为没有参考字幕：

- 未计算 CER/WER，也没有伪造插入、删除、替换、漏句或重复统计；
- 已生成 `项目\ASR基准\output\人工审核对比.md` 与 `.csv`；
- 两个文件均有恰好 20 个并排窗口，覆盖开头/中间/结尾、长短句、英文、低音量、噪声、笑声/掌声人工检查和候选分歧高点；
- 归一化全文候选相似度仅作为“候选分歧”定位信号：SenseVoice–Paraformer 0.9509，SenseVoice–Faster-Whisper 0.9146，Paraformer–Faster-Whisper 0.9053，不代表准确率。

> 准确率排名待人工审核，当前只比较技术性能、输出完整性和候选分歧。

人工审核至少需要逐窗口标记：正确字词、漏句、重复、专名/英文、标点、切点是否自然、噪声与笑声/掌声是否误转写。完成后才可补录参考字幕并计算 CER/WER。

## 12. 无参考技术评分

评分只比较技术实现，不合计总分，不是准确率排名。

| 候选 | 技术性能 /10 | 时间戳 /10 | 资源 /10 | 功能完整性 /10 | 人工准确率 |
|---|---:|---:|---:|---:|---|
| SenseVoice | 9.5 | 7.5 | 10.0 | 7.0 | 待审核 |
| Paraformer | 7.5 | 8.5 | 4.5 | 6.0 | 待审核 |
| Faster-Whisper | 6.0 | 10.0 | 9.0 | 6.0 | 待审核 |

评分口径：技术性能看热 RTF、热加载、离线/稳定；时间戳看粒度、有效性和语音区间覆盖；资源看热峰值 RSS、环境+模型磁盘、CPU；功能完整性看标点、词时间戳、中英/多语种、VAD/静音、事件/情绪和热词。阈值与计算依据都来自本报告表格，未加入文本准确率。

## 13. 候选优缺点与暂定推荐

### SenseVoiceSmall / sherpa-onnx INT8

- 优点：最快、内存和磁盘最小；情绪标签丰富；静音和离线稳定；适合笔记本持续批处理。
- 缺点：只有 VAD 段级边界；不提供 word 时间戳；sherpa 转换路线不是首选 GGUF；情绪/事件需人工核验。
- 暂定角色：低资源默认候选，等待人工准确率审核后决定是否进入正式架构。

### Paraformer + FSMN-VAD + CT-Punc

- 优点：中文专用组合；句级时间轴、中文标点与热词接口完整；速度仍快于实时。
- 缺点：加载约 18 秒，峰值内存约 6 GiB，磁盘约 3.23 GiB；本轮热词音频未包含固定词，未证明增益；没有 word 时间戳。
- 暂定角色：中文准确率挑战者。只有人工审核显示明显收益时才值得承担资源成本。

### Faster-Whisper small CPU int8

- 优点：唯一提供完整词级时间戳；热加载最快；内存适中；多语言覆盖广。
- 缺点：热 RTF 最慢；本样本输出无标点；没有事件/情绪和本轮热词能力。
- 暂定角色：词级对齐与国际化备用路线。

## 14. 错误、警告与未完成项

已解决的实施问题：

- 首次 SenseVoice 冒烟暴露 sherpa Python 包未声明 NumPy，补装并锁定 `numpy==2.3.5`；之后通过。
- SenseVoice VAD 冒烟发现读取 `pop()` 后对象生命周期错误，改为弹出前复制音频片段并增加验证；最终全长结果稳定。
- FunASR 首次导入缺少 `torchaudio`；由于 PyPI 无 Windows `torchaudio==2.13.0`，改为匹配的 CPU `torch/torchaudio==2.11.0+cpu`。最终 CUDA 检查和完整运行通过。
- ModelScope 标点大权重下载的外层进程曾无输出；安全检查阻止删除非空 partial，底层官方进程完成后目录无 `.incomplete`，主权重哈希已记录。

剩余限制：

- 准确率、漏句、重复、专名和标点质量待人工审核；CER/WER 未完成是因为没有参考字幕，不是执行失败。
- TASK-002-FIX/FIX2 只修复 Paraformer 时间戳与来源顺序契约；人工准确率审核仍未完成，不据此宣布最终生产模型。
- CAM++ 说话人探针因“明显多说话人”前提未被证实而跳过。
- `audioop` 在 Python 3.12 可用但提示 Python 3.13 将移除；未来升级 Python 前应替换人工窗口 RMS 计算实现。
- FunASR 日志提示系统 PATH 中没有 ffmpeg，随后明确使用 torchaudio 成功加载统一 WAV；项目 FFmpeg 未加入 PATH，这是隔离策略，不影响结果。
- 本任务只完成技术验证，不生成正式 `timeline.json`，不做 UI，也不执行 TASK-003。

## 15. 修改文件

- 实验实现：`experiments\asr\README.md`、`benchmark.py`、`common.py`、`metrics.py`、`normalize.py`、`resource_monitor.py`、`review.py`、三个 adapter 与包初始化文件。
- 测试：`experiments\asr\tests\test_common.py`、`test_metrics.py`、`test_benchmark.py`、`test_review.py`。
- 锁文件：`experiments\asr\locks\sherpa-onnx.lock.txt`、`funasr.lock.txt`、`faster-whisper.lock.txt`。
- 文档：`docs\ASR_DEPENDENCY_PLAN.md`、本报告、`docs\CURRENT_STATUS.md`、`docs\DECISIONS.md`、`tasks\TASK-002.md`、`tasks\reports\TASK-002_RESULT.md`。
- Git 忽略：`.gitignore` 增加 `tools/asr/`；既有规则已忽略 runtime、模型、基准 input/output 和大文件。
- 运行产物（未跟踪）：`runtime\asr-*`、`runtime\cache\asr`、`runtime\logs\asr`、`tools\asr`、`模型\asr`、`项目\ASR基准\output`。
- 未修改正式 `src/liveclip`。

## 16. 测试结果

- 实验测试：12 passed；覆盖统一输出校验、有限/单调/边界时间、CER/WER、混合归一化、SRT、无参考禁止准确率、静音、候选失败隔离及 20 窗口类别完整性。
- 基础回归：148 passed、0 failed、0 skipped，25.92 秒；基础 `.venv` `pip check` 通过。
- 媒体验证：能力探针、合成端到端媒体流程、17 个同步单元测试和 1 个 FFmpeg 集成测试全部通过（18 passed）；`TRIM_VALID=True`、`BURN_VALID=True`。
- 三个 ASR 环境：`pip check` 均通过；实际 `pip freeze --all` 与三份锁文件逐行一致。
- CUDA 核验：三个环境均无名称包含 CUDA/NVIDIA 的包；FunASR `torch 2.11.0+cpu`、`torch.version.cuda=None`、`cuda_available=False`；CTranslate2 CUDA 设备数 0。

## 17. 安全边界确认

- 样本、提取音频、字幕和识别结果未上传；仅下载公开依赖和官方模型。
- 未调用云端 ASR、收费 API 或 OpenAI API；未写入 API Key。
- 所有环境、模型、缓存、临时文件、日志和结果都在 D 盘项目目录。
- 基础 `.venv` 包清单与任务前一致，未安装任何 ASR/ML 依赖。
- 未安装 CUDA、GPU PyTorch、NVIDIA 包或 CUDA toolkit。
- 原始 MP4 未修改/删除；前后 SHA-256 一致。
- 模型、环境、缓存、样本和结果均被 Git 忽略；无 staged 文件。
- 未创建 remote、commit 或 push；HEAD 仍为基线提交。
- 未执行 TASK-003，未生成正式 `timeline.json`。

## 18. 回滚方法

如用户以后明确要求回滚，先重新确认绝对路径，再删除本任务新增的 D 盘范围：`runtime\asr-envs`、`runtime\asr-cache`、`runtime\cache\asr`、`runtime\asr-temp`、`runtime\temp\asr`、`runtime\logs\asr`、`runtime\asr-benchmark`、`tools\asr`、`模型\asr`、`experiments\asr`、`项目\ASR基准\output` 和本任务文档变更。

回滚不得包含原始 `项目\ASR基准\input\benchmark.mp4`、基础 `.venv`、项目 FFmpeg、正式 `src/liveclip` 或 TASK-001 产物。本任务没有执行回滚或删除原样本。

## 19. 下一步建议

TASK-002-FIX2 完成后先停止，下一步仅建议执行一次 TASK-002-FIX2-R 定向独立复核与质量评分，不执行 TASK-003。FIX2-R 通过后，模型选型仍需另行完成人审闭环：审核 20 个窗口，必要时补一份参考 SRT/TXT，再用已实现的归一化/CER/WER 工具计算准确率和漏句/重复统计。只有人审完成后，才能在 SenseVoice 与 Paraformer 之间确定最终中文生产基线；如果词级切点是硬要求，再评估 Faster-Whisper 的速度成本。
