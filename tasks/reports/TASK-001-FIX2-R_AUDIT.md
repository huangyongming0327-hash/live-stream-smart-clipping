# TASK-001-FIX2-R｜FFmpeg 来源链最终独立只读审核报告

- 审核日期：2026-07-19（Asia/Shanghai）
- 项目目录：`<PROJECT_ROOT>`
- 审核对象：TASK-001-FIX2
- 审核方式：完整读取指定文件，独立审阅脚本、专项测试和全部媒体模块，运行既有离线测试、同版本只读探针与合成媒体验证
- 唯一项目写入：本报告；测试产生的正常文件仅位于既有 `runtime/`
- 未执行：下载或安装、收费 API、系统 PATH/永久环境变量修改、源码修复、TASK-002、Git 提交或远程操作

## 1. 审核结论

**不通过。**

TASK-001-FIX-R 的原两个阻断问题已经按其直接要求修复：生产来源字段不再可由生产参数覆盖；同版本摘要也正确区分了历史安装验证和本次实际动作。当前真实安装的离线跳过摘要、21 项来源链专项、133 项完整回归、18 项同步/集成回归、媒体验证和 `pip check` 均通过，0 failed、0 skipped。

但本次独立审阅发现一个新的测试隔离阻断问题：`Install-FFmpeg.ps1` 把 UNC 路径和带远程主机的 `file:` URI 当作本地文件接受；同时，隔离根包含判断只对 `GetFullPath` 后的字符串做前缀比较，不解析或拒绝 junction/symlink 等重解析点。因此，“测试资源、ProjectRoot 和测试目标真实位于本地隔离根”并未被严格保证。该问题可使测试模式发生网络文件访问，或经重解析点逃逸到隔离根外，违反本任务的强制完成条件。

因此，当前不能正式结束 TASK-001，也不能建立通过态 Git 基线。

## 2. 阻断问题

### B-01｜测试模式的“仅本地且真实隔离”可被 UNC/file URI 与重解析点绕过

#### 证据一：UNC 和远程 `file:` URI 会被识别为文件

`tools/Install-FFmpeg.ps1` 的 `Resolve-LocalTestFile` 只在 URI 的 `IsFile` 为 false 时拒绝远程资源；但 Windows/.NET 把 UNC 和 `file://server/share/...` 都识别为文件 URI。独立纯内存探针结果如下，探针没有连接服务器：

| 输入 | `Uri.IsFile` | `Uri.Host` | `Uri.LocalPath` | `Path.IsPathRooted` |
|---|---:|---|---|---:|
| `file://server/share/fixture.7z` | true | `server` | `\\server\share\fixture.7z` | false（原 URI 字符串） |
| `\\server\share\fixture.7z` | true | `server` | `\\server\share\fixture.7z` | true |
| `D:\isolated\fixture.7z` | true | 空 | `D:\isolated\fixture.7z` | true |

脚本随后使用 `uri.LocalPath`，所以前两类值都会成为 UNC 路径。`TestIsolationRoot` 本身也只要求 `Path.IsPathRooted` 和目录存在；一个可访问的 UNC 隔离根会通过。之后的 `Get-Content`、`Copy-Item`、`Test-Path` 都可能访问网络共享。这与“测试模式只允许本地资源”和本任务不应发生网络资源注入的要求不一致。

#### 证据二：隔离包含判断只做词法比较

`Test-PathEqualOrWithin` 的实际规则是：

1. 对 Path 和 Parent 调用 `System.IO.Path.GetFullPath`；
2. 接受路径等于 Parent，或字符串以 `Parent + '\'` 开头。

该函数没有解析最终物理路径，没有检查 `FileAttributes.ReparsePoint`，也没有拒绝路径任一组成部分为 junction/symlink。`ProjectRoot`、测试归档、校验文本和真实安装目标比较都依赖这一词法路径。因此，隔离根内的 junction/symlink 可以指向隔离根外资源；同理，词法上不同于真实 `tools\ffmpeg` 的路径可在文件系统层解析到真实项目或其他外部目录。

#### 现有测试缺口

21 项专项测试覆盖了 HTTPS 远程 URL、普通绝对路径越界和直接把 `ProjectRoot` 指向真实项目，但没有覆盖：

- UNC `TestIsolationRoot`；
- UNC 归档或校验文本；
- `file://server/share/...`；
- 隔离根内指向根外资源的 junction/symlink；
- 经 junction/symlink 指向真实项目安装目标。

#### 影响与修复要求

该问题不改变生产模式的固定 gyan.dev 来源，但会破坏 FIX2 声称的生产/测试严格隔离。FIX3 至少应：

1. 拒绝 UNC 路径、带非空 Host 的 `file:` URI和网络驱动器资源；
2. 对隔离根、ProjectRoot、资源和安装目标执行最终物理路径核验，或明确拒绝路径链上的所有重解析点；
3. 为上述 UNC、远程 file URI、资源 junction、ProjectRoot junction 和真实目标 junction 增加离线测试；
4. 每个逃逸测试均核对真实安装标记、ffmpeg.exe 和 ffprobe.exe 哈希不变。

本审核不实施修复。

## 3. 重要问题

### I-01｜“校验值正确但归档格式损坏”的解压失败分支缺少独立自动化用例

脚本在 `tar.exe -xf` 非零时会抛错，catch/finally 会清理本次归档、partial 和解压目录，且稳定安装发布发生在解压和能力探针之后；静态控制流符合“解压失败不发布”。

不过，现有 21 项测试中的空归档在哈希前因大小失败，截断归档因哈希不匹配失败，没有构造“发布方文本、固定值和本地归档哈希三者一致，但内容不是有效 7z”的场景。因此该分支目前没有专项回归证据。FIX3 应补一项完全位于隔离根的匹配哈希损坏归档测试，并断言没有稳定安装、没有伪标记、没有 partial 和残留归档。

## 4. 一般建议

1. 新结构安装标记可记录 `ffmpeg.exe` 和 `ffprobe.exe` 的安装时 SHA-256；同版本跳过时可选择重算二进制哈希。当前分支只验证文件非空、标记来源字段和版本行，现有真实二进制虽与审核基线一致，但标记没有二进制级完整性字段。
2. 读取旧标记布尔字段时应要求 JSON 布尔类型；PowerShell 的 `[bool]"false"` 会得到 true，严格类型可避免畸形旧标记被解释为历史验证成立。
3. FIX3 完成并通过新的独立复核后，再更新 `CURRENT_STATUS.md` 并建立 Git 基线；不要在 FIX3 中扩展 UI、ASR、模型或 TASK-002。

## 5. 原两个阻断问题逐项复核表

| TASK-001-FIX-R 原阻断 | 独立验证 | 实际结果 | 结论 |
|---|---|---|---|
| 生产安装入口可覆盖 URL、校验 URL、固定哈希、版本和归档名，却仍声明 gyan.dev | 完整审阅参数块和常量；PowerShell AST 解析；运行 5 类覆盖参数专项；补跑 `-Build malicious` | 参数只剩 `ProjectRoot` 和 6 个显式测试参数；生产来源、版本、构建、归档和哈希均为脚本常量；`-Build` 与原 5 类覆盖参数均由参数绑定拒绝 | **已修复** |
| 同版本跳过把历史记录误报为本次发布方比对 | 审阅分支顺序、读取旧标记、实跑真实默认安装命令、前后哈希/PATH 比对 | 历史验证 true；本次发布方检查 false、匹配 null、归档重算 false、归档下载 false；旧标记缺失 publisher SHA 保持 null | **已修复** |

原两个问题虽已修复，但 B-01 是 FIX2 测试隔离完成条件中的新阻断，因此总体仍不通过。

## 6. TASK-001-FIX2 完成条件逐项复核表

| 完成条件 | 证据与实际结果 | 判断 |
|---|---|---|
| 生产 provider 固定为 gyan.dev | 脚本常量和生产摘要一致 | 完成 |
| 版本固定为 8.1.2 | 参数块无生产版本覆盖项；常量和版本行一致 | 完成 |
| build 固定为 full_build | 常量固定；`-Build malicious` 退出 1、参数不存在 | 完成 |
| 归档固定为 `ffmpeg-8.1.2-full_build.7z` | 常量、摘要和旧标记一致 | 完成 |
| 下载 URL 固定 | 常量为规定 gyan.dev HTTPS URL；覆盖参数不存在 | 完成 |
| 校验 URL 固定 | 常量为规定 `.sha256` URL；覆盖参数不存在 | 完成 |
| 固定 SHA-256 不可覆盖 | 固定值为 `0fff...7059`；生产参数不存在 | 完成 |
| 生产不能注入本地归档/非 gyan.dev 远程来源 | 参数绑定拒绝，专项测试通过；预存归档不使用且不删除 | 完成 |
| 生产摘要字段来自固定常量 | `mode=production`、provider/URL/version/build/archive 均由常量赋值 | 完成 |
| 升级必须修改受审计源码 | 没有生产版本/来源运行时入口 | 完成 |
| 测试模式需显式启用 | 普通模式携带测试参数失败；专项通过 | 完成 |
| 普通生产模式拒绝测试参数 | 代码和专项测试一致 | 完成 |
| 测试模式只允许本地资源 | HTTP(S) 被拒绝，但 UNC 和远程 file URI 可通过文件 URI判断 | **未完成，阻断** |
| 隔离根必须绝对且有哨兵 | 代码显式检查绝对路径、目录和哨兵 | 完成（词法层面） |
| 测试归档、校验文本、ProjectRoot 真实位于隔离根 | 普通路径越界会拒绝，但未解析重解析点，不能保证真实物理包含 | **未完成，阻断** |
| 测试目标不能指向真实 `tools\ffmpeg` | 直接路径被拒绝；经重解析点的物理目标未被可靠识别 | **未完成，阻断** |
| 测试不写真实标记/二进制 | 现有 21 项前后真实标记和二进制审核哈希均不变；但逃逸路径未受保护 | 当前实测通过，机制不完整 |
| 测试摘要如实写 test/test_fixture/local_test_resource | 同版本测试摘要专项通过，不宣称 gyan.dev | 完成 |
| 五个时态字段区分历史与本次动作 | 代码、专项和真实摘要一致 | 完成 |
| 缺失 publisher_sha256 保持 null | 当前旧标记无该字段，真实摘要为 null | 完成 |
| 同版本不访问两个 URL、不创建本次下载处理 | 分支在两个资源函数调用和 `New-Item` 前返回；真实运行 0.425 s，历史空下载目录时间戳不变 | 完成 |
| 无效/不匹配/空/截断归档和未知目录安全失败 | 专项测试通过 | 完成 |
| 解压失败不发布 | 代码控制流正确，但缺少匹配哈希损坏归档专项 | 实现通过，测试证据不完整 |
| 完整 133 项和媒体回归 | 本次 133/133、18/18、媒体流程、pip check 均通过 | 完成 |
| 不修改媒体实现、同步容差或编码策略 | 62 文件哈希清单前后相同；媒体回归稳定 | 完成 |
| 文档如实保持待独立复核，不进入 TASK-002 | 指定文档均符合 | 完成 |

## 7. 生产来源冻结复核

生产值实测/静态复核如下：

| 字段 | 固定值 |
|---|---|
| provider | `gyan.dev` |
| source page | `https://ffmpeg.org/download.html` |
| provider page | `https://www.gyan.dev/ffmpeg/builds/` |
| version | `8.1.2` |
| build | `full_build` |
| archive | `ffmpeg-8.1.2-full_build.7z` |
| download URL | `https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-8.1.2-full_build.7z` |
| checksum URL | `https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-8.1.2-full_build.7z.sha256` |
| fixed SHA-256 | `0fff188997a499b5382e0f66e845d4556c48c54f0113ebed4853d556dbdd7059` |

PowerShell AST 无解析错误，参数名仅为：

```text
ProjectRoot
TestMode
TestIsolationRoot
TestArchivePath
TestPublisherChecksumPath
TestExpectedSha256
TestExpectedVersion
```

不存在生产 `DownloadUri`、`PublisherChecksumUri`、`ExpectedSha256`、`ExpectedVersion`、`ArchiveFileName` 或 `Build` 参数。生产摘要的 provider、URL、版本、构建和归档名均来自上述常量。普通生产调用也拒绝预先放置的本地同名归档，不使用且不删除它。

当前项目二进制实测：

- ffmpeg：`ffmpeg version 8.1.2-full_build-www.gyan.dev`
- ffprobe：`ffprobe version 8.1.2-full_build-www.gyan.dev`
- 构建配置包含 `--enable-static`、`--enable-libx264`、`--enable-libass`、`--enable-amf`
- `Get-Command ffmpeg.exe` 未找到；`where.exe ffmpeg.exe` 退出 1，媒体层使用项目固定绝对路径

## 8. 测试模式隔离复核

已确认的正向保护：

- 测试参数必须配合显式 `-TestMode`；
- 需要显式 ProjectRoot、绝对 TestIsolationRoot 和哨兵；
- HTTP(S) URL在任何文件读取前被拒绝；
- 普通 `..`/兄弟目录越界经 `GetFullPath` 后被拒绝；
- 直接把测试 ProjectRoot 指向真实项目会失败；
- 测试摘要固定为 `mode=test`、`selected_provider=test_fixture`、`source_type=local_test_resource`；
- 本次所有既有测试前后真实标记、ffmpeg.exe 和 ffprobe.exe 哈希不变。

未满足的严格隔离见 B-01：UNC/远程 file URI 和重解析点没有被拒绝或物理解析。现有测试只能证明普通路径场景安全，不能证明 Windows 文件系统边界下的严格隔离。

## 9. 同版本摘要实测 JSON

实际命令：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Install-FFmpeg.ps1
```

结果：退出 0，0.425 秒，走 `already_installed`。完整摘要：

```json
{
  "status": "already_installed",
  "message": "Known matching installation was safely skipped offline.",
  "mode": "production",
  "source_type": "remote_https",
  "official_download_page": "https://ffmpeg.org/download.html",
  "official_windows_build_providers": ["gyan.dev", "BtbN"],
  "selected_provider": "gyan.dev",
  "provider_download_page": "https://www.gyan.dev/ffmpeg/builds/",
  "direct_download_url": "https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-8.1.2-full_build.7z",
  "publisher_checksum_url": "https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-8.1.2-full_build.7z.sha256",
  "archive_file_name": "ffmpeg-8.1.2-full_build.7z",
  "archive_size_bytes": 166721853,
  "download_time": "2026-07-18T23:53:17.497+08:00",
  "installed_archive_sha256": "0fff188997a499b5382e0f66e845d4556c48c54f0113ebed4853d556dbdd7059",
  "publisher_sha256": null,
  "fixed_audited_sha256": "0fff188997a499b5382e0f66e845d4556c48c54f0113ebed4853d556dbdd7059",
  "publisher_hash_verified_at_install": true,
  "publisher_hash_checked_this_run": false,
  "publisher_hash_match_this_run": null,
  "archive_hash_recomputed_this_run": false,
  "archive_downloaded_this_run": false,
  "installed_from_url": "https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-8.1.2-full_build.7z",
  "version": "8.1.2",
  "build": "full_build",
  "version_line": "ffmpeg version 8.1.2-full_build-www.gyan.dev Copyright (c) 2000-2026 the FFmpeg developers",
  "installed_at": "2026-07-18T23:55:35.872+08:00",
  "ffmpeg_path": "<PROJECT_ROOT>\\tools\\ffmpeg\\bin\\ffmpeg.exe",
  "ffprobe_path": "<PROJECT_ROOT>\\tools\\ffmpeg\\bin\\ffprobe.exe",
  "system_path_modified": false
}
```

当前 `runtime/temp/ffmpeg-download` 在运行前已经存在且为空：创建时间 `2026-07-18T23:53:17.455+08:00`，最后写入 `2026-07-18T23:55:35.936+08:00`。本次运行前后均为空，时间戳未变化。因此正确结论是“本次没有创建或进入下载处理”，而不是“项目中从来不存在该目录”。

真实安装前后：

| 对象 | 运行前 SHA-256 | 运行后 SHA-256 |
|---|---|---|
| 安装标记 | `7d624c125324dc9f3f7f556a8d35de6261da7b4b1d57132708c9835ee1ec2353` | 相同 |
| ffmpeg.exe | `ad8f211bc894755e0061c55ab280ae00e8d3d4f15a8cc4372b24cfa247b5942e` | 相同 |
| ffprobe.exe | `9df3b0b5275e830961df6d94e1f7a71121a7abd5ff708e9fec8a0b6084a55015` | 相同 |

控制流中 `Get-KnownInstallation` 和本分支返回均位于 `Get-TextResource`、`Copy-ResourceToFile` 和下载目录 `New-Item` 之前。因此本次没有访问下载 URL或校验 URL；摘要与实际动作一致。

## 10. 来源链专项测试

实际命令：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Run-Tests.ps1 tests\test_ffmpeg_install_source.py -ra --durations=10
```

结果：

| 总数 | 通过 | 失败 | 跳过 | pytest 耗时 | 整命令墙钟 |
|---:|---:|---:|---:|---:|---:|
| 21 | 21 | 0 | 0 | 7.44 s | 8.8 s |

`pip check` 同步通过。既有用例覆盖生产常量、五类旧覆盖参数、本地生产注入、预存归档保留、显式 TestMode、HTTP(S) 拒绝、普通路径隔离、直接真实目标保护、测试摘要、旧标记、五个时态字段、无效/不匹配哈希、空/截断归档、未知目录和 PATH 不变。

关键测试没有跳过。测试数量与指令预期 21 完全一致。未覆盖项见 B-01 和 I-01。

## 11. 完整媒体与 Schema 回归

### 11.1 完整测试

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Run-Tests.ps1 -ra --durations=10
```

| 总数 | 通过 | 失败 | 跳过 | pytest 耗时 | 整命令墙钟 |
|---:|---:|---:|---:|---:|---:|
| 133 | 133 | 0 | 0 | 9.52 s | 10.9 s |

数量与预期 133 完全一致。构成可核对为：65 项 Schema、21 项来源链、29 项媒体单元、17 项同步单元和 1 项关键媒体集成。

Schema 独立重跑：65 passed、0 failed、0 skipped，0.19 s。覆盖 Timeline、CurrentAnalysis、ReviewCurrent、严格类型、有限数、真实 JSON 往返、中文与空格路径等。

Windows 混合编码专项独立重跑：9 passed、0 failed、0 skipped、20 deselected，0.20 s。UTF-8 中文、UTF-8 BOM、CP936/GBK、非法字节降级、中文路径失败、非零退出和超时结构化元数据均保留。

### 11.2 媒体验证

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Validate-Media.ps1
```

整脚本退出 0，约 4.2 秒。实际输出确认：

- libx264、H.264 decoder、AAC encoder/decoder；
- subtitles/ass/libass；
- SRT、WAV、PCM s16le；
- `TRIM_VALID=True`；
- `BURN_VALID=True`；
- h264_amf/hevc_amf 被构建列出，但仍只作非阻断 advertised 探针；
- 强制同步/集成测试显示 18 个通过点，无失败或跳过。

为取得精确数量与耗时，另按同一两个测试文件重跑：18 passed、0 failed、0 skipped，pytest 1.66 s；其中 17 项同步单元 + 1 项不可跳过的 FFmpeg 集成。

本次新日志：

- `runtime/logs/media-validation-20260719-134057-1450609b.json`
- `runtime/logs/ffmpeg-capabilities-20260719-134057-195.txt`

已完整读取媒体 JSON；能力日志确认 8.1.2 full build 及所需编码器、解码器、滤镜和格式。

### 11.3 最新合成媒体实测

| 字段 | 12 s 输入 | 精准裁切 2.3—8.7 s | 中文字幕烧录 |
|---|---:|---:|---:|
| 视频首帧 PTS | 0.000000 s | 0.080000 s | 0.080000 s |
| 音频首包 PTS | -0.021333 s | 0.018000 s | 0.058000 s |
| A/V 起始差 | -21.333 ms | -62.000 ms | -22.000 ms |
| 视频流时长 | 12.000000 s | 6.360000 s | 6.360000 s |
| 音频流时长 | 12.000000 s | 6.421333 s | 6.442667 s |
| 流时长差 | 0.000 ms | +61.333 ms | +82.667 ms |
| 容器时长 | 12.000000 s | 6.422000 s | 6.442667 s |
| 目标时长差 | 0.000 ms | +22.000 ms | +42.667 ms |
| 同步/时长判断 | 通过 | 通过 | 通过 |

100/150/150 ms 门禁没有变化，所有指标在边界内，warnings/errors 为空。路径包含中文和空格；WAV 为 PCM s16le、16 kHz、单声道；SRT 三条按毫秒重计时；原 SRT 未改变。

### 11.4 pip check

```powershell
.\.venv\Scripts\python.exe -m pip check
```

退出 0，输出 `No broken requirements found.`。环境只有 Pydantic、pytest 及轻量传递依赖；未发现 torch、PyTorch、FunASR、SenseVoice、Whisper Python 包或 PySide6。

## 12. 文档与代码一致性

| 核对项 | 结果 |
|---|---|
| 生产来源已冻结 | CURRENT_STATUS、DECISIONS、MEDIA_VALIDATION_REPORT、TASK/FIX2_RESULT 与脚本常量一致 |
| 测试注入隔离 | 文档描述了普通路径机制，但未披露 B-01 的 UNC/重解析点缺口；因此“严格隔离”结论过强 |
| 历史验证与本次验证分开 | 文档、代码和真实 JSON 一致 |
| 本次未下载 | 文档与 `archive_downloaded_this_run=false` 一致 |
| 本次未重算归档哈希 | 文档与 `archive_hash_recomputed_this_run=false` 一致 |
| 旧标记缺少 publisher_sha256 | 已如实披露；真实摘要保持 null |
| gyan.dev 哈希边界 | 已说明不等于官方源码 PGP/可复现构建证明 |
| 是否提前写最终验收通过 | 否 |
| 是否建议直接进入 TASK-002 | 否 |
| 是否明确仍需本次独立复核 | 是；这些文件是在本报告前形成，状态措辞正确 |

除未识别 B-01 外，文档对时态、下载/重算边界、第三方哈希边界和待复核状态均诚实。由于本次结论不通过，现有“仍待 FIX2-R”状态并未被本报告反向造成通过态矛盾。

## 13. 安全与任务边界

本次审核确认：

- 没有重新下载或重新安装 FFmpeg；
- 没有安装或下载 FunASR、SenseVoice、Whisper、PyTorch、PySide6、ASR 模型或其他大型依赖；
- 没有调用收费 API；
- 未发现 `.env`、真实 config、私钥/证书文件或 secret-like 内容；
- 没有操作真实直播视频，媒体文件只在 `runtime/`；
- 没有修改系统/用户/进程 PATH；没有永久环境变量写入代码；
- 没有 TASK-002 文件或执行痕迹；
- 没有删除或覆盖用户文件；
- 没有修改混合编码实现、同步实现或 100/150/150 ms 容差；
- 业务源码没有新增网络客户端；网络调用仍只存在于固定来源安装脚本；
- Git 仓库仍无提交、无 remote；
- `tools/ffmpeg/`、安装标记、`runtime/logs` 和 `runtime/temp` 均被 `.gitignore` 命中；
- 审核时 9 个大于 50 MiB 的文件全部是项目 FFmpeg 二进制或 runtime 测试硬链接，全部被忽略；未发现未忽略大文件。

需要特别说明：B-01 表示“机制允许未来测试模式访问 UNC/远程 file 资源”，不是说本次审核实际访问了 UNC。纯 .NET URI 探针没有连接网络；本次所有实际测试资源均在 D 盘 `runtime/`。

### PATH 基线与复核

| Scope | 字符数 | SHA-256 | 含项目 FFmpeg | 前后 |
|---|---:|---|---:|---|
| Machine | 160 | `015ee9c6aec4e4122f27fd6dfb16e7f7dd9fe8213b5f90548312d1606a5030b8` | 否 | 相同 |
| User | 285 | `3dd925d5d202b7e9fad45620ab0cab4ec04e33c58f17f41365dd8c03c5e30e98` | 否 | 相同 |
| Process | 808 | `e59a4902170551f123269fc02621ca7fa6bd424fb8e74809f274a01769c9bd23` | 否 | 相同 |

## 14. 文件哈希变化

### 14.1 审核前基线

- 初始 Git：`No commits yet on master`；既有项目项均未跟踪；无 remote；审核报告不存在。
- 以 `.gitignore` 加 `rg --files` 建立 62 个受保护源码/测试/文档/配置/脚本文件清单，排除 `.git`、`.venv`、`runtime`、`tools/ffmpeg` 和本审核报告。
- 62 文件“相对路径 + 单文件 SHA-256”清单聚合 SHA-256：`00a011ca9742da7175d878379e3856ba338ea33c7411a35c90b0689377806fea`。

关键文件审核前 SHA-256：

| 文件 | SHA-256 |
|---|---|
| `.gitignore` | `ad343071bef0a491de870d99a6bc8e2576cf8be08ec795a19e5c877444a221c7` |
| `config.example.json` | `8b5b50fd4faadf11bb9b947d1644e2f1c0221fa0d38d187c6a60f8306e349b82` |
| `docs/CURRENT_STATUS.md` | `83c6bd08348d8dc5df7d31c3b41d06907e58991df54d8d4046b3306ed94a3ea6` |
| `docs/DECISIONS.md` | `5fc59bd0c056950d17b0f08068e736163a7ee9369fd6c826d6e5c9fafd489533` |
| `docs/MEDIA_VALIDATION_REPORT.md` | `da59835be41df2ea140c6efb83705d294695603f0d40a8d757897fd9d33bade9` |
| `tasks/TASK-001-FIX2.md` | `c1f05812102e6c0b78b5e1dbd48353ce89e2625ff117ae0a90e686a566718484` |
| `tasks/reports/TASK-001-FIX2_RESULT.md` | `bac96f64546a1e2a82c8c1fe0883448752902e832d1677e63d2ac8fafb2254f7` |
| `tools/Install-FFmpeg.ps1` | `ec087b43794b191094909365d7c704086e4affb783222570e225a3b30d402bde` |
| `tools/Validate-Media.ps1` | `69b0cc12c5a78bf214160884eb7084523975cc1bc133e9ada1c96b47840e039c` |
| `tools/Run-Tests.ps1` | `0a0c54f787597131302ee1cea4a55eb6855dec779e519a1a5ec9feff4bca054f` |
| `tests/test_ffmpeg_install_source.py` | `e9256598569172d1c0c000a78a1bea3319e24eba89c10725bce0ebf0ffd7728f` |

### 14.2 二进制和安装标记

| 文件 | 长度 | 审核前 SHA-256 | 测试后 SHA-256 |
|---|---:|---|---|
| `tools/ffmpeg/bin/ffmpeg.exe` | 242,496,512 | `ad8f211bc894755e0061c55ab280ae00e8d3d4f15a8cc4372b24cfa247b5942e` | 相同 |
| `tools/ffmpeg/bin/ffprobe.exe` | 242,291,712 | `9df3b0b5275e830961df6d94e1f7a71121a7abd5ff708e9fec8a0b6084a55015` | 相同 |
| `tools/ffmpeg/.liveclip-ffmpeg-install.json` | 894 | `7d624c125324dc9f3f7f556a8d35de6261da7b4b1d57132708c9835ee1ec2353` | 相同 |

### 14.3 测试后与报告生成后

- 全部测试和只读探针后，62 文件聚合仍为 `00a011ca9742da7175d878379e3856ba338ea33c7411a35c90b0689377806fea`，与审核前一致。
- 正常新增/更新仅位于 `runtime/`：pytest 临时内容、合成媒体、媒体 JSON和能力日志。
- 报告生成后的最终受保护文件复算：62 文件，聚合 SHA-256 仍为 `00a011ca9742da7175d878379e3856ba338ea33c7411a35c90b0689377806fea`，与审核前完全一致；FFmpeg/ffprobe/安装标记哈希也仍完全一致。
- 本次唯一新增的非 runtime 项目文件为 `tasks/reports/TASK-001-FIX2-R_AUDIT.md`。

## 15. 最终建议

**需要执行 TASK-001-FIX3。**

FIX3 应保持单一、窄范围：只修复测试模式对 UNC/远程 file URI 和重解析点的隔离缺口，补充相应测试，并补齐匹配哈希损坏归档的解压失败测试。不要重新下载或安装 FFmpeg，不要修改媒体/同步/编码实现，不要执行 TASK-002。

原两个 FIX-R 阻断问题不需要返工；FIX3 完成后仍需一次新的独立只读复核，复核通过后才能结束 TASK-001 并建立通过态 Git 基线。
