# TASK-007-R AUDIT｜字幕烧录与启动器稳健性独立审核

## 1. FIX 后复审当前结论

- 复审名称：`TASK-007-R2`
- 仓库：`huangyongming0327-hash/live-stream-smart-clipping`
- PR：`#9`
- 分支：`task/TASK-007-subtitle-burnin-launcher-fix`
- 当前审核 HEAD：`c0deea6d130b0cbc7633c7ca9a9be3c67d180ab9`
- 复审日期：2026-08-30
- 当前阻断状态：无未关闭阻断
- B-1 状态：已关闭
- N-1 状态：已关闭
- 复审性质：对 FIX 后实现独立重跑真实 FFmpeg、完成态矩阵、自动测试与范围检查；没有修改
  实现代码、测试、RESULT、README、CURRENT_STATUS 或首审历史

**总分：98/100**

**最终结论：通过，保持Draft等待用户决定**

FIX 后实现解决了首审记录的两个问题。生产 `export_review_clip()` 已在同时包含盘符冒号、中文、
空格、`&`、圆括号和单引号的真实 Windows 路径下完成字幕烧录；completed review 的布尔字段与
正式 SRT 内容不一致或损坏时，review loader 和 pipeline runner 均不再复用。当前没有一票否决
项。本次复审只形成审核结论，不执行 Ready、merge、auto-merge 或 TASK-008。

## 2. 当前阻断问题

未发现未关闭阻断问题。首审 B-1 已由真实特殊路径回归关闭；首审 N-1 已由完成态矩阵关闭。

## 3. FIX 后复审｜B-1 关闭证据

- 在全新受控审核目录生成 15 秒、960×540、H.264/AAC 合成输入；目录路径同时包含 Windows
  盘符冒号、中文、空格、`&`、圆括号和单引号，没有用路径限制或移除字符规避问题。
- 直接调用生产 `export_review_clip()` 和项目现有真实 Windows FFmpeg/ffprobe；进程路径仍由
  参数列表传递且 `shell=False`，没有 shell 拼接或长期固定字幕副本。
- 正式输出成功：review 为 completed，`subtitles_burned_in=true`，正式 SRT 为合法 1 cue；
  ffprobe 确认视频为 H.264、音频为 AAC，容器时长 15.022 秒。
- 没有把生产 `render_timeline_srt()` 当作预期值；依据审核输入独立写出预期的单 cue、0—15 秒
  SRT，正式 SRT 的序号、开始/结束毫秒和文本逐字符完全一致。
- 临时把同名 SRT 移为非 `.srt` 后，仅从 MP4 的 7.5 秒位置抽帧。人工查看可清晰看到底部
  居中的白字黑边字幕；同一帧的独立 `signalstats` 得到 `YMAX=242`，而合成底色为深色，证明
  可见文字来自 MP4 画面，不是播放器或 FFmpeg 自动读取同名 SRT。检查后 SRT 已原样恢复。
- 原视频、timeline、analysis 的 SHA-256 在导出及移走/恢复 SRT 前后完全不变；审核目录没有
  `.part`，也没有遗留 `.r2-hold`。因此 B-1 从阻断改为已关闭。
- 仓库新增的 Windows 真实 FFmpeg 单引号路径集成回归另行独立运行，1 passed、0 failed。

## 4. FIX 后复审｜N-1 关闭证据

使用同一份匹配当前输入哈希和候选范围的 completed review，分别构造下列状态。每个场景都同时
调用 `load_completed_export()` 与 pipeline runner 的完成态判定，并对调用前后的 review、MP4、
SRT 字节进行比较：

| 场景 | review loader | pipeline runner | 文件保护 |
|---|---|---|---|
| `true + 合法非空 SRT` | 可复用 | 可复用 | 三文件不变 |
| `false + 合法空 SRT` | 可复用 | 可复用 | 三文件不变 |
| `true + 空 SRT` | 不复用 | 不复用 | 三文件不变 |
| `false + 合法非空 SRT` | 不复用 | 不复用 | 三文件不变 |
| `true + 损坏 SRT` | 不复用 | 不复用 | 三文件不变 |
| `false + 损坏 SRT` | 不复用 | 不复用 | 三文件不变 |
| 旧 review 缺 `subtitles_burned_in` | 不复用 | 不复用 | 三文件不变 |

实现只读取 UTF-8-SIG SRT 并用既有严格解析器判断 cue 数；合法非空与严格 `true` 对应，合法空
与严格 `false` 对应。拒绝复用只返回未完成状态，不删除、覆盖或改写旧 review、MP4 或 SRT。
因此 N-1 已关闭。

## 5. FIX 后复审｜测试、Actions 与边界

- 指定定向回归：75 passed，0 failed。
- source-only base-schema-media：233 passed，1 deselected，0 failed，退出码 0。
- source-only asr-experiments：91 passed，2 deselected，1 个既有 `audioop` deprecation warning，
  0 failed，退出码 0。
- `pip check`：`No broken requirements found.`，退出码 0；最终
  `SOURCE_ONLY_RESULT.status=passed`。
- 实现 HEAD 对应 run `31473820980` 的 `repository-safety`、`lightweight-tests`、
  `task-report-gate` 均 completed/SUCCESS。逐 job 阅读完整 607 行日志，0 个真实失败信号；安全
  日志为 191 files scanned、191 text files、0 issue。
- 本地 tracked safety 再次为 191/191、0 issue；`git diff --check` 无问题。
- PR 文件范围没有进入 `src/liveclip/asr/`、`src/liveclip/analysis/`，没有字幕样式改动、字幕
  编辑器、批量、多片段拼接、自动发布或 TASK-008。
- R2 真实/合成产物均留在非 tracked 审核目录；报告不包含本地绝对路径、真实用户字幕正文、
  媒体、模型、凭据或密钥。

## 6. FIX 后复审评分

| 维度 | 得分 |
|---|---:|
| 字幕烧录真实可用性 | 25/25 |
| 字幕时间、文本与视觉质量 | 14/15 |
| 导出失败安全与用户文件保护 | 15/15 |
| Windows 启动器稳健性 | 15/15 |
| 测试与真实验证 | 10/10 |
| 代码简洁与维护性 | 9/10 |
| 隐私与 Git 边界 | 5/5 |
| 文档与可追溯性 | 5/5 |
| **当前总分** | **98/100** |

扣除 2 分是因为 R2 只针对 FIX 影响面重跑 15 秒合成媒体，没有再次执行首审已完成的 827.766 秒
全长真实输入人工播放流程；首审对长视频、三处同步、空字幕、失败回滚、启动器和样式的通过
证据继续有效。B-1 与 N-1 均有本轮独立运行证据，不再构成扣分或阻断。

## 7. FIX 后复审最终建议

当前审核结论为：**通过，保持Draft等待用户决定**。R2 没有执行 Ready、merge 或 auto-merge；
是否改变 Draft 状态及后续人工合并决定仍由用户处理。本审核不执行 TASK-008。

---

# 第一次审核历史（2026-08-11，以下首审内容原样保留）

## 1. 审核对象与结论

- 仓库：`huangyongming0327-hash/live-stream-smart-clipping`
- PR：`#9`
- 分支：`task/TASK-007-subtitle-burnin-launcher-fix`
- 审核基线 HEAD：`4400f9fd56bc1808f0d6ddfc1fdc6f1c97c81bf9`
- 审核日期：2026-08-11
- 审核性质：独立复核；没有修改实现、测试、RESULT、README 或其他既有文档

**总分：84/100**

**等级：分数落在“有条件通过”区间，但触发一票否决。**

**最终结论：需要TASK-007-FIX，继续Draft**

正常中文、空格、`&`、圆括号路径下的真实字幕烧录、空字幕、失败回滚、Windows 启动器和三项
Actions 均通过独立验证；但是合法 Windows 单引号目录会使 FFmpeg subtitles filter 解析失败。
审核指令把“特殊路径不可用”列为一票否决，因此 PR #9 当前不得 Ready 或 merge。

## 2. 阻断问题

### B-1｜合法单引号目录无法烧录字幕

- 严重性：阻断；命中审核指令“一票否决：普通中文/特殊路径不可用或存在命令注入”。
- 独立复现：构造 15 秒、1920×1080、H.264/AAC、非空 UTF-8 SRT 的有效审核输入；输出目录
  同时包含中文、空格、`&`、圆括号和单引号，并调用生产 `export_review_clip()`。
- 实际结果：生产 exporter 返回“FFmpeg 导出失败”；FFmpeg 原始错误包含
  `No option name near '7.467'`、`Error parsing filterchain` 和 `Invalid argument`。
- 根因：`src/liveclip/media/subtitles.py` 的 `escape_subtitles_path()` 把单引号写成 `\'`，再由
  `src/liveclip/review/exporter.py` 把整个 filename 包在单引号内；该形式没有在 FFmpeg filter
  graph 中保住 filename 边界，后续 `force_style` 被误解析。
- 安全边界：进程始终 `shell=False`，未发现命令注入；失败时没有正式 MP4/SRT、伪 completed
  review 或 `.part` 残留，因此这是可用性阻断，不是文件破坏问题。
- 修复验收建议：使用 FFmpeg filter graph 真正接受的 filename 转义/参数传递方式，并增加一个
  Windows 真实 FFmpeg 集成回归；必须覆盖中文、空格、`&`、圆括号、盘符冒号和单引号组合。

## 3. 非阻断问题

### N-1｜completed review 复用没有验证布尔值与 SRT 空/非空一致

- 缺少 `subtitles_burned_in` 的旧 review 会被正确拒绝，不会误报完成，也不会删除旧文件。
- 生产 exporter 新生成的非空/空字幕结果会分别写入严格布尔 `true`/`false`。
- 但是独立构造不一致的本地完成态后，`false + 非空 SRT` 和 `true + 空 SRT` 都仍会被
  `load_completed_export()` 与 runner 复用。当前实现只检查字段是布尔值及文件存在，没有检查
  SRT 内容与布尔值的对应关系。
- 影响限于本地 review/输出被人工修改或发生漂移后的二次复用；本次正常 exporter 结果不受影响。
  建议在 TASK-007-FIX 一并收紧，至少验证 `false` 只对应合法空 SRT。

## 4. 十四项重点结论

| # | 独立结论 |
|---|---|
| 1 | 通过。正式 MP4 的字幕确实写入画面，不是播放器加载外挂 SRT。 |
| 2 | 通过。同名 SRT 临时移走后，纯 MP4 仍从头播放到结束，`textTracks=0`，四个抽帧仍有字幕。 |
| 3 | 通过。开头、中间、结尾三个 active cue 中点均可见字幕；播放连续、切换时间与 cue 对齐，达到基本同步级别。 |
| 4 | 通过。由最终 timeline 和裁剪范围独立重算得到 14 cues；序号、毫秒时间、文本逐字符与正式 SRT 全等。 |
| 5 | 通过。真实无字幕空档仍导出 H.264/AAC MP4 和 0 字节合法 SRT，review 为 `false`，二次复用仍为 `false`。 |
| 6 | **不通过。** 中文、空格、`&`、圆括号、盘符冒号真实烧录成功；合法单引号目录真实烧录失败，见 B-1。 |
| 7 | 通过。FFmpeg、ffprobe、编码/时长、MP4/SRT/review 发布失败均不覆盖用户文件、不写伪 completed、不留正式或临时残留。 |
| 8 | 通过。原视频、timeline、analysis 在导出前或导出中发生哈希变化都会阻止发布。 |
| 9 | 部分通过。旧 review 缺字段不会误报；布尔值与 SRT 内容不一致仍可被复用，见 N-1。 |
| 10 | 通过。多个 `python.exe` 与 WindowsApps 同时存在时，WindowsApps 被排除，只返回第一个真实 Python。 |
| 11 | 通过。所选真实 Python 可运行 `liveclip --help`，无需用户关闭 Windows 应用执行别名。 |
| 12 | 通过。资产缺失提示列出 FFmpeg/ffprobe 和具体模型，并给出可复制的用户级环境变量命令；不要求管理员、不暴露 API Key。 |
| 13 | 通过。PR 未扩展到字幕编辑器、批量、多片段拼接、自动发布、ASR/分析核心或 TASK-008。 |
| 14 | 通过。审核前 HEAD 的三项 latest-head Actions 均为 completed/SUCCESS，完整日志未见隐藏失败。 |

## 5. 真实字幕烧录与播放证据

- 复用 Git 忽略目录中的真实 827.766 秒 MP4、169 段 timeline 和 completed analysis；没有调用
  ASR 或文本模型。
- 在新审核目录选择候选后，先勾选确认；入点增加 0.1 秒时确认自动清空且导出按钮禁用，再将
  出点减少 0.1 秒；重新预览后播放器时间真实前进、readyState 为 4、无媒体错误，再次确认导出。
- 新正式范围为 51.576 秒；ffprobe 容器时长 51.621016 秒，相差约 45 ms。输出包含且仅包含
  H.264 1080×1920 视频流和 AAC 音频流；review completed 且
  `subtitles_burned_in=true`，无 `.part` 残留。
- 临时移走同名 SRT 后，以只提供 MP4 的本地播放方式完整播放到 ended；浏览器显示
  `textTracks=0`、无解码错误。仅以 MP4 为输入，在开头、中间、结尾 active cue 中点及最长 cue
  中点抽帧，四帧均有画面内字幕。
- 三个抽查点的画面文字与当时 active cue 逐字符一致。没有用二次 ASR 冒充同步验证；同步结论
  限定为人工播放观察到的基本同步级别。
- 原视频、timeline、analysis 的 SHA-256 在导出前后完全一致；输出和验证帧均被 Git 忽略。

## 6. SRT 独立重算

- 从最终 `start_ms/end_ms` 与 timeline 独立裁剪、平移到 clip 0 点，没有调用生产
  `render_timeline_srt()` 作为预期值。
- 结果为 14 cues；正式 SRT 的 cue 数、序号、开始/结束毫秒、文本逐字符均完全一致。
- 所有 cue 满足 `0 <= start < end <= 51576 ms`；没有翻译、纠错、改写或越界。
- 烧录使用的临时 SRT 与最终独立 SRT 来自同一文本；三个画面抽查点与对应 cue 一致。

## 7. 字幕样式

- 真实竖屏 1080×1920 使用 `>1440` 档目标字号 32 px；普通 cue 为一行，最长抽查 cue 自然换为
  两行。白字、黑色描边、无明显阴影、底部居中且有安全边距，没有裁切或明显遮挡主体。
- 另以不含真实用户内容的 15 秒 1920×1080 合成视频完成真实烧录；`721..1440` 档目标字号
  28 px，长句在横屏保持一行且清晰可读，底部安全边距合理。
- `<=720`、`721..1440`、`>1440` 的静态边界回归分别覆盖 720/721/1440/1441，目标字号固定为
  24/28/28/32；目标像素到 libass 288 行坐标的换算与真实竖/横屏结果一致。

## 8. 空字幕与 review 兼容性

- 在真实 timeline 的无字幕空档导出约 2.02 秒 MP4：H.264/AAC 双流存在，独立 SRT 为合法
  0 字节，`subtitle_count=0`，result/review/session 均为严格布尔 `false`。
- 同一 completed review 连续加载两次均保持 `false`；页面脚本会显示“本片段没有可烧录字幕”
  与“独立字幕：已生成”，不会显示“已烧录”。
- 构造缺少字段的旧 completed review 后，schema 和 runner 都不复用、不误报，也不删除旧 review
  或旧输出。内容与布尔值不一致的漂移场景见 N-1。

## 9. 失败安全与输入保护

独立故障注入覆盖以下十类场景，全部验证旧 review/用户文件字节不变、没有新正式 MP4/SRT、
没有伪 completed、没有 `.part` 残留：

1. FFmpeg 失败；
2. ffprobe 失败；
3. 编码校验失败；
4. 时长校验失败；
5. MP4 发布失败；
6. SRT 发布失败；
7. review 原子替换失败；
8. 同名 MP4 与 SRT 同时已存在；
9. timeline 在导出中变化；
10. analysis 在导出中变化。

单引号路径失败也重复确认了相同清理性质。真实非空、空字幕导出前后，原视频、timeline、analysis
哈希均未变化。

## 10. Windows 启动器与资产根

- 在 Windows PowerShell 5.1 下调用生产函数，模拟 WindowsApps alias、两个真实 `python.exe`
  同时存在；解析器只返回首个真实 Python，且所选解释器成功运行 `liveclip --help`。
- 仓库 `.venv`、资产根 `.venv`、PATH 的优先级由专项测试验证；WindowsApps 自动排除，错误提示
  没有要求关闭或禁用应用执行别名。
- 含中文、空格、`&`、圆括号的视频路径经 PowerShell 调用后仍是一个完整 `--video` 参数。
- 未配置资产根且仓库缺资产时，提示明确列出 FFmpeg/ffprobe 和所选模型，包含可复制的用户级
  `LIVECLIP_ASSETS_ROOT` 设置示例；不扫描磁盘、不自动下载、不要求管理员、不泄露 API Key。

## 11. 自动测试、Actions 与安全扫描

- 定向回归：66 passed，0 failed。
- source-only base-schema-media：224 passed，1 deselected，0 failed，退出码 0。
- source-only asr-experiments：91 passed，2 deselected，1 个既有 `audioop` deprecation warning，
  0 failed，退出码 0。
- `pip check`：`No broken requirements found.`，退出码 0。
- 本地 tracked safety：190 files scanned，190 text files，0 issue；`git diff --check` 无问题。
- 审核前 latest-head run `31033493403` 的 head SHA 与审核基线一致。三项 job：
  `repository-safety`、`lightweight-tests`、`task-report-gate` 均 completed/SUCCESS；逐 job 阅读完整
  日志，并对合计 607 行日志扫描高置信失败标记，结果为 0。日志内三个 source-only stage 均明确
  `exit_code=0`，最终 `SOURCE_ONLY_RESULT.status=passed`。

## 12. 隐私、Git 与产品边界

- PR 相对 master 共 16 个预期文件；没有修改 `src/liveclip/asr/`、`src/liveclip/analysis/`，没有
  TASK-008 文件、字幕编辑器、前端框架、字体、模型、批量、多片段拼接或自动发布。
- tracked tree 与 PR diff 未发现真实 MP4/SRT/timeline/analysis/review、模型、字体、凭据、真实本地
  绝对路径、用户名或真实字幕正文。
- 本报告不包含真实字幕正文或本地绝对路径；所有真实/合成验证产物均位于 Git 忽略目录。

## 13. 评分

| 维度 | 得分 |
|---|---:|
| 字幕烧录真实可用性 | 17/25 |
| 字幕时间、文本与视觉质量 | 14/15 |
| 导出失败安全与用户文件保护 | 15/15 |
| Windows 启动器稳健性 | 15/15 |
| 测试与真实验证 | 8/10 |
| 代码简洁与维护性 | 6/10 |
| 隐私与 Git 边界 | 5/5 |
| 文档与可追溯性 | 4/5 |
| **总分** | **84/100** |

扣分集中在单引号路径的真实 FFmpeg 失败、缺少对应集成回归，以及 completed review 对
`subtitles_burned_in` 与 SRT 内容一致性校验不足。其余重点路径均有独立运行证据。

## 14. 最终建议

三选一结论选择第 3 项：**需要TASK-007-FIX，继续Draft**。

在 B-1 修复并补齐真实 Windows FFmpeg 单引号路径回归前，不得手动 Ready、merge 或启用
auto-merge。N-1 建议同一 FIX 收紧；修复后重新执行定向/source-only/真实路径验证与独立复核。
本审核不执行 TASK-008。
