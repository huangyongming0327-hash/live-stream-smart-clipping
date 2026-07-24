# TASK-001-FIX-R 独立只读审核报告

- 审核任务：FFmpeg 来源、编码与音画同步独立只读复核
- 审核日期：2026-07-19（Asia/Shanghai）
- 项目目录：`<PROJECT_ROOT>`
- 审核方式：完整读取指定文件，审阅实现与测试，运行既有离线测试、合成媒体流程和只读探针，只读核对官方网站与发布方校验文本
- 唯一项目写入：本报告；测试产生的文件仅位于既有 `runtime/` 测试/日志目录
- 未执行：安装或下载软件/模型、收费 API、系统 PATH 修改、Git 提交/远程操作、TASK-002、问题修复

## 1. 审核结论

**不通过**。

独立复核确认，Windows UTF-8/GBK 混合编码和音画同步自动验收闭环已经修复，当前项目内 FFmpeg/ffprobe 也确实是 D 盘的 gyan.dev 8.1.2 full build；本次重新读取的发布方 SHA-256 与原安装标记记录相同，全部媒体实测和 117 项完整回归通过。

但原三项阻断问题中的“FFmpeg 来源与校验链”仍未完全修复：生产安装脚本公开允许调用者同时替换下载 URL、发布方校验 URL、固定哈希、版本和归档名，却仍把提供方写成 gyan.dev；同时，同版本跳过分支没有在本次运行读取发布方校验文本，却输出 `publisher_hash_compared=true`。这两点会使“固定可信来源”和“本次比对”的结构化证据不可靠，属于来源链核心阻断。

## 2. 阻断问题

### B-01｜生产安装入口可绕过固定来源并生成错误来源声明

- `tools/Install-FFmpeg.ps1:3-7` 把 `DownloadUri`、`PublisherChecksumUri`、`ExpectedSha256`、`ExpectedVersion` 和 `ArchiveFileName` 全部暴露为可覆盖参数。
- `tools/Install-FFmpeg.ps1:47-60` 只要求资源是任意 HTTPS URL或任意现有本地文件，没有把非测试运行限制为 gyan.dev 固定地址。
- `tools/Install-FFmpeg.ps1:172-177` 的摘要仍无条件写入 `selected_provider=gyan.dev` 和 gyan.dev 提供方页面，即使实际 URL 已被参数替换。
- `tools/Install-FFmpeg.ps1:228-315` 会按调用者同时提供的新 URL、新校验 URL、新固定哈希和新版本继续验证、解压并发布；因此该脚本保证的是“调用者提供的三值互相一致”，而不是“生产来源不可变且属于已审计的 gyan.dev 8.1.2 full build”。

影响：具有脚本调用权限的人可传入其他 HTTPS/本地归档及其匹配哈希，安装结果仍可能被摘要和标记声明为 gyan.dev。这直接破坏来源审计的真实性。离线测试确实需要本地资源注入，但当前没有明确、受限的测试模式把它与生产入口隔离。

修复要求：生产路径必须冻结来源、校验 URL、版本和固定哈希；若保留测试注入，应使用显式测试模式，限制为本地资源和隔离的测试项目根，并确保摘要按实际来源标记为测试资源，不能写成 gyan.dev。

### B-02｜同版本跳过分支把历史记录误报为本次发布方比对

- `tools/Install-FFmpeg.ps1:211-215` 在识别到同版本安装后直接返回，先于 `tools/Install-FFmpeg.ps1:228` 的发布方校验文本读取。
- 现有 `tools/ffmpeg/.liveclip-ffmpeg-install.json` 没有 `publisher_sha256` 字段，只有原安装时的 `sha256` 和 `sha256_verified_against_publisher=true`。
- `tools/Install-FFmpeg.ps1:155-168` 在这种情况下把本地记录的 `sha256` 同时当作 `publishedHashValue`，随后仅因两个字段非空就认定 `$compared=true`。
- 本次实际运行因此输出 `publisher_hash_compared=true`、`publisher_hash_match=true`，但该次脚本运行没有联网读取 `.sha256` 文本。

影响：机器可读摘要无法区分“原安装时已记录比对”和“本次重新读取发布方哈希”。这与本任务要求的三分法（原安装时本地哈希、本次发布方哈希、本次未重新下载归档）不一致，也会误导自动审计。

修复要求：至少分别输出 `publisher_hash_verified_at_install` 与 `publisher_hash_checked_this_run`；若跳过分支不联网，应明确后者为 `false`。若需要声称本次比对，则只获取 64 字节校验文本并实际比较，仍不得下载归档。

## 3. 重要问题

1. 来源链专项测试 5 项全部通过，但没有测试“生产模式拒绝任意来源覆盖”“摘要提供方必须与实际 URL 一致”或“跳过分支不得把历史比对标成当前比对”。现有同版本测试反而断言了当前有歧义的 `publisher_hash_compared=true`。
2. AMF 初始化失败属实：本次用 64×64 合成源执行 `h264_amf` 空输出探针，得到非零退出码 `-558323010`，核心错误为 `encoder->Init() failed with error 5`。但 `tools/Validate-Media.ps1` 当前只检查编码器是否被列出，并没有执行初始化探针；文档用“此前本机初始化失败”表述基本诚实，标准验证脚本则不能自动发现状态变化。
3. `ProcessFailure.command` 保存完整 argv。当前所有媒体调用参数中未发现凭据，也没有记录环境变量；但未来不得把 Token、签名 URL 或其他秘密放入 argv，否则结构化错误对象可能保留它们。

## 4. 一般建议

1. 为安装脚本补充空文件、发布方校验文本无效、任意来源覆盖被拒绝、摘要来源一致性和跳过分支时态语义测试。
2. 为同步层补充显式缺视频轨、缺音频轨和负流时长差/负目标时长差单元测试。当前代码与本次只读探针均正确拒绝缺轨并保留负号，但现有测试文件没有完整覆盖这些分支。
3. 为超时测试增加“子进程在超时前已输出字节”的断言，以持续验证超时异常确实保留原始字节长度、编码和替换标记。
4. 真实长视频性能、峰值内存、取消/恢复和字幕像素级 OCR 继续留到后续独立任务，不应并入本次修复。

## 5. 原三项阻断问题逐项复核表

| 原问题 | 验证方法 | 实际结果 | 是否修复 |
|---|---|---|---|
| FFmpeg 来源与校验链 | 审阅安装脚本、安装标记和 5 项来源测试；实跑安装脚本；读取 FFmpeg 官方页、gyan.dev 构建页和当前 `.sha256` | 当前安装及默认 URL/哈希正确，坏哈希、截断文件、未知目录和同版本跳过均有保护；但生产参数可整体改写来源且摘要仍宣称 gyan.dev，跳过分支把历史记录误报为本次比对 | **否，部分修复** |
| Windows UTF-8 / GBK 混合编码 | 审阅 `process_runner`；完整回归；运行 9 项编码专项；运行字节精确只读探针 | argv、`shell=False`、二进制捕获、UTF-8/BOM/CP936/替换降级和成功/失败/超时元数据均符合要求 | **是** |
| 音画同步自动验收闭环 | 审阅 ffprobe JSON 同步层和导出校验；运行 17 项同步测试、关键集成测试、完整媒体脚本；对本次三个输出重新探测 | 必需字段、有限数、缺轨/缺 PTS、正负符号、包含边界的 100/150/150 ms 容差及 warnings 均正确；裁切和烧录实测通过 | **是** |

## 6. TASK-001-FIX 完成条件逐项复核表

| 完成条件 | 独立结果 | 判断 |
|---|---|---|
| 复核 FFmpeg 官方页、Windows 提供方、gyan.dev 页面、8.1.2 URL 和 `.sha256` | 2026-07-19 本次独立读取；官方页列出 gyan.dev/BtbN，gyan.dev 页列出 8.1.2 release full，校验文本 HTTP 200、长度 64 | 完成 |
| 安装脚本固定可信来源和发布方 SHA-256 三方比对 | 默认值和新安装正常路径实现三方比对，但生产入口可同时覆盖全部来源与审计值 | **未完成** |
| partial 下载、临时解压、验证后发布 | 代码路径符合；截断下载测试通过；稳定目录发布前检查版本、ffprobe、libx264 和 libass | 完成 |
| 同版本安全跳过、未知目录不覆盖、不改 PATH | 实跑 `already_installed`；测试覆盖跳过/未知目录；PATH 三层均无项目 FFmpeg | 完成，但跳过摘要语义有阻断 |
| 来源链离线测试 | 5/5 通过，0 跳过 | 完成但覆盖不充分 |
| argv、`shell=False`、字节捕获和结构化解码 | 代码与专项测试一致 | 完成 |
| UTF-8、CP936/GBK、BOM、非法字节、中文路径错误和替换标记测试 | 9 项 process_runner 专项全部通过；字节精确复核通过 | 完成 |
| ffprobe JSON 首帧/首包 PTS、两路流时长、容器时长 | 使用三个 JSON 调用，不解析面向用户日志；本次实测可重复 | 完成 |
| 有限数、缺轨/缺 PTS、正负方向、边界容差 | 代码、17 项测试和补充只读探针通过 | 完成 |
| 冻结 100/150/150 ms 容差并接入 `ExportValidation` | 配置、代码、测试和结构化日志一致 | 完成 |
| 12 秒合成媒体，2.3—8.7 秒关键集成测试不得跳过 | 关键测试独立重跑通过，未跳过 | 完成 |
| 字幕烧录时间戳重置和同步回归 | 烧录 A/V -22.000 ms、流时长差 +82.667 ms、目标差 +42.667 ms | 完成 |
| 文档如实披露边界和待复核状态 | 原归档删除、第三方哈希边界、AMF、真实长视频、OCR、待复核和不得进入 TASK-002 均已披露；但结果报告沿用了有歧义的跳过摘要字段 | 部分完成 |

## 7. FFmpeg 来源与哈希复核

### 7.1 当前安装与 PATH

| 项目 | 实测 |
|---|---|
| `ffmpeg.exe` | `<PROJECT_ROOT>\tools\ffmpeg\bin\ffmpeg.exe`，242,496,512 bytes |
| `ffprobe.exe` | `<PROJECT_ROOT>\tools\ffmpeg\bin\ffprobe.exe`，242,291,712 bytes |
| ffmpeg 版本行 | `ffmpeg version 8.1.2-full_build-www.gyan.dev` |
| ffprobe 版本行 | `ffprobe version 8.1.2-full_build-www.gyan.dev` |
| 构建特征 | `--enable-static`、`--enable-libx264`、`--enable-libass`，版本名为 `full_build` |
| 本地 ffmpeg 二进制 SHA-256 | `ad8f211bc894755e0061c55ab280ae00e8d3d4f15a8cc4372b24cfa247b5942e` |
| 本地 ffprobe 二进制 SHA-256 | `9df3b0b5275e830961df6d94e1f7a71121a7abd5ff708e9fec8a0b6084a55015` |
| PATH 查询 | `Get-Command ffmpeg.exe` 未找到，`where.exe ffmpeg.exe` 退出 1 |
| PATH 注册表/进程 | 用户、机器、当前进程 PATH 均不包含项目 FFmpeg 路径 |

代码运行时由 `src/liveclip/media/ffmpeg_paths.py` 解析项目内固定绝对路径，不查询系统 PATH。

### 7.2 在线只读核对

- [FFmpeg 官方下载页](https://ffmpeg.org/download.html) 当前明确说明 FFmpeg 官方只提供源码，并在 Windows EXE Files 下列出 gyan.dev 和 BtbN；页面同时列出 8.1.2 源码版本。
- [gyan.dev 构建页](https://www.gyan.dev/ffmpeg/builds/) 当前列出 8.1.2 release build，并说明构建为 Windows 64 位、静态；full build 包含额外库。
- 安装标记中的实际归档 URL 为 `https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-8.1.2-full_build.7z`，主机确为 `www.gyan.dev`。
- 本次只读 GET `https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-8.1.2-full_build.7z.sha256` 返回 HTTP 200、64 字节，正文为：
  `0fff188997a499b5382e0f66e845d4556c48c54f0113ebed4853d556dbdd7059`
- 本次没有请求或下载 FFmpeg 归档。

### 7.3 三类哈希证据必须分开

| 证据 | 值/状态 | 结论 |
|---|---|---|
| 原安装时本地归档哈希 | 安装标记记录 `0fff...7059`，归档大小 166,721,853 bytes | 是历史安装记录，本次无法重新计算 |
| 本次读取的发布方哈希 | `0fff...7059` | 本次实际读取，和安装记录一致 |
| 本次原归档状态 | 原归档不存在，安装标记位于 `tools/ffmpeg/.liveclip-ffmpeg-install.json`；项目根同名标记不存在 | 没有重新下载、没有重新哈希归档 |

因此可以确认“当前发布方文本与原安装记录一致”，不能声称“本次重新下载并证明原归档或当前二进制与归档逐字节一致”。gyan.dev SHA-256 也不是 FFmpeg 官方源码 PGP 到该第三方 Windows 二进制的可复现构建证明。

### 7.4 安装脚本行为

| 要求 | 独立结果 |
|---|---|
| 哈希不匹配失败 | 是；固定值与发布方不一致、本地归档与发布方不一致均失败 |
| 截断或空下载不发布 | 是；截断测试通过，空文件有显式大小检查 |
| 临时解压后再发布 | 是；唯一临时目录验证后同卷移动 |
| 同版本安全跳过 | 是；本次 0.437 秒返回 `already_installed`、`downloaded_this_run=false` |
| 未知目录不覆盖 | 是；测试保留用户文件并失败 |
| 不修改系统 PATH | 是 |
| 固定可信来源 | **否；公开参数可整体覆盖，见 B-01** |
| 如实区分本次/历史发布方比对 | **否；见 B-02** |

## 8. 混合编码复核

### 8.1 实现检查

- `run_process` 构造字符串 argv 元组并直接调用 `subprocess.run`。
- `shell=False`，stdin 为 `DEVNULL`，stdout/stderr 均为 `PIPE`，没有 `text=True` 或预先指定单一文本编码。
- 解码顺序实际为：严格 UTF-8；若字节以 UTF-8 BOM 开头则用 `utf-8-sig` 去 BOM；UTF-8 失败后用 Windows 当前 ANSI 代码页；再失败则用安全替换。
- stdout/stderr 各自保存 `raw_byte_length`、`text`、`encoding_used`、`replacement_occurred`。
- 非零退出码和 `TimeoutExpired` 都构造相同的 `ProcessFailure` 元数据。
- argv 与 `shell=False` 避免 shell 元字符解释；中文和空格路径直接作为单一参数传入。
- 实现没有枚举、序列化或记录完整环境变量；当前调用方也没有凭据参数。
- 本次 JSON 日志为严格 UTF-8 无 BOM；能力日志为有效 UTF-8 with BOM。

### 8.2 实际测试

运行 `tests/test_media_unit.py -k process_runner`：9 passed、0 failed、0 skipped、20 deselected，pytest 0.19 秒。

覆盖并通过：

- UTF-8 中文；
- CP936/GBK 中文；
- UTF-8 BOM；
- ASCII + CP936 中文路径错误；
- UTF-8 与 CP936 均非法的字节；
- 未知 ANSI 代码页安全降级；
- replacement 标记；
- 中文非零退出错误；
- 超时结构化失败。

补充字节精确只读探针再次得到 UTF-8、CP936、BOM 和 replacement 分支均正确；带超时前输出的探针保留了非零原始字节长度和解码元数据。一次最初使用 PowerShell 管道传中文源码字面量的审计探针受宿主管道编码影响，结果被判为无效并未计入结论；改用固定十六进制字节重跑后通过。

## 9. 音画同步实测

### 9.1 实现与判定

- 同步层分别调用 ffprobe 的流/容器 JSON、首视频帧 JSON、首音频包 JSON；没有解析普通用户日志。
- `video_start_time` 取首帧 `best_effort_timestamp_time`，回退 `pts_time`。
- `audio_start_time` 取首包 `pts_time`，回退 `dts_time`。
- 所有输入和计算结果必须有限；流时长和容器/目标时长还必须非负。
- 缺首 PTS、缺视频轨或缺音频轨均抛出 `ProbeError`。本次补充只读探针实际得到 `no video stream` 和 `no audio stream`。
- `av_start_offset_ms = (audio - video) × 1000`；负值为音频早于视频，正值为视频早于音频。
- `stream_duration_delta_ms = (audio duration - video duration) × 1000`。
- `target_duration_delta_ms = (container duration - target duration) × 1000`。
- 冻结容差为 A/V 起始绝对差 `<= 100 ms`、流时长绝对差 `<= 150 ms`、容器/目标绝对差 `<= 150 ms`；边界包含，只有 `1e-9 ms` 浮点噪声补偿。
- 正负起始偏差、边界、非有限数、超限 warnings 均有测试；补充只读探针确认负流时长差和负目标差保留方向。

### 9.2 本次合成媒体实测

日志：`runtime/logs/media-validation-20260719-120505-93169e71.json`（已完整读取）。本次随后又直接对三个文件运行 `probe_media_sync`，结果与日志/测试一致。

| 字段 | 12 s 合成输入 | 精准裁切 2.3—8.7 s | 中文字幕烧录输出 |
|---|---:|---:|---:|
| `video_start_time` | 0.000000 s | 0.080000 s | 0.080000 s |
| `audio_start_time` | -0.021333 s | 0.018000 s | 0.058000 s |
| `av_start_offset_ms` | -21.333 ms | **-62.000 ms** | **-22.000 ms** |
| `video_duration` | 12.000000 s | 6.360000 s | 6.360000 s |
| `audio_duration` | 12.000000 s | 6.421333 s | 6.442667 s |
| `stream_duration_delta_ms` | 0.000 ms | **+61.333 ms** | **+82.667 ms** |
| `container_duration` | 12.000000 s | 6.422000 s | 6.442667 s |
| `target_duration` | 12.000000 s | 6.400000 s | 6.400000 s |
| `target_duration_delta_ms` | 0.000 ms | **+22.000 ms** | **+42.667 ms** |
| `sync_within_tolerance` | true | true | true |
| `duration_within_tolerance` | true | true | true |
| `warnings` | `[]` | `[]` | `[]` |

### 9.3 媒体流程其他验收

- 使用 12 秒合成 H.264/AAC 输入，不使用用户真实视频。
- 精准裁切范围为 2.3—8.7 秒，目标 6.4 秒，CPU `libx264` + AAC。
- 输入、输出和 SRT 路径均含中文与空格。
- 裁切和烧录输出均各有 1 条视频轨、1 条音频轨。
- SRT 三条重计时结果为 0.000—0.700、1.200—5.200、5.700—6.400 秒；原 SRT 未改变。
- 中文字幕烧录命令成功，输出可由 ffprobe 读取；按文档披露，没有执行像素 OCR。
- 既有输出由 `prepare_output` 拒绝；媒体先写同目录唯一 `.part` 临时文件，完成后才无覆盖发布。

## 10. 测试复核

| 命令 | 总数 | 通过 | 失败 | 跳过 | 耗时 |
|---|---:|---:|---:|---:|---:|
| `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Run-Tests.ps1 -ra --durations=10` | 117 | 117 | 0 | 0 | pytest 3.83 s；整脚本 4.958 s |
| `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Validate-Media.ps1` | 18 | 18 | 0 | 0 | 整脚本 3.979 s |
| `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Run-Tests.ps1 tests\test_media_sync.py tests\test_media_integration.py -ra --durations=10` | 18 | 18 | 0 | 0 | pytest 1.62 s；整脚本 2.732 s |
| `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Run-Tests.ps1 tests\test_ffmpeg_install_source.py -ra --durations=10` | 5 | 5 | 0 | 0 | pytest 2.76 s；整脚本 3.956 s |
| `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Run-Tests.ps1 tests\test_media_integration.py -ra --durations=5` | 1 | 1 | 0 | 0 | pytest 2.31 s；整脚本 3.601 s |
| `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Run-Tests.ps1 tests\test_media_unit.py -k process_runner -ra --durations=10` | 9 | 9 | 0 | 0 | pytest 0.19 s；整脚本 1.329 s |
| `.\.venv\Scripts\python.exe -m pip check` | 不适用 | 通过 | 0 | 0 | 0.485 s |

`Validate-Media.ps1` 同时通过 libx264、H.264、AAC、subtitles/ass/libass、SRT、WAV 和 PCM s16le 强制能力探针，输出 `TRIM_VALID=True`、`BURN_VALID=True`。关键媒体集成测试未被跳过。测试数量与预期 117 和 18 一致。

安装脚本单独实跑：

`powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Install-FFmpeg.ps1`

结果：退出 0，0.437 秒，`already_installed`，`downloaded_this_run=false`。其 `publisher_hash_compared=true` 的语义缺陷已列为 B-02，不把它当作本次联网证据。

## 11. 文档和代码一致性

| 核对项 | 结果 |
|---|---|
| `CURRENT_STATUS.md`、`DECISIONS.md`、`MEDIA_VALIDATION_REPORT.md`、`TASK-001-FIX_RESULT.md`、配置与代码容差 | 100/150/150 ms、符号、字段和测试数基本一致 |
| 是否把来源核对写成官方二进制完整真实性证明 | 否；明确说明 gyan.dev SHA-256 不等于官方源码 PGP/可复现构建证明 |
| 是否披露原归档已删除 | 是 |
| 是否披露 AMF 初始化失败 | 是；本次独立重现，属实 |
| 是否披露未做真实长视频测试 | 是 |
| 是否披露未做字幕 OCR | 是 |
| 是否提前写“最终验收通过” | 否；均写本地验证完成、待独立复核 |
| 是否明确复核后才能进入 TASK-002 | 是 |
| 来源脚本与文档“固定可信来源” | **不一致；脚本参数可整体覆盖，见 B-01** |
| 结果报告对 `publisher_hash_compared=true` 的使用 | 报告其他段落正确区分了历史记录和本次发布方读取，但第 6 节沿用脚本字段描述“本次运行”会造成歧义，见 B-02 |

## 12. 安全与边界

- `.venv` 仅列出 Pydantic、pytest 及轻量传递依赖；未安装 FunASR、SenseVoice、Whisper、torch/PyTorch 或 PySide6。
- `模型/` 只有 `.gitkeep`；未发现 ASR 模型或检查点。
- 未发现 `.env`、真实 `config.json`、私钥/证书文件或 secret-like 内容匹配；示例配置没有密钥，`allow_paid_api=false`。
- `src/` 没有 requests、urllib、httpx、aiohttp 或业务 HTTP URL；网络能力只在 FFmpeg 安装/来源测试脚本中。
- 项目中 `runtime/`、`.venv` 和 FFmpeg 工具目录之外没有视频/音频文件；本次只处理合成媒体。
- 用户、机器和当前进程 PATH 都不含项目 FFmpeg；没有永久环境变量修改。
- 未发现 TASK-002 文件；现有 `TASK-002` 文本均是“未执行/不得进入”的边界说明。
- `tools/ffmpeg/` 和 `runtime/` 均由 `.gitignore` 命中。
- 大于 50 MiB 的 5 个当前文件均为项目 FFmpeg 二进制或 runtime 测试硬链接，全部被 Git 忽略；没有意外未忽略大文件。
- Git 仓库仍为 0 提交、0 远程；本次未创建提交或远程仓库。
- 未删除、移动或覆盖原视频、用户文件或现有输出；未调用收费 API。

## 13. 文件哈希变化检查

### 审核前

- 记录了 `git status --porcelain=v2 --branch`：仓库无提交，已有项目项均为未跟踪；报告文件不存在。
- 使用 `rg --files -uu -g '!.git/**'` 记录当前文件清单。
- 对根配置、全部 `src/*.py`、全部 `tests/*.py`、全部文档/任务文档、工具脚本、FFmpeg 安装标记及 ffmpeg/ffprobe 二进制建立 58 文件 SHA-256 基线。

### 测试和探针后

- 58 个基线文件逐一重算，`MISMATCH_COUNT=0`。
- FFmpeg 安装标记、ffmpeg.exe 和 ffprobe.exe 也未变化。
- 新产生内容仅为 `runtime/` 下的 pytest 临时目录、合成媒体和 UTF-8 日志。

### 报告生成后最终确认

- 唯一新增的项目审核文件应为 `tasks/reports/TASK-001-FIX-R_AUDIT.md`。
- 已再次重算上述 58 个受保护文件，实际 `MISMATCH_COUNT=0`；报告文件为有效 UTF-8，最终 Git 状态没有显示源码、测试、文档、配置、脚本、安装标记或二进制发生变化。

## 14. 最终建议

**需要执行 TASK-001-FIX2**。

FIX2 只应处理来源链剩余问题：冻结生产来源/版本/哈希，隔离测试注入，并纠正同版本跳过摘要对历史比对和本次比对的区分；同时补齐对应回归测试。不要在 FIX2 中扩展 UI、ASR、模型、真实长视频或 TASK-002。
