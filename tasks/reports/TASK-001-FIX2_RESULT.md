# TASK-001-FIX2 完整结果报告

## 1. 任务状态

- 任务：TASK-001-FIX2｜FFmpeg 来源链最终修复。
- 日期：2026-07-19（Asia/Shanghai）。
- 范围：只修复 FFmpeg 生产来源冻结、测试注入隔离和安装摘要时态语义。
- 状态：实现和本地测试完成；仍待 TASK-001-FIX2-R 独立只读复核。
- 验收边界：复核前不写 TASK-001 最终验收通过，不执行或建议直接进入 TASK-002。

## 2. 原两个阻断问题逐项修复

| FIX-R 阻断 | 修复 | 本地证据 |
|---|---|---|
| 生产调用者可覆盖 URL、校验 URL、固定哈希、版本和归档名，却仍声明 gyan.dev | 删除五类生产覆盖参数；生产值全部改为脚本内受审计常量；测试来源只在显式隔离模式出现 | 五类参数逐项拒绝、非 gyan.dev URL拒绝、本地生产注入拒绝、生产摘要固定来源测试通过 |
| 同版本分支把历史安装记录误报为本次发布方比对 | 删除歧义字段，分离历史验证和本次动作；同版本采用完全离线安全跳过 | 实测 `checked_this_run=false`、`match_this_run=null`、未下载、未重算，且旧标记/二进制哈希不变 |

## 3. 生产来源冻结实现

生产入口固定为：

- 提供方：`gyan.dev`；页面：`https://www.gyan.dev/ffmpeg/builds/`；
- 版本/构建：`8.1.2` / `full_build`，Windows 64 位静态构建；
- 归档：`ffmpeg-8.1.2-full_build.7z`；
- 下载 URL：`https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-8.1.2-full_build.7z`；
- 校验 URL：同地址加 `.sha256`；
- 固定 SHA-256：`0fff188997a499b5382e0f66e845d4556c48c54f0113ebed4853d556dbdd7059`。

上述值不在参数列表中。`DownloadUri`、`PublisherChecksumUri`、`ExpectedSha256`、`ExpectedVersion` 和 `ArchiveFileName` 传参均由 PowerShell 参数绑定直接拒绝；`ProjectRoot` 只能改变目标项目根，不能改变生产来源。

## 4. 测试模式隔离实现

- 必须显式传入 `-TestMode`；测试专用参数在普通模式下被拒绝。
- 必须提供绝对 `TestIsolationRoot`，且根目录包含 `.liveclip-ffmpeg-test-root` 哨兵。
- `ProjectRoot`、本地归档和本地校验文本必须位于隔离根内。
- 只接受本地绝对路径或 `file:` URI；任何远程 URL 均在访问前拒绝。
- 真实项目 `tools\ffmpeg` 不能作为测试目标；测试前后真实安装标记哈希一致。
- 测试摘要固定如实写 `mode=test`、`selected_provider=test_fixture`、`source_type=local_test_resource`，不会冒充 gyan.dev 生产下载。

## 5. 安装标记和摘要新字段

新安装标记明确写入 `publisher_sha256`、`publisher_hash_verified_at_install`、`installed_archive_sha256`、`installed_archive_size`、`installed_from_url`、`provider`、`version` 和 `installed_at`，同时保留必要旧字段以便兼容。

摘要使用：

- `publisher_hash_verified_at_install`：历史安装标记是否记录过发布方比对；
- `publisher_hash_checked_this_run`：本次是否实际读取校验文本；
- `publisher_hash_match_this_run`：仅本次实际读取后才为布尔值，未读取为 `null`；
- `archive_hash_recomputed_this_run`：本次是否对归档文件重新计算 SHA-256；
- `archive_downloaded_this_run`：本次是否通过生产远程来源下载归档。

现有旧标记只含 `sha256` 和 `sha256_verified_against_publisher`。兼容逻辑把它们分别解释为历史安装归档哈希和历史安装验证状态；缺失的 `publisher_sha256` 保持 `null`，没有伪造或迁移旧标记。

## 6. 同版本跳过实测 JSON

默认生产调用在现有安装上实测退出 0，且标记与二进制哈希不变：

```json
{
  "status": "already_installed",
  "mode": "production",
  "source_type": "remote_https",
  "selected_provider": "gyan.dev",
  "direct_download_url": "https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-8.1.2-full_build.7z",
  "publisher_checksum_url": "https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-8.1.2-full_build.7z.sha256",
  "archive_file_name": "ffmpeg-8.1.2-full_build.7z",
  "installed_archive_sha256": "0fff188997a499b5382e0f66e845d4556c48c54f0113ebed4853d556dbdd7059",
  "publisher_sha256": null,
  "fixed_audited_sha256": "0fff188997a499b5382e0f66e845d4556c48c54f0113ebed4853d556dbdd7059",
  "publisher_hash_verified_at_install": true,
  "publisher_hash_checked_this_run": false,
  "publisher_hash_match_this_run": null,
  "archive_hash_recomputed_this_run": false,
  "archive_downloaded_this_run": false,
  "version": "8.1.2",
  "build": "full_build",
  "system_path_modified": false
}
```

本分支未创建 `runtime/temp/ffmpeg-download`，证明没有进入下载或归档处理路径。

## 7. 来源链专项测试

命令：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Run-Tests.ps1 tests\test_ffmpeg_install_source.py -ra --durations=10
```

最终结果：21 passed、0 failed、0 skipped；pytest 7.50 秒；`pip check` 通过。

覆盖生产常量、五类覆盖参数逐项拒绝、本地/非 gyan.dev 来源拒绝、预存本地归档拒绝且原文件保留、显式测试开关、远程资源拒绝、隔离根边界、真实目标保护、测试摘要真实性、旧标记兼容、离线同版本五字段、无效发布方哈希、固定值不匹配、空/截断归档、未知目录和 PATH 不变。

如实记录中间结果：首次专项为 20 passed、1 个收集错误，原因是辅助函数误以 `test_` 命名而被 pytest 当成测试；重命名后专项全部通过。该错误不是安装逻辑失败，也未被跳过。

## 8. 完整回归结果

| 验证 | 结果 |
|---|---|
| `Run-Tests.ps1 -ra --durations=10` | 133 passed、0 failed、0 skipped；pytest 9.55 秒 |
| `pip check` | `No broken requirements found.` |
| `Validate-Media.ps1` | 强制 FFmpeg 能力、合成端到端媒体流程通过；`TRIM_VALID=True`、`BURN_VALID=True` |
| 强制同步/集成 pytest | 18 passed、0 failed、0 skipped（17 项同步单元 + 1 项关键集成） |

媒体回归继续使用 `runtime/` 生成的 12 秒合成 H.264/AAC 样本，没有读取或修改真实直播视频。既有混合编码、精准裁切、SRT、中文字幕烧录、中文空格路径和 100/150/150 ms 同步门禁均通过。

## 9. 修改文件清单

修改：

- `tools/Install-FFmpeg.ps1`
- `tests/test_ffmpeg_install_source.py`
- `docs/CURRENT_STATUS.md`
- `docs/DECISIONS.md`
- `docs/MEDIA_VALIDATION_REPORT.md`

新增：

- `tasks/TASK-001-FIX2.md`
- `tasks/reports/TASK-001-FIX2_RESULT.md`

没有修改 `src/liveclip/media/`、`tools/Validate-Media.ps1`、`tools/Run-Tests.ps1`、配置、依赖锁文件或 FFmpeg 二进制。

任务开始前关键 SHA-256 基线及收尾结果：

| 文件 | 开始前 SHA-256 | 收尾状态/最终 SHA-256 |
|---|---|---|
| `tools/Install-FFmpeg.ps1` | `a17ee40b6649f5bedec93ca9e6cfe0b9f2255e6a603c6765c354e87b7360a749` | 已按任务修改；`ec087b43794b191094909365d7c704086e4affb783222570e225a3b30d402bde` |
| `tests/test_ffmpeg_install_source.py` | `33db14638caab4b1b995caee7ac0bc63cf4045ac156eb5818fdf35d6a93a2f68` | 已按任务修改；`e9256598569172d1c0c000a78a1bea3319e24eba89c10725bce0ebf0ffd7728f` |
| `tools/ffmpeg/.liveclip-ffmpeg-install.json` | `7d624c125324dc9f3f7f556a8d35de6261da7b4b1d57132708c9835ee1ec2353` | 完全相同 |
| `tools/ffmpeg/bin/ffmpeg.exe` | `ad8f211bc894755e0061c55ab280ae00e8d3d4f15a8cc4372b24cfa247b5942e` | 完全相同 |
| `tools/ffmpeg/bin/ffprobe.exe` | `9df3b0b5275e830961df6d94e1f7a71121a7abd5ff708e9fec8a0b6084a55015` | 完全相同 |
| `tools/Validate-Media.ps1` | `69b0cc12c5a78bf214160884eb7084523975cc1bc133e9ada1c96b47840e039c` | 完全相同 |
| `tools/Run-Tests.ps1` | `0a0c54f787597131302ee1cea4a55eb6855dec779e519a1a5ec9feff4bca054f` | 完全相同 |

仓库仍为初始分支、无提交，全部既有项目项显示为未跟踪；因此文件清单和上述哈希是本任务主要的变化证据。

## 10. 环境和依赖变化

- 新增 Python 包：无；大型 AI 依赖：无；ASR 模型：无。
- FFmpeg 下载/安装：无；继续使用原有项目内 8.1.2。
- 收费 API、网络业务调用和凭据写入：无。
- 永久环境变量变化：无；系统/用户 PATH 变化：无。
- 测试脚本只在子进程设置 D 盘 `PIP_CACHE_DIR`、`TEMP`、`TMP` 和 UTF-8 变量。

## 11. 安全边界

- 未下载 FFmpeg 归档，未重新安装 FFmpeg；现有安装标记、`ffmpeg.exe`、`ffprobe.exe` 未修改。
- 未下载 ASR 模型，未安装 PyTorch、PySide6、FunASR、SenseVoice、Whisper 或其他大型依赖。
- 未调用收费 API，未操作真实直播视频，未删除用户文件。
- 未修改系统 PATH 或永久环境变量，未执行 TASK-002，未创建提交或远程仓库。
- 未修改混合编码策略、音画同步容差、裁切、SRT 或字幕烧录实现。
- `tools/ffmpeg/` 继续被 `.gitignore` 命中；测试产物仅位于 pytest 隔离目录和 `runtime/`。

## 12. 已知问题

1. TASK-001-FIX2-R 尚未执行，因此当前只有实现和本地测试结论。
2. 现有安装标记是旧结构，缺少独立 `publisher_sha256`；本任务没有伪造未知值或为满足新结构而覆盖历史标记。
3. 原 FFmpeg 归档已删除，无法在本次重新计算；摘要明确为 `archive_hash_recomputed_this_run=false`。
4. gyan.dev SHA-256 不等于 FFmpeg 官方源码 PGP 到第三方 Windows 二进制的可复现构建证明。
5. AMF 初始化、真实长视频性能和字幕像素 OCR 是既有非本任务风险，未在 FIX2 扩展处理。
6. 仓库没有提交且所有文件未跟踪，Git 不能精确生成本任务差异或自动回滚。

## 13. 文档更新

- `CURRENT_STATUS.md`：记录 FIX2 本地完成、待 FIX2-R、不得写最终验收或进入 TASK-002。
- `DECISIONS.md`：新增生产来源冻结、测试隔离、摘要真实性、五字段时态和同版本离线策略。
- `MEDIA_VALIDATION_REPORT.md`：移除对歧义字段的当前使用，列出新字段及本次未联网、未下载、未重算边界。
- `TASK-001-FIX2.md`：记录任务开始基线、完成项、实测摘要和下一步边界。

## 14. 下一步建议

下一步只能建议执行 TASK-001-FIX2-R 独立只读复核，重点检查：生产参数列表不可覆盖来源；生产不复用预存本地归档；测试资源和目标隔离；生产/测试摘要来源一致；旧标记兼容不伪造；同版本五字段与实际动作一致；完整 133 项和媒体回归可重复。

本任务在此停止，不自动执行 TASK-002。

## 15. 用户检查方法

```powershell
Set-Location '<PROJECT_ROOT>'

# 阅读状态、决策和结果
Get-Content .\docs\CURRENT_STATUS.md -Encoding UTF8
Get-Content .\tasks\reports\TASK-001-FIX2_RESULT.md -Encoding UTF8

# 纯离线来源链专项（测试资源只在 pytest 隔离目录）
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Run-Tests.ps1 tests\test_ffmpeg_install_source.py -ra --durations=10

# 完整回归与合成媒体验证
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Run-Tests.ps1 -ra --durations=10
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Validate-Media.ps1

# 确认本地二进制与 runtime 仍被忽略
git check-ignore -v .\tools\ffmpeg\bin\ffmpeg.exe
git check-ignore -v .\runtime\logs\media-validation-20260719-124347-dfbb0d55.json
```

预期：来源链 21 passed；完整回归 133 passed；均 0 failed、0 skipped；`pip check` 通过；媒体验证输出 `TRIM_VALID=True`、`BURN_VALID=True` 和 18 项通过。

默认安装命令虽然在当前已知安装上实测为完全离线跳过，但若未来安装标记或目录状态变化，它可能按固定生产来源执行安装；因此用户复核时优先检查本报告中的实测 JSON和专项测试，不为重复验证而再次运行安装命令。

## 16. 回滚方法

仓库无提交，不能安全使用 `git checkout` 或 `git reset`。回滚前先备份项目，并确认没有用户后续编辑：

1. 从任务开始前备份手工还原 `tools/Install-FFmpeg.ps1`、`tests/test_ffmpeg_install_source.py`、`docs/CURRENT_STATUS.md`、`docs/DECISIONS.md`、`docs/MEDIA_VALIDATION_REPORT.md`。
2. 仅在确认不再需要 FIX2 记录后，删除本任务新增的 `tasks/TASK-001-FIX2.md` 与 `tasks/reports/TASK-001-FIX2_RESULT.md`。
3. 不删除 `tools/ffmpeg`、`src/liveclip/media`、`runtime`、`项目`、`模型`、原视频或整个仓库；本任务没有修改现有 FFmpeg 安装，因此无需回滚二进制。

没有可靠的任务前备份时，应保留现状并由独立只读复核逐文件检查，不执行宽范围删除。
