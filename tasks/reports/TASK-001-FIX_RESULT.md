# TASK-001-FIX 完整结果报告

## 1. 任务信息和最终状态

- 任务：TASK-001-FIX｜FFmpeg 来源、编码与音画同步修复。
- 执行日期：2026-07-19（Asia/Shanghai）。
- 项目：`<PROJECT_ROOT>`。
- 范围：只处理 FFmpeg 来源/校验、Windows 混合编码、音画同步闭环；未执行 TASK-002。
- 最终状态：TASK-001-FIX 实现和本地测试完成；仍待 TASK-001-FIX-R 独立只读复核。
- 验收措辞：本报告只陈述实现和本地验证状态，不作独立复核结论。

## 2. 实际完成内容

1. 完整读取 TASK-001-FIX 指令及指定的仓库文件，先记录 Git 和文件基线。
2. 开始时更新 `docs/CURRENT_STATUS.md`，记录独立复核未通过、三个阻断项和修复进行中。
3. 只读在线复核 FFmpeg 官方下载页、官方列出的 Windows 提供方、gyan.dev 构建页面和发布方校验文本。
4. 加固便携安装脚本：固定版本、发布方 SHA-256 自动取得和三方比对、partial 下载、临时解压、原子发布、安全跳过、未知目录保护、结构化摘要。
5. 将子进程输出改为结构化解码：原始字节数、文本、编码、替换标记；成功、失败和超时路径一致。
6. 新增 UTF-8、BOM、CP936/GBK、非法字节和降级测试。
7. 新增 ffprobe JSON 同步指标、有限数检查、正负偏差、固定容差和 warnings。
8. 将同步字段接入 `ExportValidation`。
9. 关键集成测试实际生成合成媒体，测量输入，精准裁切 2.3—8.7 秒，测量输出并执行三类容差判断。
10. 在回归中发现并修复字幕烧录的 -101.333 ms 时间戳偏差；修复后为 -22.000 ms。
11. 运行完整 Schema 和媒体回归、`pip check` 与一键媒体验证。
12. 更新状态、决策、媒体报告、任务执行记录和本结果报告。

## 3. 未完成或无法验证的内容

- 没有未完成的 TASK-001-FIX 范围内实现或本地测试项。
- TASK-001-FIX-R 独立只读复核尚未执行，因此没有独立复核结论。
- 原 166,721,853-byte FFmpeg 归档已由 TASK-001 在安装成功后删除；本次没有重复下载，不能对归档重新计算哈希。本次实际重新读取发布方哈希并与原安装时记录的本地归档哈希比较。
- gyan.dev SHA-256 只能证明本地下载记录与提供方公开值一致；没有完成 FFmpeg 官方源码 PGP 到该第三方 Windows 二进制的可复现构建证明。
- 未使用真实长视频，因此长时性能、峰值资源、取消和恢复无法验证。
- AMF 仍无法实际初始化；CPU `libx264` 为已验证基线。
- 未执行字幕像素 OCR；烧录验证限于命令、路径、轨道、时长、同步和 ffprobe 可读性。

## 4. 完整修改文件清单

修改：

- `config.example.json`
- `docs/CURRENT_STATUS.md`
- `docs/DECISIONS.md`
- `docs/MEDIA_VALIDATION_REPORT.md`
- `src/liveclip/media/__init__.py`
- `src/liveclip/media/errors.py`
- `src/liveclip/media/process_runner.py`
- `src/liveclip/media/subtitles.py`
- `src/liveclip/media/validate.py`
- `tests/test_media_integration.py`
- `tests/test_media_unit.py`
- `tools/Install-FFmpeg.ps1`
- `tools/Validate-Media.ps1`

新增：

- `src/liveclip/media/sync.py`
- `tests/test_ffmpeg_install_source.py`
- `tests/test_media_sync.py`
- `tasks/TASK-001-FIX.md`
- `tasks/reports/TASK-001-FIX_RESULT.md`

已读取或核验但未修改：`.gitignore`、`tools/Run-Tests.ps1`、既有 Schema 源码与 Schema 测试、`tools/media_validation.py` 等。未修改任何 `tools/ffmpeg` 二进制。

## 5. FFmpeg 来源、版本、下载地址、大小和 SHA-256

| 项目 | 值 |
|---|---|
| 官方下载页 | <https://ffmpeg.org/download.html> |
| 官方列出的 Windows 提供方 | gyan.dev、BtbN |
| 选定提供方 | gyan.dev |
| 提供方下载页 | <https://www.gyan.dev/ffmpeg/builds/> |
| 版本 | 8.1.2 full build，Windows 64 位静态构建 |
| 直接地址 | <https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-8.1.2-full_build.7z> |
| 文件名 | `ffmpeg-8.1.2-full_build.7z` |
| 大小 | 166,721,853 bytes |
| 原下载时间 | 2026-07-18T23:53:17.497+08:00 |
| 本地归档 SHA-256 | `0fff188997a499b5382e0f66e845d4556c48c54f0113ebed4853d556dbdd7059` |
| 发布方校验地址 | <https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-8.1.2-full_build.7z.sha256> |
| 发布方 SHA-256 | `0fff188997a499b5382e0f66e845d4556c48c54f0113ebed4853d556dbdd7059` |

实际 `ffmpeg -version`：`ffmpeg version 8.1.2-full_build-www.gyan.dev`。

## 6. 发布方哈希是否实际完成比对

是，已实际完成，但需区分两个时间点：

- TASK-001 原安装时计算本地归档 SHA-256 并记录到 `.liveclip-ffmpeg-install.json`。
- TASK-001-FIX 执行时实际只读获取发布方 `.sha256` 内容，再与安装标记中的本地归档 SHA-256 比较；两者一致。
- 更新后的安装脚本对新安装强制执行“发布方值 = 固定审计值 = 本地文件值”，任一不匹配即失败。
- 本次运行安装脚本得到 `already_installed`、`downloaded_this_run=false`、`publisher_hash_compared=true`、`publisher_hash_match=true`，没有重复下载。
- 由于原归档不存在，本次没有重新计算归档哈希；这一点已在风险中披露，未虚构“本次重新哈希通过”。

## 7. 混合编码处理方案和测试结果

执行层固定为 argv 列表、二进制 stdout/stderr、`shell=False`。解码顺序：

1. 严格 UTF-8；
2. UTF-8 成功且有 BOM 时以 `utf-8-sig` 解码并记录；
3. 当前 Windows ANSI 代码页，本机 CP936；
4. 最后使用替换模式安全降级。

每一路输出记录 `raw_byte_length`、`text`、`encoding_used`、`replacement_occurred`。非零退出和超时同样保留元数据；技术日志为 UTF-8，不记录环境变量内容或凭据。

测试结果：UTF-8 中文、CP936/GBK 中文、UTF-8 BOM、ASCII + 非 UTF-8 中文字节、中文路径错误、安全替换、未知代码页降级和替换标记全部通过。

## 8. 输入与裁切后的音画同步实测数据

符号均保留方向：A/V 差为音频减视频，流时长差为音频减视频，目标差为容器减目标。

| 指标 | 输入合成媒体 | 精准裁切 2.3—8.7 s |
|---|---:|---:|
| `video_start_time` | 0.000000 s | 0.080000 s |
| `audio_start_time` | -0.021333 s | 0.018000 s |
| `av_start_offset_ms` | -21.333 ms | -62.000 ms |
| `video_duration` | 12.000000 s | 6.360000 s |
| `audio_duration` | 12.000000 s | 6.421333 s |
| `stream_duration_delta_ms` | 0.000 ms | +61.333 ms |
| `container_duration` | 12.000000 s | 6.422000 s |
| `target_duration` | 12.000000 s | 6.400000 s |
| `target_duration_delta_ms` | 0.000 ms | +22.000 ms |
| `sync_within_tolerance` | true | true |
| `duration_within_tolerance` | true | true |
| `warnings` | `[]` | `[]` |

输入首音频包 -21.333 ms 是 AAC priming/Skip Samples。裁切后首视频帧 80 ms、首音频包 18 ms，形成审核指出的约 62 ms A/V 差；“62—80 ms”已披露并解释。

## 9. 同步容差及通过或失败判断

| 判定 | 冻结容差 | 裁切实测绝对值 | 结果 |
|---|---:|---:|---|
| A/V 起始差 | <= 100 ms | 62.000 ms | 通过 |
| 音频/视频流时长差 | <= 150 ms | 61.333 ms | 通过 |
| 容器/目标时长差 | <= 150 ms | 22.000 ms | 通过 |

边界包含在内；`sync_within_tolerance` 同时要求前两项通过，`duration_within_tolerance` 要求第三项通过。缺失首 PTS、非有限数、缺轨或超限均判失败。

附加回归：旧字幕烧录初测 A/V -101.333 ms，正确失败；修复后为 -22.000 ms，流时长差 +82.667 ms，目标差 +42.667 ms，全部通过，没有放宽容差。

## 10. 全部测试命令、总数、通过、失败、跳过和耗时

最终验收命令：

| 命令 | 总数 | 通过 | 失败 | 跳过 | 耗时 |
|---|---:|---:|---:|---:|---:|
| `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Run-Tests.ps1 -ra --durations=10` | 117 | 117 | 0 | 0 | 最终 pytest 3.88 s；脚本约 5.0 s；同命令此前 4.07 s 也通过 |
| `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Validate-Media.ps1` 内强制 pytest | 18 | 18 | 0 | 0 | 整条媒体验证脚本约 4.4 s |
| `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Run-Tests.ps1 tests\test_ffmpeg_install_source.py -q --durations=10` | 5 | 5 | 0 | 0 | 脚本约 3.2 s |
| `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Run-Tests.ps1 tests\test_media_integration.py -q --durations=5` | 1 | 1 | 0 | 0 | 测试 1.45 s；脚本约 3.7 s |

`pip check` 在 Run-Tests 成功路径全部执行，最终输出 `No broken requirements found.`。

如实记录中间失败：

| 阶段 | 总数 | 通过 | 失败 | 跳过 | 原因与处理 |
|---|---:|---:|---:|---:|---|
| 编码首轮 | 29 | 27 | 2 | 0 | 实际子 Python 继承 CP936，测试误固定 UTF-8；改为核对 UTF-8 或本机 ANSI，独立 UTF-8 字节场景仍严格覆盖。 |
| 同步边界首轮 | 46 | 45 | 1 | 0 | 150 ms 浮点表示微超；加入仅 `1e-9 ms` 的舍入噪声比较。 |
| 直接集成首轮 | 1 | 0 | 1 | 0 | 直接 pytest 把 tmp 放到 C 盘，驱动器断言在媒体生成前失败；改用项目 Run-Tests 后通过。 |
| 导出同步首轮 | 47 | 46 | 1 | 0 | 字幕烧录 A/V -101.333 ms 超限；修正时间戳后 47/47 通过。 |

所有中间失败均已修复并由最终 117 项完整回归覆盖；未隐藏、未标记跳过。

## 11. 新增依赖、工具和环境变化

- 新增 Python 依赖：无。
- 新增大型依赖或模型：无。
- 新增外部工具：无；继续使用项目现有 FFmpeg/ffprobe 8.1.2、PowerShell、Python 标准库、pytest 和 Pydantic。
- 使用的新增标准库能力：`ctypes` 读取 Windows ANSI code page；未安装包。
- FFmpeg 下载：本次无；同版本安全跳过。
- 永久环境变化：无。
- 进程级环境：测试脚本临时设置 `PIP_CACHE_DIR`、`TEMP`、`TMP`、`PYTHONUTF8`、`PYTHONIOENCODING` 到 D 盘项目路径；进程结束即失效。
- 系统/用户 PATH：逐项未修改。

## 12. 安全与任务边界核验

- [x] 未安装或下载 FunASR、SenseVoice、Whisper 模型/Python 包、PyTorch、PySide6 或大型 AI 依赖。
- [x] 未调用收费 API，未写入 API Key、Token 或真实凭据。
- [x] 未操作用户真实直播视频；全部媒体是项目生成的合成样本。
- [x] 未修改系统或用户 PATH，未永久修改环境变量。
- [x] 未写 C 盘大型数据；一次空 pytest 临时目录被 D 盘断言立即阻止，未生成媒体。
- [x] 未执行 TASK-002，未开发 UI、ASR、爆点分析或完整产品功能。
- [x] 未删除用户文件、原始视频或无关文件，未覆盖已有输出。
- [x] FFmpeg 二进制继续由 `.gitignore` 忽略；测试生成物只在 `runtime/`。
- [x] 未在业务源码中新增网络客户端；网络读取只发生在安装/来源复核脚本。
- [x] 未创建远程仓库、提交或收费服务资源。

## 13. 已知问题和风险

1. 原 FFmpeg 归档已删除，本次没有重新哈希归档；依赖原安装标记记录与本次发布方值复核。
2. 发布方 SHA-256 不等于官方源码 PGP/可复现构建证明。
3. 未测试真实长视频，性能和资源峰值未知。
4. AMF 初始化仍失败，GPU 驱动链原因未处理；CPU libx264 不受影响。
5. AAC priming、25 fps 帧栅格和非整数切点使首 PTS 不会天然都是 0；当前依固定容差自动判定。
6. 未做字幕像素 OCR。
7. 仓库仍无提交，所有文件均未跟踪；无法用 Git 自动精确回退本任务修改。

## 14. 文档更新情况

- `docs/CURRENT_STATUS.md`：开始时标记修复进行中；完成后写明实现/本地测试完成、待 TASK-001-FIX-R、不得进入 TASK-002。
- `docs/DECISIONS.md`：新增来源校验链、混合编码、同步指标/符号/容差/失败条件。
- `docs/MEDIA_VALIDATION_REPORT.md`：更新来源真实状态、哈希比对、编码策略、完整同步实测、62—80 ms 解释、回归、安全和风险。
- `tasks/TASK-001-FIX.md`：新增任务执行记录。
- `tasks/reports/TASK-001-FIX_RESULT.md`：新增本 17 项完整结果报告。
- `config.example.json`：新增 100/150/150 ms 三项媒体容差示例。

## 15. 下一步建议

下一步只建议执行 TASK-001-FIX-R 独立只读复核，重点重跑：

1. 安装脚本来源字段、发布方哈希文本和同版本跳过；
2. 编码降级元数据与非法字节测试；
3. ffprobe 首帧/首包 JSON、非有限数和容差边界；
4. 关键合成媒体 2.3—8.7 秒裁切同步测试；
5. 完整 117 项回归与 `pip check`。

独立复核前只保持“实现和本地测试完成、待复核”的状态；不要自动继续 TASK-002。

## 16. 用户检查方法

在 PowerShell 中：

```powershell
Set-Location '<PROJECT_ROOT>'

# 1. 检查完整结果报告和当前状态
Get-Content .\tasks\reports\TASK-001-FIX_RESULT.md -Encoding UTF8
Get-Content .\docs\CURRENT_STATUS.md -Encoding UTF8

# 2. 验证同版本安全跳过；预期 status=already_installed、downloaded_this_run=false
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Install-FFmpeg.ps1

# 3. 完整回归与 pip check
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Run-Tests.ps1 -ra --durations=10

# 4. 合成媒体、同步和关键集成验证
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Validate-Media.ps1

# 5. 确认大二进制和 runtime 日志被忽略
git check-ignore -v .\tools\ffmpeg\bin\ffmpeg.exe
git check-ignore -v .\runtime\logs\media-validation-20260719-114016-a477df9f.json
```

预期：117 passed、0 failed、0 skipped；`No broken requirements found.`；媒体验证 `TRIM_VALID=True`、`BURN_VALID=True`；18 项强制同步/集成 pytest 通过。

## 17. 回滚方法

仓库无提交，不能安全使用 `git checkout` 或 `git reset` 自动还原。回滚前先备份当前项目，并确认没有用户在下列文件或 `runtime/` 验证目录中加入数据。

只删除本任务新增文件：

- `src/liveclip/media/sync.py`
- `tests/test_ffmpeg_install_source.py`
- `tests/test_media_sync.py`
- `tasks/TASK-001-FIX.md`
- `tasks/reports/TASK-001-FIX_RESULT.md`

再依据任务开始前备份，手工还原第 4 节“修改”列表中的文件。不要删除整个 `src/liveclip/media`、`tests`、`tools`、`runtime`、`项目`、`模型` 或项目根目录；不要删除 `tools/ffmpeg`，因为本任务没有重新安装或更改现有二进制。若没有任务开始前备份，建议保留现状并由独立复核逐文件确认，而不是执行宽范围删除。
