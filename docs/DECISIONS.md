# 技术决策记录

## D-0001｜本地优先存储

- 状态：已接受
- 决策：项目代码、`.venv`、运行数据、设置和未来模型优先放在 `<PROJECT_ROOT>`。
- 原因：避免 C 盘被大型缓存或模型占用，并方便整体备份与回滚。

## D-0002｜Python 基线

- 状态：已接受
- 决策：当前使用 64 位 Python 3.12；项目允许 Python `>=3.11,<3.14`。
- 原因：本机 3.12.10 可用，且满足当前 Pydantic/pytest 验证需求。

## D-0003｜数据契约

- 状态：已接受
- 决策：三个模块接口使用 Pydantic v2 严格模型，拒绝未知字段；V1 只接受 `schema_version = "1.0"`。
- 原因：尽早暴露跨模块数据错误，支持 JSON 往返和后续生成 JSON Schema。

## D-0004｜时间单位

- 状态：已接受
- 决策：所有 `start`/`end` 时间使用秒，可为小数，且结束时间必须严格大于开始时间。
- 原因：与 FFmpeg 常用时间表达兼容，并支持帧以下之外的精确切点描述。

## D-0005｜TASK-000 依赖边界

- 状态：已接受
- 决策：只安装 Pydantic 和 pytest 及其轻量传递依赖；不安装媒体、界面、ASR 或机器学习大型依赖。
- 原因：本任务只验证契约和骨架。

## D-0006｜TASK-000-FIX 严格契约修复

- 状态：已接受
- 决策：启用全局严格类型和 `extra="forbid"`，所有可写入 JSON 的浮点字段拒绝非有限数；分类字段冻结为英文 `Literal`，现实时间点必须带时区并规范为 UTC。
- 原因：阻止 Pydantic 自动转换错误类型，避免非标准 JSON、跨模块分类漂移和无时区时间歧义。

## D-0007｜文本与评分精度

- 状态：已接受
- 决策：取消全局字符串裁剪；原始文本、清洗文本、逐字稿、字幕修改和用户备注无损保存。评分内部及 JSON 保存未舍入值，判级使用未舍入值；UI 需要显示时按 `ROUND_HALF_UP` 保留 1 位小数。
- 原因：JSON 若只保存已舍入分数，会在 `64.95`、`74.95`、`84.95` 等边界破坏无损往返并可能改变等级。精确数据与显示格式分离可同时保证契约稳定和一致展示。

## D-0008｜时间范围完整性

- 状态：已接受
- 决策：`current_analysis` 顶层增加有限正数 `video_duration`，用于执行候选范围上界校验；timeline 相邻 segment 最多允许 `0.05` 秒识别边界重叠。
- 原因：没有视频时长就无法执行候选不得超界的规则；固定小容差允许识别器的边界抖动，同时拒绝明显重叠或反向数据。

## D-0009｜项目进程级缓存策略

- 状态：已接受
- 决策：`tools/Run-Tests.ps1` 仅在子进程中设置 `PIP_CACHE_DIR`、`TEMP`、`TMP` 和 UTF-8 环境，并直接调用项目 `.venv` Python；不修改 Windows 用户或系统环境变量。
- 原因：后续任务可重复使用 D 盘缓存和临时目录，又不会删除 C 盘已有缓存或改变用户的全局配置。

## D-0010｜项目内 FFmpeg 便携基线

- 状态：已接受（TASK-001 本地验证完成，待独立复核）。
- 决策：使用 FFmpeg 官方下载页列出的 gyan.dev Windows 64 位 release full 静态构建 8.1.2，固定安装在 `tools/ffmpeg`；安装前比对发布方 SHA-256，运行时不查询或修改系统 PATH。
- 原因：稳定路径和公开校验值便于复现与审计，便携解压不会让未知安装器改变系统状态。

## D-0011｜媒体子进程与输出发布规则

- 状态：已接受（TASK-001 本地验证完成，待独立复核）。
- 决策：所有 FFmpeg/ffprobe 调用使用 argv 列表和 `shell=False`，捕获输出、限制超时并返回结构化错误；输出使用同目录唯一临时文件并以不覆盖现有目标的方式原子发布。
- 原因：中文和空格路径无需 shell 转义，调用失败不会终止宿主程序，且中断或并发时不会把残缺文件伪装成完成输出。

## D-0012｜精准裁切和字幕基线

- 状态：已接受（TASK-001 本地验证完成，待独立复核）。
- 决策：精准裁切的稳定基线为 CPU `libx264` + AAC 重编码，默认时长误差容差为 0.15 秒；SRT 以纯 Python 实现毫秒级边界裁剪和重新计时，烧录使用 `subtitles`/libass。
- 原因：本机 AMF 运行探针未成功，CPU 基线已实际通过；纯 Python SRT 路径无需新增大型依赖，并可独立单元测试。

## D-0013｜FFmpeg 来源与发布方校验链

- 状态：已接受（TASK-001-FIX 本地验证完成，待独立复核）。
- 决策：固定使用 FFmpeg 官方下载页列出的 gyan.dev Windows 64 位 release full 8.1.2 构建。安装时必须记录官方页、官方列出的 Windows 提供方、选定提供方页面、直接 URL、文件名、大小、下载时间、本地 SHA-256 和发布方校验 URL；默认流程实际读取发布方 `.sha256`，依次比对发布方值、固定审计值和本地文件值。
- 失败条件：发布方值缺失或格式错误、固定值与发布方不一致、本地文件与发布方不一致、压缩包为空、解压或能力探针失败时均不得形成稳定安装；未知现有安装目录不得覆盖。
- 发布规则：下载先写唯一 `.partial`，解压到 D 盘项目临时目录，验证完成后以同卷目录移动发布；同版本且安装标记、文件和运行版本均匹配时安全跳过，不修改 PATH。
- 原因：区分“本地计算了哈希”和“实际与发布方比对”可避免把未完成的来源验证误写成通过。

## D-0014｜Windows 子进程混合编码

- 状态：已接受（TASK-001-FIX 本地验证完成，待独立复核）。
- 决策：所有媒体命令继续使用 argv 列表、`shell=False` 和二进制 stdout/stderr 捕获。解码顺序冻结为严格 UTF-8；检测到 BOM 时使用 `utf-8-sig`；失败后使用 Windows 当前 ANSI 代码页（本机 CP936）；最后以替换模式安全降级。
- 结构化结果：stdout 与 stderr 各自记录原始字节数、解码文本、实际编码和是否发生替换；失败与超时也保留同样元数据。
- 日志规则：技术日志使用 UTF-8，不记录环境变量内容或其他凭据；用户级错误保持简洁，细节保存在结构化失败对象中。
- 原因：Windows 工具可能混合输出 UTF-8、BOM、GBK/CP936 和非法字节，过早按单一编码解码会丢失整个诊断结果。

## D-0015｜音画同步指标与 MVP 容差

- 状态：已接受（TASK-001-FIX 本地验证完成，待独立复核）。
- 决策：用 ffprobe JSON 分别测量首个视频帧 PTS、首个音频包 PTS、视频/音频流时长和容器时长。`av_start_offset_ms = (audio_start_time - video_start_time) * 1000`，负值表示音频较早；流时长差和目标时长差也保留 `音频 - 视频`、`容器 - 目标` 的正负号。
- MVP 容差：裁切后 A/V 起始绝对差不超过 100 ms；音频与视频流时长绝对差不超过 150 ms；容器与目标时长绝对差不超过 150 ms，边界包含在内。
- 通过条件：`sync_within_tolerance` 同时要求起始差和流时长差通过；`duration_within_tolerance` 要求目标时长差通过。缺失首 PTS、缺轨、非有限数或任一阈值超限均失败并产生结构化警告。
- 原因：单看容器总时长无法发现首时间戳偏移或流尾长度差；三类指标共同形成可自动复核的同步闭环。

## D-0016｜冻结 FFmpeg 生产来源并隔离测试注入

- 状态：已接受（TASK-001-FIX2 本地验证完成，待独立复核）。
- 生产决策：提供方 `gyan.dev`、提供方页面、版本 `8.1.2`、`full_build`、归档名、下载 URL、发布方校验 URL 和固定 SHA-256 均为 `Install-FFmpeg.ps1` 内受审计常量；生产入口不再提供来源、版本、归档名或哈希覆盖参数。未来升级必须修改常量并重新独立审核。
- 测试决策：离线注入仅在显式 `-TestMode` 下可用，只接受带哨兵文件的隔离根内本地绝对路径或 `file:` URI；项目根和资源必须位于该隔离根，远程 URL 与真实项目 `tools\ffmpeg` 目标均被拒绝。测试摘要固定为 `mode=test`、`selected_provider=test_fixture`、`source_type=local_test_resource`。
- 摘要决策：来源摘要必须反映实际来源；历史安装时验证、本次发布方文本读取、本次匹配、本次归档重算和本次归档下载分别使用 `publisher_hash_verified_at_install`、`publisher_hash_checked_this_run`、`publisher_hash_match_this_run`、`archive_hash_recomputed_this_run`、`archive_downloaded_this_run`。
- 同版本策略：采用完全离线安全跳过，不请求发布方校验文本。因此历史记录可为 `publisher_hash_verified_at_install=true`，但本次必须为 `publisher_hash_checked_this_run=false`、`publisher_hash_match_this_run=null`、`archive_hash_recomputed_this_run=false`、`archive_downloaded_this_run=false`。
- 旧标记兼容：允许把旧 `sha256` 解释为历史安装归档哈希，把旧 `sha256_verified_against_publisher` 解释为历史安装验证状态；缺失的 `publisher_sha256` 保持未知，不伪造、不迁移、不把历史值冒充本次读取值。
- 原因：生产来源的真实性不能由调用者提供的互相匹配值证明；历史证据与本次动作也必须在机器可读字段中保持时态分离。原归档已删除时不得声称本次重新计算其哈希。

## D-0017｜FFmpeg 测试模式固定磁盘与重解析点隔离

- 状态：已接受（TASK-001-FIX3 本地验证完成，待 FIX3-R 定向只读复核）。
- 本地磁盘决策：测试模式只接受本机固定磁盘上的绝对路径，或 Host 为空且转换后仍通过同一检查的本地 `file:` URI。UNC、带 Host 的远程 `file:` URI、网络映射盘、非固定或无法确定类型的卷、设备路径和命名管道路径一律在文件读取、复制和解压前拒绝。
- 重解析点决策：隔离根及其从卷根开始的已存在父路径、ProjectRoot、测试资源、安装目标、标记、临时归档、partial、解压和发布路径链均不得包含 `FileAttributes.ReparsePoint`。本阶段直接拒绝 junction、symlink、mount point 等重解析点，不实现跟随并解析最终物理路径。
- 时序决策：首次验证后，在临时目录创建、资源读取/复制、归档移动、解压前后和发布前后重复验证；解压树也拒绝重解析点，以降低检查后替换风险。该措施降低但不宣称消除所有 Windows 文件系统竞态。
- 失败发布决策：归档即使通过大小、发布方文本和真实 SHA-256 检查，只要解压失败，就必须非零退出、清理本次 partial/临时归档/解压目录，不写安装标记、不形成稳定安装，并保留隔离项目中的既有用户文件。
- 原因：词法路径包含关系不能证明真实文件系统隔离；采用固定磁盘白名单和重解析点拒绝策略更简单、可审计，也能保护真实项目内 FFmpeg 安装。

## D-0018｜TASK-002 本地 ASR 候选与暂定角色

- 状态：技术验证已由 TASK-002-FIX2-R 以 100/100 最终通过；无阻断问题，不需要 FIX3；准确率与最终生产选型仍待人工审核。
- SenseVoice 决策：首选官方 GGUF 路线因当前官方 README 尚未提供本任务所需 timestamps，改用官方 sherpa-onnx SenseVoiceSmall INT8 + Silero VAD。其热 RTF 0.02449、峰值 RSS 490.44 MiB，暂定为低资源默认候选；时间轴仅为 VAD 段级，不伪造 word 时间戳。
- Paraformer 决策：保留 `paraformer-zh + fsmn-vad + ct-punc` 作为中文准确率挑战者，并只执行一次固定热词探针。其热 RTF 0.04827，但峰值 RSS 5.979 GiB；只有人工审核显示明显文字质量收益时，才考虑承担资源成本。
- Faster-Whisper 决策：保留 small CPU int8 作为词级时间戳和国际化备用路线。它提供 3,033 个词级时间戳，但热 RTF 0.22376 且本样本输出无标点。
- 依赖决策：三候选使用 D 盘独立环境；FunASR 使用官方 PyPI CPU 配对 `torch/torchaudio 2.11.0+cpu`。所有环境无 CUDA/NVIDIA 包，不修改基础 `.venv`。
- 准确率边界：无参考字幕时不计算 CER/WER、不合计准确率总分。技术评分只说明速度、时间戳、资源与功能完整性；最终生产模型必须等待 20 窗口人工审核或参考字幕评测。
- 原因：当前证据足以比较本机可运行性、吞吐、资源和输出能力，但不足以证明真实直播文字准确率、漏句和重复情况。

## D-0019｜ASR 时间戳证据与性能复现边界

- 状态：已接受（原 FIX-R 漏检已由 TASK-002-FIX2 修复，并经 FIX2-R 最终复核通过）。
- 时间轴决策：统一 ASR 输出禁止根据整段音频时长、字符长度、平均分配、相邻结果或其他无模型证据的信息猜测或伪造时间戳。无可用时间戳的文本不得进入 timeline segment；原始文本保留在 raw JSON，并以包含数量、raw 索引和原因的结构化 warning/error 追溯。
- 失败决策：候选存在文本但完全没有可用时间戳时，统一结果标记 `timeline_status=unavailable`，保留 raw/unified/TXT/metrics，候选以失败退出且不生成正常 SRT。部分条目缺失时只保留有真实时间证据的 segment，标记 `timeline_status=partial`，并记录所有未定时条目，不静默丢弃。
- 性能复现决策：后续横向性能比较必须固定并记录电源状态、Windows 电源模式、背景 CPU 负载、线程数、候选顺序和候选间冷却时间。接电原实验与电池供电复跑的差异只能记录为复现限制，不解释为单一确定因果。
- 原因：确定时间轴会直接进入字幕、人工审核和切片链路；把未知范围伪装成确定范围会产生比显式失败更危险的下游误用。供电和背景负载未固定时，性能变化也不足以支持单因果结论。

## D-0020｜Paraformer 来源顺序在适配器层校验

- 状态：已接受（TASK-002-FIX2-R 最终复核通过，评分 100/100）。
- 来源顺序决策：Paraformer 的 `sentence_info` 条目及多个 raw item 必须按模型原始出现顺序在适配器层校验；当前 `start` 和 `end` 均不得早于上一个已接受有效段。公共层排序可保留为通用标准化，但不得被视为来源异常修复。
- 排除决策：非单调条目使用既有 `PARAFORMER_TIMESTAMP_INVALID` / `timestamp_non_monotonic` 结构化排除，记录 raw/sentence 索引、当前与前序时间以及 `raw_text_preserved=true`。异常条目不进入 segment 或 SRT。
- 恢复决策：比较基准始终是上一个已接受有效段；排除一个异常条目后，后续条目仍独立判断，不因单个异常级联丢弃其后的正常段。
- 空结果决策：正常无文本、无 segment 的静音结果不是时间轴不可用，不产生 warning/error，也不标记 `timeline_status=unavailable`。
- 原因：来源非单调若交给公共排序，会丢失异常证据并把错误时间轴静默发布为正常字幕；在适配器边界拒绝可保持 raw 可追溯性，同时不改变正常模型时间。

## D-0021｜source-only 测试统一入口与原生命令失败传播

- 状态：已接受（TASK-GITHUB-002-FIX2 本地验证通过，待在线 Actions 和 FIX2-R 独立审核）。
- 决策：GitHub `lightweight-tests` 和本地任务发布共同调用 `tools/github/Invoke-SourceOnlyTests.ps1`。基础测试、ASR 实验测试和 `pip check` 后必须立即读取 `$LASTEXITCODE`，任一非零即停止，后续成功命令不得覆盖失败。
- 编码决策：脚本仅在自身进程范围为 Python 设置 UTF-8 环境并在结束时恢复。两个进程执行器回归测试由子 Python 的 `stdout.buffer`/`stderr.buffer` 明确写 UTF-8 字节，继续严格断言完整中文、退出码 7 和无替换字符。
- workflow 决策：依赖安装的每个 pip 命令也显式传播失败；同 PR/ref 的新 run 会取消旧 run。三个 required job 名称保持不变。
- 原因：Windows PowerShell 5.1 不会自动把 run block 中较早原生命令的非零结果保持到步骤结束；控制台文本编码也不是 `run_process()` 字节捕获/解码契约的一部分。

## D-0022｜Codex GitHub 自动化绑定与人工合并门禁

- 状态：已接受（TASK-GITHUB-002-FIX2 本地验证通过，待在线 Actions 和 FIX2-R 独立审核）。
- 仓库决策：`.github/liveclip-workflow.json` 是 canonical repository、base branch、required checks 和 85/100 审核门槛的单一策略来源。Start、Publish、Audit 和 Handoff 都拒绝缺失、歧义、非 GitHub 或其他 owner/repository 的 origin。
- 启动决策：Start 只从干净的 base branch 运行，先 `pull --ff-only` 并验证本地/远端 SHA 完全一致；落后只允许快进，领先或分叉停止。
- 发布决策：任务发布必须指明本次 RESULT 报告并在 stage/commit 前通过统一测试；审核发布只接受一个或多个 AUDIT 报告；push 始终普通且有界，不 force、不 merge、不启用 auto-merge、不重复创建同 head/base PR。
- 交接决策：Handoff 同时报告 head SHA、required checks、RESULT/AUDIT、审核分数/结论、阻断问题、`eligible_to_mark_ready` 和 `eligible_for_manual_merge`。只有 Ready PR 才可能具备人工合并资格，最终动作始终由用户决定。
- 原因：本项目的本地 Codex 发布器服务于唯一公开仓库；把仓库身份、测试、审核和 Draft/Ready 状态放进机器可读门禁，能减少误发布、假绿和错误合并。

## D-0023｜20窗口本地人工听音审核包

- 状态：已接受（TASK-002-HUMAN-001 本地生成与验证完成，等待用户人工听音）。
- 证据决策：人工听音是 SenseVoice、Paraformer 与 Faster-Whisper 最终模型选择的重要证据；没有人工标准文本时不伪造 CER/WER，也不宣布准确率冠军。
- 存储决策：真实音频、运行时审核数据、用户结果、备注及 JSON/CSV 导出默认只保存在 Git 忽略的 `local-data/`。GitHub 只保存生成器、离线 HTML 模板、合成测试、使用说明和脱敏任务报告。
- 范围决策：第一轮只审核既有 20 个窗口，页面使用相对音频路径和 localStorage，可导入/导出 JSON、导出 CSV；本阶段不运行 ASR 模型、不调用云端、不修改正式 `src/liveclip`，也不执行 TASK-003。
- 时间边界决策：既有 CSV 以三位小数保存时间，允许末端因表示舍入比 WAV 精确时长最多高半毫秒；原值保留在 manifest，实际 PCM 帧严格钳制到 WAV 边界，更大的越界仍拒绝。
- 原因：轻量、可追溯、完全离线的人工证据闭环可以在不上传真实直播音频的前提下补足纯技术指标无法回答的文字质量问题。

## D-0024｜ASR MVP生产基线与人工结果门禁

- 状态：TASK-002-HUMAN-002本地分析完成；等待独立审核、Draft PR三项检查和用户手动合并决定。
- 输入门禁：完成版人工JSON必须与真实`review-manifest.json`的原始文件SHA-256精确匹配，且必须为`schema_version=1.0`、指定审核类型、`completed=true`、20/20窗口。`severity`和`error_tags`的模型键集合必须恰好等于SenseVoice、Paraformer、Faster-Whisper；额外键、重复/未知窗口、非法值或未知/重复标签均直接阻断，不自动修复。
- 质量决策：20窗口中Paraformer明确胜出18次、聚合质量分92.58，SenseVoice胜出2次、49.00，Faster-Whisper胜出0次、40.00；三者平均severity分别为0.25、0.90、1.20，severity 3数量分别为0、0、1。没有难辨认窗口，因此全量与清晰音频子集排序一致。
- 生产基线：MVP主模型为Paraformer，备用模型为SenseVoice；`decision_status=confirmed_mvp_baseline`，`decision_confidence=high`。人工质量是主证据；既有速度、内存、标点和时间戳能力只作次级工程证据，本任务不重新运行模型。
- 评分口径：`winner_score`、`severity_quality_score`、`reliability_score`分别按胜出积分、0—3严重度和severity 3数量计算，聚合权重为45%/35%/20%；公开显示使用`ROUND_HALF_UP`保留2位小数，本地JSON同时保存未舍入数值和精确分数。
- 隐私决策：原始人工JSON、用户备注、实际听写、逐窗口候选文本和`local-data/`不进入Git；公开材料只保留输入哈希、聚合统计、决策和样本限制。
- 重新评估条件：模型或权重、预处理/切段规则、目标硬件、主要语种、噪声/专名分布或直播领域发生实质变化时，重新执行定向人工听音；当前20窗口单样本结果不是行业基准，也不称为CER/WER。
- 阶段门禁：TASK-002只有在本任务独立审核通过且由用户决定合并后才能正式关闭；TASK-003在此之前继续禁止启动。

## D-0025｜TASK-003 单视频本地 ASR 生产管线

- 状态：已接受；PR #5 已合并，merge commit 为
  `0e619b6fbb3e34250f10b1719dfb5a666ea7020f`。
- 范围决策：只提供 `python -m liveclip transcribe` 一个入口；单次只处理一个最长
  3 小时的 MP4。默认 Paraformer，SenseVoice 只能由用户手动选择，不自动切换。
- 分块决策：默认按 60 秒顺序处理。每次只提取一个 PCM16、16 kHz、单声道 WAV，
  模型在进程内只加载一次；每块完成后原子更新 `task_state.json`，已完成块恢复时不重跑。
- 状态门禁：源 SHA-256、时长、引擎、分块长度和本地模型文件身份共同绑定状态。
  任一不匹配都拒绝复用；损坏状态不会被静默替换。
- 发布决策：块结果只存在于状态文件；全部块完成、源 SHA-256 复核和 timeline 校验
  通过后才发布 SRT/TXT，最后发布 `timeline.json`。发布失败会清理本次新建的部分正式文件，
  不覆盖既有成功结果。
- 离线与资源决策：模型加载和推理期间主动阻断 socket 连接，缓存和临时目录保持在
  本地资产根；单任务、四线程、无并行模型，不查询电池状态，也不在电池供电时自动暂停。
- 原因：这是满足当前单视频核心闭环的最小实现；模型管理器、插件系统、后台服务、
  通用工作流和 TASK-004 均不属于本任务。

## D-0026｜TASK-004 顺序语义分段与爆点候选

- 状态：已接受；独立审计 89/100、无阻断，PR #6 已合并，merge commit 为
  `a1e8921abb8d43d289e28282ef63e058b86e6470`。
- 接口决策：只支持一个用户配置的 OpenAI-compatible Chat Completions HTTPS 地址，
  使用 Python 标准库 HTTP，不安装厂商 SDK、不路由或自动切换模型。API Key 只从
  环境变量读取，不进入请求正文、状态、日志或 Git。
- 窗口决策：按时间顺序切为最多 10 分钟且约 12,000 字幕字符的非重叠窗口，不拆单个
  segment；单线程顺序请求，每窗口最多 3 个候选，每完成一个窗口原子保存状态，不做
  全文第二轮模型重排或 embeddings。
- 可信字段决策：模型只提出真实连续 segment 范围、标题、摘要、理由、quote segment
  ID 和七项原始分值。程序从 timeline 计算毫秒时间、复制 quote、计算并限制总分，
  过滤 60 分以下和 15—180 秒之外候选，按 60% 重叠规则去重并限制全局 20 个。
- 恢复与发布决策：状态绑定 timeline 文件 SHA-256、endpoint host、model 和固定窗口
  参数，不保存密钥。全部窗口完成并通过输出校验后才原子发布
  `current_analysis.json`；当前加历史总共最多保留 3 个完整版本，普通发布失败会恢复
  旧 current 和历史。
- 真实验证：827.766 秒、169 segments 的真实 timeline 分为 2 个窗口，完成态运行发起
  2 次请求并在 16.282 秒内生成 11 个 topics 和 6 个 candidates；全部范围、时间、
  quote、总分和 timeline SHA 回溯通过。前 3 候选人工抽查显示真实可用性不等于全部
  可直接采用：一项基本合理但需营销合规复核，一项存在标题外推和范围不完整，一项
  基本合理但隐私风险扣分偏低，因此后续仍必须保留人工审核门禁。
- 原因：该边界形成最小可恢复语义分析闭环，同时保持用户媒体、本地路径和凭据不离开
  本机，也避免为单 timeline 技术验证引入 Agent、插件、数据库、RAG 或工作流引擎。

## D-0027｜TASK-005 本地审核与单片段导出

- 状态：已接受；独立审核 93/100、无阻断，PR #7 已合并，merge commit 为
  `7ae8b89dfc92f5915030662e7a36bf048da14254`。
- 输入决策：一次只绑定一个 MP4、一个 completed timeline 和一个 completed analysis；
  文件名、视频 SHA、时长、timeline SHA、candidate 范围与 schema 全部在页面启动前校验。
  原视频、timeline 和 analysis 始终只读，不因调整写回 analysis。
- 审核决策：所有 AI 候选默认“待审核”，首项只可默认选中用于预览；分数、排名和
  `recommended` 均不代表批准。只有服务端收到严格布尔 `confirmed=true` 和合法的
  1—180 秒最终范围后才允许一次导出。
- 页面与服务决策：使用标准库 `ThreadingHTTPServer` 和项目内原生 HTML/CSS/JavaScript，
  仅绑定 `127.0.0.1`，页面、session、单一媒体文件、导出与停止 API 使用随机 token。
  媒体端点支持单范围请求；页面生命周期事件与心跳超时共同停止服务，不建设常驻后台。
- 导出决策：使用现有 FFmpeg 精确重编码 H.264 + AAC，不提供 stream copy 或 GPU 分支；
  MP4 与 timeline 派生 SRT 先写临时文件，ffprobe 校验后无覆盖发布，最后才原子替换
  `review_current.json`。失败回滚本次正式输出并保留旧 review；电池供电不暂停。
- 产品边界：浏览器无法直接解码的 MP4 只提示兼容限制，不生成代理；不做批量、多片段
  拼接、波形、缩略图、字幕烧录、竖屏、队列、自动发布、TASK-003/TASK-004 backlog 或
  TASK-006。
- 原因：该边界以最小本地页面补齐“AI 候选必须人工预览与确认”的安全门禁，同时让
  输出可回溯、失败不伪完成，并避免把首版扩大为通用剪辑器或长期 Web 服务。

## D-0028｜TASK-006 单视频端到端入口与 Windows 启动器

- 状态：已接受；PR #8 已合并，merge commit 为
  `97fdcd5bb782a5fafef188a1c6f8f34839d0d24a`。
- 编排决策：只新增 `python -m liveclip run` 顺序调用既有 transcribe、analyze 和 review；
  一次只处理一个 MP4，不复制 ASR、模型分析、审核或导出算法，也不建立数据库、队列、
  工作流引擎或多 Agent。
- 启动决策：任何长时间 ASR 前先验证文本模型环境变量、FFmpeg/ffprobe、本地 ASR 模型、
  MP4 音视频流和工作目录写入。默认 Paraformer、视频旁工作目录及其 `exports`，允许用户
  显式选择 SenseVoice、自定义目录或禁止自动打开浏览器。
- 恢复决策：timeline 绑定视频文件名、SHA 和时长；analysis 绑定 timeline SHA；completed
  review 还必须绑定输入哈希并存在对应 MP4/SRT。合法结果复用，既有未完成状态交给原模块
  恢复；损坏或错配文件不自动删除、不静默覆盖。
- 状态决策：`pipeline_status.json` 仅原子记录源文件名/SHA、三个 pending/completed 阶段、
  固定产物文件名和 UTC 时间；不保存绝对路径、密钥、字幕、候选标题或推荐理由。状态损坏
  时从可信产物重推导，不替代 TASK-003/TASK-004 的恢复状态。
- 启动器决策：根目录 `.cmd` 只调用 Windows PowerShell 脚本；脚本使用系统 MP4 选择框和
  两个原生选项，沿用源码 Python 环境并调用统一命令。不需要管理员权限、不写系统环境、
  不安装 GUI 框架，取消选择正常退出，失败时保留控制台。
- 审核易用性决策：候选或任何范围变化都会撤销当前确认；导出完成态只展示文件名、最终
  范围、时长和输出文件夹名称。服务端人工确认门禁和单次导出边界不变。
- 产品边界：不做批量、多片段、队列、自动开始下一视频、安装包、更新器、托盘、服务、
  云存储、自动上传、代理、波形、缩略图、新模型/provider 或 TASK-007。
- 原因：该实现形成可日常试用的最小本地闭环，同时让已有模块继续拥有算法和恢复状态，
  将编排层限制为验证、衔接、最小状态和启动体验。

## D-0029｜TASK-007 默认字幕烧录与 Windows 启动器稳健性

- 状态：本地实现、自动测试和真实验证完成；等待 Draft PR latest-head 三项检查。
- 字幕决策：人工确认后的正式 MP4 默认烧录与最终裁剪范围完全相同的 timeline 派生 SRT，
  同时继续生成同名独立 SRT；不重新调用 ASR 或文本模型，不翻译、纠错或改写字幕。
- 样式决策：固定微软雅黑优先、白色文字、黑色描边、底部居中和安全边距；视频高度
  `<=720`、`721..1440`、`>1440` 分别使用 24、28、32 px 目标字号，并按视频高度换算为
  libass 的 SRT 脚本坐标，避免竖屏视频出现过大字幕。不提供字体、颜色、位置、动画或
  字幕编辑器。
- 发布决策：最终 SRT 先写临时文件，非空时由同一次 FFmpeg H.264/AAC 导出烧录；ffprobe
  校验编码、音视频流和时长，并在发布前复核原视频、timeline、analysis SHA。任一步失败
  都不发布正式 MP4/SRT/review，既有同名输出不覆盖；成功后才原子记录
  `subtitles_burned_in=true`。旧的缺字段 review 不作为完成态复用。
- 空字幕决策：最终范围确实没有字幕时，不强造字幕或重跑识别；仍导出视频和空独立 SRT，
  并记录 `subtitles_burned_in=false`，页面给出与非空片段不同的明确说明。
- 启动器决策：只选择一个 Python，依次尝试仓库 `.venv`、资产根 `.venv`、PATH 中首个
  非 WindowsApps Application。Windows 应用执行别名自动排除，不要求用户关闭；资产根
  缺失或不完整时列出缺失项，并给出不含本机硬编码路径的用户级环境变量设置示例。
- 产品边界：不下载或移动模型，不修改 TASK-003/TASK-004 核心逻辑，不做批量、多片段
  拼接、字幕编辑、翻译、竖屏转换或自动发布，也不执行 TASK-008。
- 原因：真实首次试用表明独立 SRT 不适合直接发布，且 Python 别名和资产位置会阻碍普通
  Windows 用户启动；该最小修复保持现有审核门禁、字幕原文与本地资产控制不变。
