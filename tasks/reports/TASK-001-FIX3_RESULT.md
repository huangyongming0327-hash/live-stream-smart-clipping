# TASK-001-FIX3 完整结果报告

## 1. 任务状态

- 任务：TASK-001-FIX3｜FFmpeg 测试隔离最终修复。
- 日期：2026-07-19（Asia/Shanghai）。
- 状态：三个限定目标的实现和本地测试已完成；仍待 TASK-001-FIX3-R 最终定向只读复核。
- 验收边界：当前不宣称 TASK-001 最终验收通过，不执行或建议直接进入 TASK-002。

| 限定目标 | 结果 | 证据 |
|---|---|---|
| UNC、远程 `file:` URI 和非本地固定磁盘拒绝 | 完成 | UNC 隔离根/归档/校验文本、两个远程 Host、设备/命名管道测试通过 |
| junction/symlink 等重解析点隔离 | 完成 | 5 类 junction + 归档/校验文件 symlink 均真实创建并被拒绝，0 skipped |
| 哈希正确但归档损坏的解压失败测试 | 完成 | 三方 SHA-256 一致后由 `tar.exe` 真实非零失败，不发布且清理 |

## 2. 三个修复目标完成情况

1. 测试模式路径改为本机固定磁盘白名单；不再以 `Uri.IsFile` 作为“本地”充分条件。
2. 隔离根、ProjectRoot、资源、安装目标、标记和临时/发布路径链全部拒绝 Windows `ReparsePoint`，并在关键阶段重复检查。
3. 新增非空损坏 7z 专项，确保大小和哈希均通过后才在解压分支失败；验证失败不发布、清理完整、用户文件和真实安装不变。

完成条件实测：来源链 36/36、完整回归 148/148、媒体验证与 18 项同步/集成检查通过；0 failed、0 skipped；`pip check` 通过。当前机器只有 C、D 两个 `DriveType=Fixed` 卷，没有安全可用的实际映射网络盘，因此未创建网络映射；实现对任何非 `Fixed` 或无法确定类型的卷均关闭失败，并通过源码语义测试固定该规则。

## 3. UNC / file URI 拒绝实现

- `Resolve-LocalFixedDiskPath` 统一处理所有测试路径。
- 原始值以 `\\` 或 `//` 开头时立即拒绝，覆盖 UNC、扩展设备路径和命名管道路径，不调用 `Test-Path`、`Get-Content`、`Copy-Item` 或 `tar.exe`。
- 接受 `file:` URI时要求 `Uri.Host` 为空；`file://server/...` 和 `file://localhost/...` 均立即拒绝。本地 `file:///D:/...` 转为绝对路径后继续全部检查。
- 只接受盘符绝对路径，并用 `System.IO.DriveInfo` 要求 `DriveType=Fixed`；网络盘、可移动盘、光驱、RAM、无根卷和无法判断类型的路径全部拒绝。
- 错误包含未通过的字段名、路径、本地固定磁盘要求，以及 UNC/网络/设备/命名管道或远程 Host 被禁止的原因。

专项覆盖：UNC `TestIsolationRoot`、UNC `TestArchivePath`、UNC `TestPublisherChecksumPath`、`file://server/share/...`、`file://localhost/share/...`、`\\?\D:\...`、`\\.\pipe\...`。测试均在访问目标资源前失败，没有连接外部服务器。

## 4. 重解析点检查实现

- `Assert-NoReparsePointPath` 从路径所在卷根开始，逐个检查到目标的所有已存在组件；任一组件带 `FileAttributes.ReparsePoint` 即失败。
- `Assert-TestModeSafetyBoundary` 覆盖隔离根、哨兵、ProjectRoot、归档、校验文本、`tools\ffmpeg`、ffmpeg/ffprobe、安装标记、下载目录、临时归档、唯一 partial 和唯一解压目录。
- 首次验证后，在临时目录创建、校验文本读取、归档复制、partial 移动、解压目录创建、解压完成、标记写入和原子发布前后重复检查。
- `Assert-NoReparsePointTree` 拒绝解压树内部的 junction/symlink 等重解析项；测试清理函数在递归删除前再次验证，遇到不可信重解析点时宁可拒绝递归清理，也不跟随它删除目标内容。
- 本阶段采用“直接拒绝重解析点”，没有实现复杂的最终物理路径跟随解析。

本机真实执行并通过的拒绝场景：隔离根 junction、ProjectRoot junction 指向真实项目、资源目录 junction 指向根外、目标 junction 指向真实 `tools\ffmpeg`、临时下载目录 junction 指向根外、归档 symlink 指向根外、校验文本 symlink 指向根外。Windows 文件 symlink 权限可用，因此没有跳过补充场景。

## 5. 解压失败专项实测

- 测试资源：非空文本字节，明确不是有效 7z。
- 测试归档实际 SHA-256、校验文本中的 SHA-256 和 `TestExpectedSha256` 完全一致。
- 结构化失败摘要确认：`publisher_hash_checked_this_run=true`、`publisher_hash_match_this_run=true`、`archive_hash_recomputed_this_run=true`，证明未在大小、发布方哈希或本地哈希阶段提前失败。
- `tar.exe` 实际返回非零，脚本报告 `Archive extraction failed with exit code ...`，安装进程退出非零。
- 断言结果：没有稳定 `tools\ffmpeg`，项目内没有安装标记，没有伪完整目录；`.partial`、临时归档和 `extract-*` 均不存在；预存中文用户文件内容不变；原测试资源未被删除。
- 真实项目安装标记、ffmpeg.exe 和 ffprobe.exe SHA-256 前后完全一致。

## 6. 真实安装哈希保护

| 对象 | 开始前 SHA-256 | 完成后 SHA-256 | 结果 |
|---|---|---|---|
| `tools/ffmpeg/.liveclip-ffmpeg-install.json` | `7d624c125324dc9f3f7f556a8d35de6261da7b4b1d57132708c9835ee1ec2353` | 相同 | 未修改 |
| `tools/ffmpeg/bin/ffmpeg.exe` | `ad8f211bc894755e0061c55ab280ae00e8d3d4f15a8cc4372b24cfa247b5942e` | 相同 | 未修改 |
| `tools/ffmpeg/bin/ffprobe.exe` | `9df3b0b5275e830961df6d94e1f7a71121a7abd5ff708e9fec8a0b6084a55015` | 相同 | 未修改 |

每个 junction/symlink 逃逸测试都在调用前后重算上述三项真实 SHA-256。没有运行默认生产安装命令，没有下载或重新安装 FFmpeg。

## 7. 来源链专项测试

命令：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Run-Tests.ps1 tests\test_ffmpeg_install_source.py -ra --durations=10
```

最终结果：36 passed、0 failed、0 skipped；pytest 24.28 秒；随后 `pip check` 输出 `No broken requirements found.`。

除 FIX3 新增场景外，原有生产常量冻结、五类覆盖参数拒绝、测试开关、来源摘要、旧标记、同版本时态、无效/不匹配哈希、空/截断归档、未知目录、预存用户文件和 PATH 不变测试全部保留并通过。

如实记录：第一次专项为 32 passed、4 failed，第二次为 33 passed、3 failed；失败原因都是 Windows PowerShell 错误记录自动换行把英文断言字符串拆开，实际拒绝行为已触发。改为校验稳定错误字段后，第三次 36/36 通过；没有跳过或掩盖安全逻辑失败。

## 8. 完整回归

| 验证 | 结果 |
|---|---|
| `Run-Tests.ps1 -ra --durations=10` | 148 passed、0 failed、0 skipped；pytest 26.31 秒 |
| `pip check` | `No broken requirements found.` |
| `Validate-Media.ps1` | 退出 0；强制能力、合成端到端流程通过 |
| 媒体关键值 | `TRIM_VALID=True`、`BURN_VALID=True` |
| 同步/集成 | 17 项同步单元 + 1 项关键 FFmpeg 集成，全部通过 |

最新验证日志：

- `runtime/logs/media-validation-20260719-150704-ddfeeabd.json`
- `runtime/logs/ffmpeg-capabilities-20260719-150704-267.txt`

本次没有修改 `src/liveclip/media/`、`tools/Validate-Media.ps1`、媒体测试、混合编码处理或 100/150/150 ms 同步容差。`Validate-Media.ps1` SHA-256 仍为 `69b0cc...039c`，`Run-Tests.ps1` 仍为 `0a0c54...054f`。

## 9. 修改文件清单

修改：

- `tools/Install-FFmpeg.ps1`
- `tests/test_ffmpeg_install_source.py`
- `docs/CURRENT_STATUS.md`
- `docs/DECISIONS.md`
- `docs/MEDIA_VALIDATION_REPORT.md`

新增：

- `tasks/TASK-001-FIX3.md`
- `tasks/reports/TASK-001-FIX3_RESULT.md`

没有修改任何媒体、SRT、字幕烧录、混合编码、音画同步实现、依赖锁文件或 FFmpeg 二进制。

关键来源文件 SHA-256：

| 文件 | 开始前 | 完成后 |
|---|---|---|
| `tools/Install-FFmpeg.ps1` | `ec087b43794b191094909365d7c704086e4affb783222570e225a3b30d402bde` | `0180cbc3e89e48f49a0130136f681ccfd7178bf522a840ce37564a466a6ebb12` |
| `tests/test_ffmpeg_install_source.py` | `e9256598569172d1c0c000a78a1bea3319e24eba89c10725bce0ebf0ffd7728f` | `c648ed00bcb3d312c3df5290c27422f1ef3136f484faa6473a50d13b01305043` |

仓库仍无提交，全部项目项仍为未跟踪，因此不能用 Git diff 精确区分历史内容；上述允许清单和任务前后哈希是本次变化证据。

## 10. 环境变化

- 新增 Python 包：无；依赖安装：无。
- ASR 模型、大型 AI 依赖：无。
- FFmpeg 下载/重新安装：无。
- 收费 API、凭据、远程仓库：无。
- 系统/用户 PATH 和永久环境变量：无变化。
- 测试只在子进程使用项目 D 盘 `runtime/cache` 与 `runtime/temp`；合成媒体与日志只在既有 `runtime/`。

PATH SHA-256 前后均为：Machine `015ee9c6...a5030b8`、User `3dd925d5...c5e30e98`、Process `e59a4902...69c9bd23`；三者均不含项目 FFmpeg。

## 11. 安全边界

- 未访问 UNC 或网络共享；所有 UNC/远程 URI 用例均在任何目标资源访问前失败。
- 未下载或重新安装 FFmpeg，未修改真实标记和二进制。
- 未操作真实直播视频；媒体验证只使用 D 盘 `runtime/` 合成样本。
- 未安装 ASR 模型、PyTorch、FunASR、SenseVoice、Whisper、PySide6 或其他大型依赖。
- 未调用收费 API，未写密钥，未修改系统 PATH 或永久环境变量。
- 未删除用户文件；专项明确验证预存中文用户文件保留。
- 未执行 TASK-002，任务目录中不存在 TASK-002 文件；未创建提交或 remote。

## 12. 已知限制

1. 当前机器只有 C、D 两个固定磁盘，没有安全可用的实际映射网络盘。本任务没有为测试而连接共享或创建网络映射；`DriveInfo` 固定盘白名单保证任何 `DriveType` 非 `Fixed` 的映射盘都会被拒绝，但该分支缺少本机真实网络盘实测。
2. 重解析点拒绝和关键阶段复检显著降低逃逸风险，但不宣称消除所有 Windows 文件系统 TOCTOU 竞态、内核级替换或恶意管理员攻击面。
3. pytest 自身会在被 Git 忽略的 `runtime/temp/pytest-*` 下创建名称含 `current` 的重解析别名；FIX3 自建 junction/symlink 均在用例结束时移除，安装脚本若收到这些 pytest 别名也会按策略拒绝。
4. gyan.dev SHA-256、AMF、真实长视频性能和字幕像素 OCR 是既有边界，本任务没有扩展处理。
5. TASK-001-FIX3-R 尚未执行，因此当前结论仅为实现与本地验证完成。

## 13. 文档更新

- `CURRENT_STATUS.md`：记录 FIX3 实现/本地测试完成、待 FIX3-R、不得提前通过 TASK-001 或进入 TASK-002。
- `DECISIONS.md`：新增固定磁盘白名单、远程 URI/网络盘拒绝、重解析点拒绝、关键阶段复检和解压失败不发布决策。
- `MEDIA_VALIDATION_REPORT.md`：补充 FIX3 隔离策略、36/148 测试结果、最新合成媒体验证和当前个人本地项目适用范围；明确不宣称覆盖全部 Windows 文件系统攻击面。
- `TASK-001-FIX3.md`：记录任务边界、开始基线、实现、测试和下一步。

## 14. 下一步仅建议 FIX3-R

下一步只建议执行 TASK-001-FIX3-R 最终定向只读复核，只检查：

1. UNC / 远程 `file:` URI 和非固定盘拒绝；
2. 隔离根、ProjectRoot、资源、目标和临时路径重解析点隔离；
3. 匹配哈希损坏归档解压失败不发布且清理；
4. 148 项完整回归及媒体验证无回归。

复核前不得写 TASK-001 最终验收通过；停止，不执行 TASK-002。

## 15. 用户检查方法

```powershell
Set-Location '<PROJECT_ROOT>'

# 查看状态与完整结果
Get-Content .\docs\CURRENT_STATUS.md -Encoding UTF8
Get-Content .\tasks\reports\TASK-001-FIX3_RESULT.md -Encoding UTF8

# 完全离线的来源链专项
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Run-Tests.ps1 tests\test_ffmpeg_install_source.py -ra --durations=10

# 完整回归与合成媒体验证
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Run-Tests.ps1 -ra --durations=10
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Validate-Media.ps1

# 只读核对真实安装哈希
Get-FileHash .\tools\ffmpeg\.liveclip-ffmpeg-install.json -Algorithm SHA256
Get-FileHash .\tools\ffmpeg\bin\ffmpeg.exe -Algorithm SHA256
Get-FileHash .\tools\ffmpeg\bin\ffprobe.exe -Algorithm SHA256
```

预期：来源链 36 passed；完整回归 148 passed；均 0 failed、0 skipped；`pip check` 通过；媒体验证显示 `TRIM_VALID=True`、`BURN_VALID=True` 和 18 项同步/集成通过。不要为复核重复运行默认生产安装命令。

## 16. 回滚方法

仓库没有提交，不能安全使用 `git checkout`、`git reset` 或宽范围删除。回滚前先备份项目，并确认没有用户后续编辑：

1. 从 TASK-001-FIX3 开始前的可信备份恢复 `tools/Install-FFmpeg.ps1`、`tests/test_ffmpeg_install_source.py`、`docs/CURRENT_STATUS.md`、`docs/DECISIONS.md` 和 `docs/MEDIA_VALIDATION_REPORT.md`。
2. 仅在确认不再需要 FIX3 记录时，单独移除 `tasks/TASK-001-FIX3.md` 和 `tasks/reports/TASK-001-FIX3_RESULT.md`。
3. 不删除 `tools/ffmpeg`、`src/liveclip/media`、`runtime`、`项目`、`模型`、原视频或整个仓库；本任务没有修改真实 FFmpeg 安装，无需回滚二进制。
4. 没有可信任务前备份时，保留现状并执行 FIX3-R 只读复核，不尝试手工猜测旧代码或批量删除文件。

本任务至此停止，未执行 TASK-002。
