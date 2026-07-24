# TASK-001 / TASK-001-FIX / TASK-001-FIX2 / TASK-001-FIX3 媒体技术验证报告

## 1. 状态与结论

- TASK-001 的独立只读复核未通过，阻断项为 FFmpeg 来源校验链、Windows 混合编码处理和音画同步自动验收闭环。
- TASK-001-FIX-R 确认混合编码和音画同步已修复，但来源链仍有两个阻断问题；这两个问题由 FIX2 修复。TASK-001-FIX2-R 随后发现测试模式的 UNC/远程 `file:` URI、重解析点隔离缺口和解压失败专项证据缺口，因此结论仍不通过。TASK-001-FIX3 已完成这三项限定实现和本地测试，仍待 TASK-001-FIX3-R 最终定向只读复核；不得直接进入 TASK-002。
- 验证只使用项目在 D 盘 `runtime/` 生成的 12 秒合成 H.264/AAC 媒体，没有读取、修改、上传或删除用户真实直播视频。
- FIX3 来源链专项：36 passed、0 failed、0 skipped；pytest 24.28 秒；junction 和两个文件 symlink 均在本机真实创建并被拒绝。
- FIX3 最终完整回归：148 passed、0 failed、0 skipped；pytest 26.31 秒；`pip check` 为 `No broken requirements found.`。

## 2. FFmpeg 来源链

| 项目 | 记录 |
|---|---|
| FFmpeg 官方下载页 | <https://ffmpeg.org/download.html> |
| 官方页列出的 Windows 构建提供方 | gyan.dev、BtbN |
| 实际选择提供方 | gyan.dev |
| 实际下载页面 | <https://www.gyan.dev/ffmpeg/builds/> |
| 固定版本 / 构建 | 8.1.2 release full，Windows 64 位，静态，GPLv3 |
| 直接下载 URL | <https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-8.1.2-full_build.7z> |
| 文件名 | `ffmpeg-8.1.2-full_build.7z` |
| 下载文件大小 | 166,721,853 bytes（约 159.00 MiB） |
| 原下载完成时间 | 2026-07-18 23:53:17.497 +08:00 |
| 本地归档 SHA-256 | `0fff188997a499b5382e0f66e845d4556c48c54f0113ebed4853d556dbdd7059` |
| 发布方校验 URL | <https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-8.1.2-full_build.7z.sha256> |
| 发布方 SHA-256 | `0fff188997a499b5382e0f66e845d4556c48c54f0113ebed4853d556dbdd7059` |
| 安装路径 | `tools/ffmpeg`（二进制被 Git 忽略） |

来源和时态必须分开理解：

- 来源链验证：已复核。FFmpeg 官方下载页当前列出 gyan.dev 和 BtbN；实际选择和直接 URL 均属于 gyan.dev。
- 本地哈希计算：已在原下载完成时执行并写入安装标记，值见上表。
- 历史发布方哈希比对：TASK-001 原安装标记记录 `sha256_verified_against_publisher=true`；TASK-001-FIX-R 也曾独立只读取得发布方文本并确认当时一致。这些是历史证据，不是 FIX2 本次脚本运行的联网动作。
- FIX2 本次同版本实测采用完全离线安全跳过，实际字段为：`publisher_hash_verified_at_install=true`、`publisher_hash_checked_this_run=false`、`publisher_hash_match_this_run=null`、`archive_hash_recomputed_this_run=false`、`archive_downloaded_this_run=false`。
- 现有旧标记没有 `publisher_sha256`，因此 FIX2 摘要保持 `publisher_sha256=null`，只保留历史 `installed_archive_sha256=0fff...7059`，不伪造未知值。
- 本次未重复下载：脚本验证现有标记、二进制和版本后返回 `already_installed`。原归档已在 TASK-001 安装成功后删除，本次没有重新计算归档哈希，也没有重新安装。
- 不可确认：发布方校验值是发布方公开的 SHA-256，不等同于 FFmpeg 官方源码 PGP 签名；该 Windows 第三方二进制没有在本项目内进行可复现构建比对。

## 3. 安装脚本验收

`tools/Install-FFmpeg.ps1` 当前行为：

- 生产提供方、页面、8.1.2 full build、归档名、下载 URL、校验 URL 和固定 SHA-256 均为脚本内常量；生产参数列表不能覆盖这些值，非 gyan.dev URL和本地归档不能注入生产模式。
- 离线测试注入只能显式开启 `-TestMode`，只接受本机固定磁盘上的绝对路径或 Host 为空的本地 `file:` URI；隔离根需有哨兵文件。UNC、远程 `file:` URI、网络/非固定/未知类型驱动器、设备/命名管道路径、隔离根外资源和真实项目 `tools\ffmpeg` 目标均被拒绝。
- 测试模式从卷根开始检查隔离根、ProjectRoot、资源、安装目标、标记和临时路径的所有已存在组件；发现 junction、symlink、mount point 或其他 `ReparsePoint` 即失败。临时目录创建、资源复制、解压和发布关键阶段会重复检查，解压树也不得包含重解析点。
- 测试摘要如实写 `mode=test`、`selected_provider=test_fixture`、`source_type=local_test_resource`，测试模式不能写入或覆盖真实安装标记。
- 发布方 SHA-256 必须是 64 位十六进制，并必须与固定审计值一致；本地归档必须再与发布方值一致。
- 下载先写唯一 `.partial`；只有下载调用完整返回后才移动为临时归档。
- 解压到项目 D 盘的唯一临时目录，版本、ffprobe、libx264 和 libass 能力通过后才同卷移动到稳定目录。
- 哈希不匹配、空文件、解压失败或能力缺失不会形成稳定安装；本次下载的坏归档会定点清理。
- 已安装同版本时完全离线安全跳过；不读发布方文本、不下载、不重新哈希已删除的原归档。未知或不完整现有目录立即停止，不覆盖任何内容。
- 不运行安装器、不查询或修改系统 PATH；成功、跳过和操作阶段失败输出 `LIVECLIP_FFMPEG_SUMMARY` JSON 摘要，新字段明确区分历史验证与本次动作。

FIX2 离线来源链测试 21 项全部通过。FIX3 扩展后为 36 项全部通过，新增覆盖 UNC 隔离根、UNC 归档/校验文本、`file://server`、`file://localhost`、设备/命名管道路径、固定磁盘判定语义、隔离根/ProjectRoot/资源/目标/临时目录 junction、归档与校验文本 symlink，以及匹配哈希损坏归档的真实解压失败。

匹配哈希损坏归档测试使用非空、非有效 7z 的本地字节，并让校验文本、`TestExpectedSha256` 和归档实际 SHA-256 三者完全一致。实测已通过大小和哈希检查，由 `tar.exe` 返回非零而进入解压失败分支；没有形成 `tools\ffmpeg`、没有写任何安装标记，partial、临时归档和 `extract-*` 均清理，预存中文用户文件保留，真实安装标记与两个二进制哈希不变。

## 4. Windows 混合编码策略

统一命令执行层继续使用 `subprocess.run` 参数列表、二进制 stdout/stderr、`shell=False`、超时和退出码。每一路输出解码顺序为：

1. 严格 UTF-8；
2. 若严格 UTF-8 成功且检测到 BOM，则以 `utf-8-sig` 去除 BOM 并记录该编码；
3. UTF-8 失败后使用 Windows 当前 ANSI 代码页，本机为 CP936；
4. ANSI 严格解码也失败时使用替换模式，设置 `replacement_occurred = true`，不丢失整段结果。

`DecodedProcessOutput` 为 stdout/stderr 分别记录：

- `raw_byte_length`；
- `text`；
- `encoding_used`；
- `replacement_occurred`。

成功、非零退出和超时均保留结构化解码元数据。日志使用 UTF-8，不写环境变量内容、密钥或凭据。

编码离线测试全部通过，覆盖 UTF-8 中文、CP936/GBK 中文、UTF-8 BOM、ASCII 加非 UTF-8 中文字节、中文路径错误、安全替换降级、未知代码页降级和替换标记。

## 5. 同步定义与符号

- `video_start_time`：ffprobe JSON 中首个视频帧的 `best_effort_timestamp_time`，缺失时尝试帧 `pts_time`。
- `audio_start_time`：首个音频包 `pts_time`，缺失时尝试 `dts_time`。
- `av_start_offset_ms = (audio_start_time - video_start_time) * 1000`；负值表示音频早于视频。
- `stream_duration_delta_ms = (audio_duration - video_duration) * 1000`。
- `target_duration_delta_ms = (container_duration - target_duration) * 1000`。
- ffprobe 只使用 JSON / 机器可解析输出，不解析面向人的普通日志；缺失 PTS、缺轨和 NaN/Infinity 均拒绝。

## 6. 输入同步实测

本次样本：`runtime/temp/媒体 测试/20260719-114016-a477df9f/输入 视频.mp4`。

| 指标 | 实测 |
|---|---:|
| 首视频帧 PTS | 0.000000 s |
| 首音频包 PTS | -0.021333 s |
| 输入 A/V 起始差（音频－视频） | -21.333 ms |
| 视频流时长 | 12.000000 s |
| 音频流时长 | 12.000000 s |
| 流时长差（音频－视频） | 0.000 ms |
| 容器时长 | 12.000000 s |
| 目标时长 | 12.000000 s |
| 目标时长差 | 0.000 ms |
| 同步判断 | 通过 |

首音频包为负值来自 AAC 编码器预滚/priming，ffprobe 同时报告 Skip Samples；这里保留真实首包 PTS，没有用流级 `start_time=0` 隐藏它。

## 7. 精准裁切后同步实测

- 请求：2.3—8.7 秒；目标 6.4 秒。
- 编码：CPU `libx264` + AAC；中文与空格路径；一条视频轨和一条音频轨。
- 发布：同目录唯一临时文件完成后原子发布；已有输出会拒绝，不覆盖。

| 指标 | 实测 |
|---|---:|
| 首视频帧 PTS | 0.080000 s |
| 首音频包 PTS | 0.018000 s |
| 输出 A/V 起始差（音频－视频） | -62.000 ms |
| 视频流时长 | 6.360000 s |
| 音频流时长 | 6.421333 s |
| 流时长差（音频－视频） | +61.333 ms |
| 容器时长 | 6.422000 s |
| 目标时长 | 6.400000 s |
| 目标时长差（容器－目标） | +22.000 ms |
| `sync_within_tolerance` | `true` |
| `duration_within_tolerance` | `true` |
| `warnings` | `[]` |

## 8. 冻结容差与判定

| 判定项 | 容差 | 实测绝对值 | 结果 |
|---|---:|---:|---|
| 裁切后 A/V 起始差 | <= 100 ms | 62.000 ms | 通过 |
| 音频/视频流时长差 | <= 150 ms | 61.333 ms | 通过 |
| 容器/目标时长差 | <= 150 ms | 22.000 ms | 通过 |

边界值包含在内；只为浮点舍入噪声使用 `1e-9 ms` 的数值比较容差，不放宽业务阈值。`sync_within_tolerance` 同时要求前两项通过，`duration_within_tolerance` 要求第三项通过。

## 9. 已观察到的 62—80 ms 差异

独立审核指出的约 62—80 ms 差异已明确披露：裁切后首视频帧位于 80 ms，首音频包位于 18 ms，因此音频相对视频早 62 ms。两者是同一组首时间戳的“绝对位置”和“相互差值”，不是两个互相矛盾的测量。其来源与 25 fps 视频帧栅格、2.3 秒非整数切点、重编码时间戳归零策略和 AAC 包边界/priming 有关。本任务不把它写成 0，也不无限放宽容差；实测 62 ms 在冻结的 100 ms 起始差容差内。

## 10. 字幕烧录同步回归

首次把同步门禁接入所有导出时，旧烧录命令实测 A/V 起始差为 -101.333 ms，刚超出 100 ms，测试按规则失败。随后仅对合成样本验证并修复：视频与音频分别用 `setpts/asetpts=PTS-STARTPTS` 重置时间戳，并使用 `-avoid_negative_ts make_zero`。

最终烧录输出实测：首视频帧 0.080 s、首音频包 0.058 s、A/V 差 -22.000 ms；视频流 6.360 s、音频流 6.442667 s、流时长差 +82.667 ms；容器 6.442667 s、目标差 +42.667 ms。三项均在同一容差内，字幕烧录回归通过。

## 11. 媒体与 Schema 回归

- FFmpeg/ffprobe 8.1.2、H.264、AAC、libx264、SRT、WAV、PCM s16le、subtitles/ass/libass 强制能力通过。
- 视频探测、16 kHz 单声道 WAV、精准裁切、SRT 毫秒重计时、中文字幕烧录、导出校验和中文空格路径通过。
- 合成源 1,252,579 bytes；WAV 384,420 bytes；精准裁切 621,265 bytes；烧录输出 596,314 bytes。
- 全部既有 Timeline、CurrentAnalysis、ReviewCurrent Schema 测试保留并通过。
- 构建仍列出 `h264_amf` / `hevc_amf`；此前本机初始化失败，继续作为非阻断限制，未更新驱动。

## 12. 测试命令与结果

1. `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Run-Tests.ps1 -ra --durations=10`
   - FIX3 最终运行 148 passed，0 failed，0 skipped；pytest 26.31 秒。
   - `pip check`：通过，`No broken requirements found.`。
2. `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Validate-Media.ps1`
   - 强制能力探针全部通过；`TRIM_VALID=True`、`BURN_VALID=True`。
   - 17 项同步单元测试 + 1 项关键 FFmpeg 集成测试全部通过，关键集成测试未跳过；整条脚本约 4.4 秒。
3. `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Run-Tests.ps1 tests\test_ffmpeg_install_source.py -ra --durations=10`
   - 36 passed、0 failed、0 skipped；pytest 24.28 秒；`pip check` 通过；全部使用 D 盘本地隔离资源，没有访问 UNC 或网络共享。
4. FIX3 未运行默认生产安装命令；真实安装保护通过前后 SHA-256 比对完成，不以重复调用安装入口作为验证手段。

FIX3 最新一键验证日志：

- `runtime/logs/media-validation-20260719-150704-ddfeeabd.json`
- `runtime/logs/ffmpeg-capabilities-20260719-150704-267.txt`

它们均在 `.gitignore` 覆盖的 D 盘 `runtime/` 下。

## 13. 结构化媒体校验字段

有效音视频导出的 `ExportValidation` 已包含：`video_start_time`、`audio_start_time`、`av_start_offset_ms`、`video_duration`、`audio_duration`、`stream_duration_delta_ms`、`container_duration`、`target_duration`、`target_duration_delta_ms`、`sync_within_tolerance`、`duration_within_tolerance` 和 `warnings`。可用数值全部经过有限数检查；不可探测媒体返回 `None` 和结构化错误，不产生 NaN/Infinity。

## 14. 安全与任务边界

- 未安装或下载 FunASR、SenseVoice、Whisper 模型/Python 包、PyTorch、PySide6 或其他大型 AI 依赖。
- 未调用收费 API，未写入 API Key，未新增业务网络客户端。
- 未操作用户真实直播视频；只处理合成样本。
- FIX3 没有修改 `src/liveclip/media/`、混合编码、音画同步容差或编码策略；媒体验证只回归既有合成样本。
- FIX3 没有访问 UNC 或网络共享，没有下载或重新安装 FFmpeg；测试只在 D 盘 pytest 隔离目录和既有 `runtime/` 内创建小型资源。
- 未修改用户或系统 PATH，未永久修改环境变量；测试脚本只设置子进程级 D 盘缓存和临时目录。
- 未写 C 盘大型数据；一次误用直接 pytest 在 C 盘创建空的 pytest 临时目录后被驱动器断言立即终止，未生成媒体，后续全部使用项目测试脚本。
- 未执行 TASK-002，未开发 UI、ASR、爆点分析，未创建远程仓库或提交。
- 未删除原视频或用户文件；FFmpeg 二进制继续被 Git 忽略，测试生成物只在 `runtime/`。

## 15. 尚存风险与下一步

1. 原 FFmpeg 归档已在 TASK-001 成功安装后删除；本次可复核安装标记并重新读取发布方 SHA-256，但没有重新下载和重新计算归档哈希。
2. gyan.dev SHA-256 证明下载内容与提供方公开值一致，不等于 FFmpeg 官方源码 PGP 签名或可复现构建证明。
3. 未测试真实长视频，长时性能、峰值资源、取消和恢复仍未知。
4. AMF 仍不可用；CPU `libx264` 是当前稳定基线。
5. 未做字幕像素 OCR；烧录验证范围仍是滤镜成功、路径、轨道、时长、同步和 ffprobe 可读性。
6. FIX3 的隔离策略面向当前个人本地 Windows 项目：固定磁盘、已存在路径组件和解压树重解析点拒绝。它降低但不宣称覆盖所有 Windows 文件系统攻击面或消除并发替换竞态；没有为测试构造真实映射网络盘，而是使用 `DriveInfo` 固定盘白名单并对 UNC/远程 URI 做无网络访问的行为测试。

下一步只建议执行 TASK-001-FIX3-R 最终定向只读复核，只核对 UNC/远程 `file:` URI 拒绝、重解析点隔离、解压失败不发布和完整回归无回归；不得自动继续 TASK-002。
