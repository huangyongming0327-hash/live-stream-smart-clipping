# TASK-001-FIX3-R｜FFmpeg 测试隔离最终定向只读复核报告

- 审核日期：2026-07-19（Asia/Shanghai）
- 项目目录：`<PROJECT_ROOT>`
- 审核对象：仅 TASK-001-FIX3 指定的四项最终定向复核
- 审核方式：完整读取指定材料；逐行审阅安装脚本和来源链测试；运行指定离线测试、合成媒体验证和只读探针
- 唯一非 `runtime/` 写入：本报告
- 未执行：源码/测试/文档/配置/脚本修改、下载或安装、UNC/网络共享访问、生产安装命令、收费 API、PATH 修改、TASK-002、Git 提交或远程操作

## 1. 审核结论

**通过。**

本次定向复核没有发现停止规则所列的真实阻断项。UNC、远程 `file:` URI、设备/命名管道路径、非固定或无法判断类型的驱动器均在资源读取、复制、解压或联网前关闭失败；实际 junction 和文件 symlink 逃逸测试全部执行并被拒绝；匹配真实哈希的非空损坏归档确实进入 `tar.exe` 解压并以非零结果失败，未发布、未写标记且清理完整；148 项完整回归、18 项同步/集成验证和合成媒体流程均通过，0 failed、0 skipped。

真实 FFmpeg 安装标记、`ffmpeg.exe`、`ffprobe.exe`、66 个受保护项目文件以及 Machine/User/Process PATH 在复核前后完全一致。

## 2. 阻断问题

**无。**

未观察到以下任一情况：访问 UNC/远程资源；重解析点逃逸并触碰真实安装或外部路径；损坏归档形成伪安装或危险残留；用户文件被删除或覆盖；真实 FFmpeg 安装变化；核心媒体功能回归；测试或报告结果造假。

## 3. UNC、远程 file URI 与非固定盘复核

### 3.1 实现审阅

`Resolve-LocalFixedDiskPath` 在任何 `Test-Path`、`Get-Content`、`Copy-Item` 或 `tar.exe` 操作之前统一验证测试路径：

1. 以 `\\` 或 `//` 开头的 UNC、扩展设备路径和命名管道路径立即拒绝；
2. `file:` URI 只有 `Host` 为空时才可转换为本地路径；`server` 和 `localhost` 均不是例外；
3. 转换后的值必须是盘符绝对路径；
4. `System.IO.DriveInfo.DriveType` 必须严格等于 `Fixed`；
5. 取得驱动器根或类型发生异常时进入 catch 并关闭失败；
6. 验证完成后才会检查文件存在性或进入读取、复制、解压流程。

### 3.2 实际测试结果

36 项来源链专项实际覆盖并通过：

- UNC `TestIsolationRoot`；
- UNC 测试归档和 UNC 校验文本；
- `file://server/share/...` 与 `file://localhost/share/...`；
- `\\?\D:\...` 设备路径；
- `\\.\pipe\...` 命名管道路径；
- `DriveInfo` 固定盘白名单、非 `Fixed` 拒绝和无法判定时关闭失败的源码语义。

相关用例均在临时下载目录创建、资源读取/复制或解压之前失败，并断言真实安装哈希不变。测试只使用本机 D 盘隔离资源，没有连接或探测网络共享。

本机只发现两个固定卷；没有映射网络盘，因此没有创建网络映射或对真实网络盘做行为测试。该项按指令记为非阻断已知边界。

## 4. 重解析点隔离复核

### 4.1 路径链与关键阶段复检

`Assert-NoReparsePointPath` 从卷根开始逐级检查所有已存在路径组件，发现 `FileAttributes.ReparsePoint` 即拒绝。`Assert-TestModeSafetyBoundary` 覆盖：

- 隔离根和哨兵；
- ProjectRoot；
- 归档和校验文本；
- 稳定安装目标、ffmpeg/ffprobe、安装标记；
- 下载目录、临时归档、唯一 `.partial` 和唯一解压目录。

该边界不是只在入口检查一次：创建临时目录后、校验文本读取和归档复制前、partial 移动后、解压前后、标记写入前后以及原子发布后均会再次检查。`tar.exe` 成功返回后立即对整个解压树执行 `Assert-NoReparsePointTree`，发布源目录在写标记和移动前也再次检查。

清理逻辑在递归删除前重新验证路径链和整棵树；若发现不可信重解析点，会告警并拒绝递归删除，而不会跟随它删除外部内容。

### 4.2 实际执行结果

以下场景均实际创建并运行，没有跳过：

| 场景 | 结果 | 外部/真实安装保护 |
|---|---|---|
| 隔离根 junction | 拒绝 | 真实三项哈希不变 |
| ProjectRoot junction 指向真实项目 | 拒绝 | 真实三项哈希不变 |
| 资源目录 junction 指向根外 | 拒绝 | 未创建项目 runtime；真实三项哈希不变 |
| 安装目标 junction 指向真实 `tools\ffmpeg` | 拒绝 | 未进入下载；真实三项哈希不变 |
| 临时下载目录 junction 指向根外 | 拒绝 | 根外目录保持为空；真实三项哈希不变 |
| 归档文件 symlink 指向根外 | 拒绝 | 真实三项哈希不变 |
| 校验文本 symlink 指向根外 | 拒绝 | 真实三项哈希不变 |

本机文件 symlink 权限可用；专项测试为 0 skipped。测试前后 66 个既有受保护文件的聚合哈希不变。损坏归档专项另有预存中文用户文件哨兵并确认内容未删除或改写。

解压树重解析点拒绝由 `tar.exe` 返回后的强制树扫描、发布前再次树扫描和清理前再次树扫描共同保证。现有 36 项中没有另行打包一个“解压后产生重解析点”的专用归档夹具；这是证据粒度限制，不是已观察到的逃逸，且不满足停止规则中的真实阻断条件。

## 5. 匹配哈希但归档损坏的解压失败复核

专项测试 `test_matching_hash_corrupt_archive_fails_extraction_without_publication` 独立运行和完整回归中均通过。逐项确认如下：

1. 归档为 77 字节，非空；
2. 起始字节为普通 ASCII `LiveCl`，不是有效 7z 文件头；
3. 测试真实读取文件并计算 SHA-256：`2c6b25eec747e91450c86dab889aef7d654ab1fde20fa02acb20aaa404322321`；
4. 校验文本内容等于该哈希；
5. `TestExpectedSha256` 等于该哈希；
6. 结构化摘要为 `publisher_hash_checked_this_run=true`、`publisher_hash_match_this_run=true`、`archive_hash_recomputed_this_run=true`，证明大小和两层哈希门禁均已通过；
7. 静态控制流与唯一错误文本共同确认实际进入 `tar.exe -xf`；
8. `tar.exe` 返回非零，脚本报告 `Archive extraction failed with exit code ...`，安装进程非零退出；
9. 稳定 `tools\ffmpeg` 不存在；
10. 隔离项目内没有安装标记；
11. 没有伪完整安装目录；
12. `.partial`、临时归档和 `extract-*` 全部不存在；
13. 预存 `用户资料\必须保留.txt` 内容仍为 `不要删除`，原测试资源也未删除；
14. 真实项目安装标记、ffmpeg 和 ffprobe 三项 SHA-256 前后相同。

该测试不是在大小或哈希阶段提前失败，符合本次专项要求。

## 6. 真实安装哈希保护

| 对象 | 字节数 | 复核前 SHA-256 | 测试后 SHA-256 | 结果 |
|---|---:|---|---|---|
| `tools/ffmpeg/.liveclip-ffmpeg-install.json` | 894 | `7d624c125324dc9f3f7f556a8d35de6261da7b4b1d57132708c9835ee1ec2353` | 相同 | 未修改 |
| `tools/ffmpeg/bin/ffmpeg.exe` | 242,496,512 | `ad8f211bc894755e0061c55ab280ae00e8d3d4f15a8cc4372b24cfa247b5942e` | 相同 | 未修改 |
| `tools/ffmpeg/bin/ffprobe.exe` | 242,291,712 | `9df3b0b5275e830961df6d94e1f7a71121a7abd5ff708e9fec8a0b6084a55015` | 相同 | 未修改 |

没有运行默认生产安装命令，没有下载或重新安装 FFmpeg。

## 7. 来源链专项测试

命令：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Run-Tests.ps1 tests\test_ffmpeg_install_source.py -ra --durations=10
```

| 总数 | 通过 | 失败 | 跳过 | pytest 耗时 | 整命令墙钟 |
|---:|---:|---:|---:|---:|---:|
| 36 | 36 | 0 | 0 | 23.22 s | 24.357 s |

随后由 `Run-Tests.ps1` 自动执行的 `pip check` 输出 `No broken requirements found.`。慢测试清单显示 junction、两个文件 symlink、UNC、远程 file URI 和损坏归档场景均实际执行。

## 8. 完整回归与媒体验证

### 8.1 完整测试

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Run-Tests.ps1 -ra --durations=10
```

| 总数 | 通过 | 失败 | 跳过 | pytest 耗时 | 整命令墙钟 |
|---:|---:|---:|---:|---:|---:|
| 148 | 148 | 0 | 0 | 25.43 s | 26.655 s |

完整回归中的中文与空格路径媒体集成测试实际执行并通过。`Run-Tests.ps1` 随后执行的 `pip check` 也通过。

### 8.2 合成媒体验证

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Validate-Media.ps1
```

- 退出码：0；墙钟 4.791 秒；
- `TRIM_VALID=True`；
- `BURN_VALID=True`；
- 强制能力：libx264、H.264、AAC、subtitles/ass/libass、SRT、WAV、PCM s16le 全部通过；
- 路径：`runtime\temp\媒体 测试\...`，中文与空格路径通过；
- WAV：PCM s16le、16 kHz、单声道，12.010688 秒；
- 精准裁切：2.3—8.7 秒，目标 6.4 秒，实测容器 6.422 秒；
- SRT：3 条字幕完成毫秒重计时，源 SRT 哈希语义保持不变（`source_srt_unchanged=true`）；
- 字幕烧录：容器 6.442667 秒，验证通过；
- 同步/集成：实际执行 18 项，收集结构为 17 项同步单元 + 1 项不可跳过的 FFmpeg 集成，全部通过。

本次媒体 JSON：`runtime/logs/media-validation-20260719-152921-44518a78.json`。

| 输出 | A/V 起始绝对差 | 流时长绝对差 | 目标时长绝对差 | 结果 |
|---|---:|---:|---:|---|
| 精准裁切 | 62.000 ms | 61.333 ms | 22.000 ms | 通过 |
| 字幕烧录 | 22.000 ms | 82.667 ms | 42.667 ms | 通过 |

源码 `SyncTolerances` 仍为 100/150/150 ms，`_within` 使用包含边界的 `<=`；边界单元测试仍明确以 100/150/150 ms 验证通过。受保护文件聚合哈希未变化，因此同步门禁没有被本次测试改写。

### 8.3 独立 pip check

```powershell
.\.venv\Scripts\python.exe -m pip check
```

退出 0，0.511 秒；输出 `No broken requirements found.`。

## 9. 文件哈希与 PATH 变化

### 9.1 开始状态

初始 Git 状态为 `No commits yet on master`；全部既有项目项仍为未跟踪，报告文件开始前不存在。由于没有 Git 基线，本次使用“相对路径 + 单文件 SHA-256”的确定性清单保护源码、测试、文档、配置和脚本，并排除 `.git`、`.venv`、`runtime`、`tools/ffmpeg` 与本报告；真实 FFmpeg 三项另行哈希。

| 项目 | 复核前 | 测试后 |
|---|---|---|
| 受保护文件数 | 66 | 66 |
| 受保护清单聚合 SHA-256 | `d0c91188e3cee804a347ede29d76c0a86f8ae56c0bf71261ae935e95397ce5a3` | 相同 |
| `tools/Install-FFmpeg.ps1` | `0180cbc3e89e48f49a0130136f681ccfd7178bf522a840ce37564a466a6ebb12` | 相同 |
| `tests/test_ffmpeg_install_source.py` | `c648ed00bcb3d312c3df5290c27422f1ef3136f484faa6473a50d13b01305043` | 相同 |

复核前完整 PATH：

```text
Machine=<REDACTED_PATH>
User=<REDACTED_PATH>
Process=<REDACTED_PATH>
```

| PATH scope | 字符数 | 复核前 SHA-256 | 测试后 |
|---|---:|---|---|
| Machine | 160 | `015ee9c6aec4e4122f27fd6dfb16e7f7dd9fe8213b5f90548312d1606a5030b8` | 相同 |
| User | 285 | `3dd925d5d202b7e9fad45620ab0cab4ec04e33c58f17f41365dd8c03c5e30e98` | 相同 |
| Process | 808 | `e59a4902170551f123269fc02621ca7fa6bd424fb8e74809f274a01769c9bd23` | 相同 |

测试后的 Git 状态与开始时一致；正常新增/更新只位于被忽略的 `runtime/`，包括本次合成媒体、媒体 JSON 和能力日志。除本报告外，没有新增或修改非 `runtime/` 项目文件。

本报告首次写入后再次复算：66 个受保护文件的聚合 SHA-256 仍为 `d0c91188e3cee804a347ede29d76c0a86f8ae56c0bf71261ae935e95397ce5a3`；安装脚本、专项测试、真实安装三项和 Machine/User/Process PATH 也仍与复核前完全相同。

## 10. 已知非阻断限制

1. 本机没有映射网络盘；没有为了测试而连接共享或创建网络映射。非 `Fixed`/未知驱动器的关闭失败结论来自源码控制流和现有离线语义测试。
2. 现有专项没有包含“归档解压后生成重解析点”的独立恶意归档夹具；解压后树扫描、发布前树扫描和清理前树扫描已静态确认。未观察到实际逃逸。
3. 重解析点拒绝和关键阶段复检不宣称消除全部理论 TOCTOU、恶意管理员或内核级替换竞态。
4. 二进制可复现构建、AMF 驱动、真实长视频性能和字幕像素 OCR 均为指令明确列出的 backlog，不阻断本次 TASK-001 结论。

## 11. 最终建议

**可以正式结束 TASK-001，并建立 Git 基线。**

本报告完成后停止；不执行 TASK-002，不创建 Git 提交。
