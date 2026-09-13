# TASK-005-FIX-R｜审核页预览兼容性与轻量代理独立审核

总分：75/100
审核结论：不通过

审核日期：2026-09-05。未达到 85 分门槛，存在三项未关闭阻断。正式导出隔离检查通过，但不足以抵消路径写入安全与预览正确性问题。PR 必须保持 Draft；不允许用户据本次审核手动 Ready，也不允许手动 Squash and merge。

## 审核对象和边界

- 仓库：huangyongming0327-hash/live-stream-smart-clipping；PR #11。
- base：master，`0e38465d51f94c0cd69c450504f2f1d5c20e4481`。
- 实现分支：`task/TASK-005-FIX-preview-proxy`。
- 实现 HEAD：`5988ff5e0013740386c1acfa91ea00a9f2b03b2a`。
- 实现 Actions run：33953640746，API headSha 与上述 HEAD 一致；日志实际 checkout 的是该 PR merge ref `0f6bafd2973d130c057b6c8ef0e7c423fc7f4d47`，不混称为直接 checkout 实现提交。
- 独立读取 AGENTS、完整 12 文件 PR diff、TASK、RESULT、CURRENT_STATUS、preview/server/schema/probe/process runner/exporter、完整 review.js 和相关自动测试、三项实际 Actions 日志。
- 原始工作目录处于旧 master 且有既存未跟踪审核文件，故在 D 盘独立 worktree 检出指定实现分支。未改动原工作目录文件。仅新增本报告；按本次用户要求不更新 CURRENT_STATUS，不修改实现、测试、TASK 或 RESULT。
- 用户已完成并确认真实浏览器 UAT，通过范围全部接受为用户证据。本次没有调用 browser、computer use、GUI 点击，也没有读取真实媒体。测试中的 webbrowser.open 已被 fixture 替换，不打开浏览器。
- 独立探针与合成媒体全部位于 `runtime/temp/audit005/`（Git 忽略）；未安装依赖、模型或新 FFmpeg。公开报告使用路径占位符，不提交本机路径、运行 token、媒体或原始日志。

## 分维度评分

| 维度 | 得分 | 依据 |
| --- | ---: | --- |
| fallback 与前端状态正确性 | 17/25 | 常规去重与切换有效；迟到 play 超时竞态未关闭 |
| 代理编码、尺寸和低资源设计 | 15/20 | 编码参数与普通合成媒体通过；音轨相对时间偏移丢失 |
| 缓存、并发、原子发布及输入安全 | 8/15 | 生产锁、唯一临时文件有效；junction 写入逃逸及命中复核缺口 |
| token、Range、路径和本地服务安全 | 13/15 | localhost/token/常规 Range 正确；未验证缓存可直接读取、关闭等待限制 |
| 正式导出隔离及字幕/SRT回归 | 10/10 | API 和真实 exporter 参数始终是原视频，原有发布/字幕逻辑未改 |
| 自动测试、独立探针和 Actions 证据 | 8/10 | 必需测试均运行；部分源码断言和 fake 留下关键分支空缺 |
| 代码简洁性、范围、隐私和文档 | 4/5 | 范围合理且隐私扫描通过；测试覆盖描述偏强、存在冗余状态 |
| 合计 | 75/100 | 不通过 |

## 阻断问题

### B1 / P1：缓存目录 junction 可造成预期目录外写入与覆盖

位置：`src/liveclip/review/preview.py:193-206,240`。

`mkdir(exist_ok=True)` 接受已存在的目录 junction；临时文件与最终文件均沿该链接写入。随后 `os.replace` 覆盖目标同名文件，没有校验缓存目录是否为重解析点、解析后是否仍在绑定工作目录内，也没有对未知同名文件建立所有权边界。

独立 Windows 实测：仅在忽略目录内创建工作目录与另一独立目录，以 PowerShell `New-Item -ItemType Junction` 将前者 `.review_preview` 指向后者；后者预放按生产缓存名称命名的合成哨兵。调用真实 `ensure_preview_proxy` 和现有 FFmpeg 后，`junction_escaped=true`、`sentinel_overwritten=true`、本次 part 数量 0。没有接触或损坏用户文件；但生产行为确实会覆盖链接目标中的同名文件。普通 URL 路径穿越拒绝不能防止此本地文件路径风险。

最小修复要求：在缓存校验、创建临时文件、发布及媒体读取前拒绝异常文件类型和重解析点逃逸，校验实际目标属于受控缓存目录；拒绝覆盖不能确认属于本应用的既存文件；发布前重验目标以避免检查后目标变化。增加真实 Windows junction/文件链接/目录占位/同名哨兵测试，确认拒绝后无写入、无覆盖、无残留。

### B2 / P1：代理 play 超时后迟到启动绕过 endMs 自动暂停

位置：`src/liveclip/review/static/review.js:69-87,96-114,350-370`。

`Promise.race` 超时只结束等待，没有停止或失效化底层 `video.play()`。失败路径清除 `pendingStartMs`、令 `rangePreviewActive=false`，却没有取消迟到播放。此后播放器可能正常启动，而 `timeupdate` 的 end 判断始终被 false 状态跳过。没有播放请求代次来隔离旧调用与新候选。

独立 Node 探针实际执行生产 review.js，沿用现有 fake DOM，但把 play 改为可控 deferred Promise，并手动触发生产注册的超时回调：生成一次代理，选择 B（329.702—365.116 秒），点击预览，先超时，再令底层 play 启动并 resolve；发出 329.802 和 366 秒的 timeupdate。输出 `paused=false, rangePreviewActive=false, proxyPosts=1`，同时页面仍显示兼容预览播放失败。366 秒仍在 600 秒合成 session 内，已经越过 B 结束点。探针退出码 0，证明成功复现缺陷，不表示功能通过。

最小修复要求：超时/切换/新预览时使旧播放请求失效并停止其播放，旧 Promise 不得修改新状态；对迟到启动采取明确暂停或恢复受控区间策略。补充生产 JS 的可控定时器与 deferred play 测试：超时后迟到成功/失败、连续点击、候选切换、旧成功覆盖新状态，验证结束自动停止且代理 POST 保持一次。

### B3 / P1：独立归零音视频时间戳改变源音画相对时间

位置：`src/liveclip/review/preview.py:24-28,79-80,156-174`；`src/liveclip/media/probe.py` 的 StreamInfo 未保存起始时间。

视频 `setpts=PTS-STARTPTS` 与音频 `asetpts=PTS-STARTPTS` 分别减去自身起点，无法保留源文件的音画相对偏移。零起点容器不等于完整源时间轴正确；校验器只比较总时长，未比较流起点或音画相对位置。

真实 FFmpeg 合成三秒视频，音频输入使用 `-itsoffset 0.6`、2.4 秒正弦音。ffprobe：源视频 start=0.000000/duration=3.000000；源音频 start=0.576009/duration=2.423220。生产代理生成成功，视频仍为 0/3 秒，音频却变为 start=0.000000/duration=2.438005，即音频提前约 576 ms，总时长检查仍通过。候选按原视频时间审核时听到的内容会与原片时间不一致。这是合成媒体契约缺陷，不否定用户已通过的普通样本 UAT。

另对正常代理执行 stream copy 加 `-output_ts_offset 0.5`，得到容器 start=0.476009 的缓存，生产 validator 仍返回有效；说明所谓时间轴校验并未验证起点。

最小修复要求：以共同源时间基准归零并保留音视频相对偏移（必要时明确补齐开始空白/静音），记录并校验视频/音频起点和时长；缓存需验证零基准及源时间对应关系。补充有偏移音轨与非零容器起点的真实 FFmpeg 测试。不得改变正式 exporter 使用原片的隔离原则。

## 非阻断问题及 backlog

1. 缓存命中分支在输入 SHA 复核之前返回。独立探针生成有效缓存后只更改合成 timeline 文件，再调用仍返回 cached=true；视频/analysis 同样走这条分支。建议复用前及必要发布边界统一复核三项输入。当前正式导出仍会独立拦截输入变化，故未单列为正式导出安全阻断。
2. validator 未验证 Main profile、faststart、起点、不得大于源尺寸；且只检查首条音视频元信息，不能证明整段可解码。普通生成命令通过真实探针，但缓存的实际契约弱于报告表述。起点部分纳入 B3，其他作为补充加固。对超小、奇数尺寸、非方形像素、旋转元数据亦缺真实样本覆盖，不宣称这些已通过。
3. `/media/preview` 只 stat/open 固定路径，并不要求当前服务已完成 cache 验证。实测不存在时 404；预放未经验证的合成字节后直接 GET 200。建议只服务经校验的普通缓存文件，联同 B1 收紧路径。token 仍有效，不是匿名任意文件读取漏洞。
4. 服务 `daemon_threads=False/block_on_close=True`：关闭会等待已进入的生成线程；`subprocess.run` 仅有 14400 秒超时，没有 shutdown cancellation。它不是退出后假造 completed review，但可能长时间占用资源，锁上排队请求也不会主动取消。现有 heartbeat 测试只覆盖空闲服务；活跃转码关闭/断连测试应补充。本次未运行四小时极端关闭实验，不宣称即时退出。
5. `proxyRequested` 只写不读；多个失败/ready 布尔状态可进一步合并。原片媒体 error 提前请求代理而 play 拒绝较迟到达时，可能落在 ready 守卫之前未记录自动播放意图，建议纳入 deferred 测试。
6. HEAD 成功媒体路径不发正文；错误/session 路径仍调用未区分 HEAD 的 `_send_json`，是既有协议细节。静态 JS/CSS 是公开白名单资源，不含用户数据；主页面、session/API、两种媒体均要求 token。CLI 无自动打开时会有意输出带 token 的本地访问 URL，不能笼统称 token 从不出现在任何输出；请求日志已禁用，代理错误为固定安全文本。
7. TASK 最后两项未勾选与实现提交前的交接时序一致：PR 已实际存在且 run 33953640746 全绿；旧最终 handoff 原文未提供，不反推此前执行成功。本任务最终另行执行 Get-PRHandoff。此项不是实现阻断，不在审核中修改 TASK/RESULT/CURRENT_STATUS。

## 重点项目逐项结论

| 项目 | 独立结论 |
| --- | --- |
| 原视频优先 | firstLoad 只设置 /media；无初始化代理 POST。正常成功 play 无 fallback；error、play 拒绝/超时、无可解码视频轨进入统一请求流程。部分异常仍见 B2 |
| 编码与低资源 | 命令固定 libx264 Main/yuv420p、veryfast、CRF29、threads=2、AAC96k 双声道、faststart；无音源只映射视频，无强造音轨。低资源参数符合任务，未做全长峰值资源基准 |
| 尺寸 | 真实 1920x1080 降至 1280x720；320x180 无音不放大；16:9 与偶数尺寸通过。filter 限宽高，其他极端形状未验证 |
| 时间轴 | 普通零起点样本通过；带相对偏移样本失败，B3 |
| 缓存与原子性 | 文件名绑定版本及完整源 SHA；复用前 ffprobe；真实坏缓存重建；唯一 UUID part，finally 清理，仅验证后 replace。路径逃逸 B1；缓存命中输入复核缺口 |
| 同服务并发 | HTTP 并发测试真实进入 production preview_lock 和 ensure/cache，process/probe 被 fake；两请求仅一次 process。锁范围为同一服务，不保证多服务全局唯一 |
| 页面状态/切换 | ready 不再生成，proxyPromise 去重，错误不递归；既有 Node 真执行 JS 的 A→B 与旧 timeupdate 防护通过，但未覆盖 B→A、连续点击、正常原片、启动超时等所有宣称；B2 未关闭 |
| session 重载 | firstLoad 防止导出后 loadSession 把 src 切回原片；仍重新选择首候选并暂停，是现有行为 |
| 本地安全 | IPv4 127.0.0.1、随机 token_urlsafe(32)、constant-time 比较、拒绝额外/重复 token、白名单路由、固定代理错误、no-referrer/CSP；无代理时404，普通 GET/HEAD/Range206/416通过 |
| 断开与关闭 | BrokenPipe/ConnectionReset 被抑制，标准错误日志不输出路径/token；活跃转码可能继续至完成/超时，无取消机制，不宣称关闭立即结束 |
| 正式导出 | /api/export 传 self.app.inputs；exporter 的 -i 始终 inputs.video_path，未引用 preview path。代理存在的 API 测试通过；字幕烧录、独立 SRT、确认、一次导出、回滚、SHA复核保持，exporter diff为空 |
| 范围和隐私 | 12项改动局限本任务及状态/GUI边界说明；无 ASR、分析算法、模型、HLS/GPU框架、批量或 TASK-008；未发现新提交真实媒体或密钥，安全扫描0项 |

## 独立命令与结果

命令在审核 worktree 运行，python 从既有 D 盘项目 `.venv/Scripts` 临时置于 PATH 首位。Python 3.12.10、pytest 8.4.2、pydantic 2.13.4；Node v24.15.0。TEMP/TMP 指向 worktree 的 `runtime/temp/audit005`，未修改永久环境；真实 FFmpegPaths 显式指向既有 D 盘工具。

| 实际命令（本机绝对前缀脱敏） | 退出码 | 结果 |
| --- | ---: | --- |
| `python -m pytest tests/test_review_and_export.py -q` | 0 | 69项全通过，无skip；Node状态测试实际执行 |
| `.\tools\github\Invoke-SourceOnlyTests.ps1` | 0 | 基础268 passed/1 deselected（10.79s）；ASR91 passed/2 deselected（1.63s）；pip check通过；三stage均0 |
| `node --check src/liveclip/review/static/review.js` | 0 | 语法通过 |
| `git diff --check` | 0 | 无输出 |
| `git status --short` | 0 | 报告写入前无输出；发布前仅本报告 |
| `git diff --name-only 0e38465d51f94c0cd69c450504f2f1d5c20e4481...5988ff5e0013740386c1acfa91ea00a9f2b03b2a` | 0 | 12文件，与完整diff一致 |
| `.\tools\github\Invoke-RepositorySafetyCheck.ps1 -RepositoryRoot . -Scope Tracked` | 0 | 197文件、197文本、issue_count=0 |
| `python runtime/temp/audit005/probe.py <LOCAL_FFMPEG>` | 0 | 两类真实媒体、缓存、faststart、hash、坏缓存重建；junction首次创建失败，未当成功 |
| `python runtime/temp/audit005/edge.py <LOCAL_FFMPEG>`（PYTHONUTF8=1） | 0 | junction正式复现并生成Node脚本；初次因默认GBK读UTF8失败，改进程编码后复跑 |
| `node runtime/temp/audit005/probes/late-play.cjs src/liveclip/review/static/review.js` | 0 | B迟到播放缺陷复现；实际生产JS，不是源码字符串推测 |
| `python runtime/temp/audit005/timing.py <LOCAL_FFMPEG>`（PYTHONUTF8=1） | 0 | 偏移音轨、非零起点缓存、HTTP负面探针完成 |
| `python -m pytest tests/test_ffmpeg_install_source.py -q -k 'production_call_cannot_override_audited_source_fields or incomplete_archive_never_forms_stable_install'` | 1 | 5通过、1失败；子PowerShell Get-FileHash CommandNotFoundException |

合成媒体生成核心参数：`-f lavfi -i testsrc2=size=1920x1080:rate=12:duration=3`，有音样本增加 `-f lavfi -i sine=frequency=440:duration=3`；源编码 libx264/threads2/AAC。代理通过生产 ensure 函数与真实 FFmpeg/ffprobe，不 mock 编码器；输入对象使用测试 fixture 构造后绑定合成视频尺寸/时长/SHA，未运行 ASR 或语义分析。

普通HD结果：H.264 Main、yuv420p、1280x720、视频0/3秒，AAC LC音频0/3.018005秒，容器3.018005秒；小无音结果320x180、3秒、仅视频流。两者 moov 均在 mdat 前，第二次 cached=true 且mtime/SHA不变，三输入SHA不变，本次part=0。另有专门输入变更的负面样本，不能与正常“不变”样本混称。

HTTP独立探针：缺失代理404；多余参数403；错误token POST403；四种非法Range（零长度suffix、倒序、多range、非bytes单位）均416。现有生产锁测试、回滚测试、代理存在时export输入测试均在专项实际通过。

## 测试质量与全量 pytest 既知失败判断

专项不是单靠字符串断言：并发HTTP确实走生产锁与缓存；Node VM确实执行当前 review.js，并验证575.110—600.000的A切到329.702—365.116的B，旧timeupdate纠正起点，B结束暂停，代理POST一次。其fake play立即resolve，load也立即排队metadata，无法覆盖迟到播放。脚本没有再选A，故RESULT所述完整A→B→A自动覆盖偏强（用户人工双向UAT仍有效）。

`test_preview_validation_rejects_codec_pixel_format_size_duration_and_audio` 把多个错误同时放进一个probe，首先尺寸拒绝便返回，不能证明其余每个独立校验分支；有/无音、坏缓存和失败回滚多数fake，真实探针补充了正常格式。建议把每个坏字段独立参数化，并增加B1—B3探针对应回归。

RESULT的19项缺工具/标记及跨盘问题、之后10项Windows集成失败是实现方历史记录，本次没有把完整 `pytest tests -q` 重新跑全，也没有宣布完整pytest通过。独立重跑最相关的既知PowerShell失败组，确实5个参数拒绝通过，截断归档用例仍报Get-FileHash CommandNotFoundException；安装器、该测试与正式exporter在本PR diff均未改。此失败属于既有安装测试环境/命令可用性问题，无证据归因于预览改动；其余历史失败数及PTY成因没有逐一重现，保留未验证限制。当前新增代理核心问题由独立生产路径探针证实，绝不以环境失败为由忽略。

## 实现 HEAD 的 Actions 日志证据

读取 `gh run view 33953640746 --repo huangyongming0327-hash/live-stream-smart-clipping --json headSha,jobs,conclusion` 及 `--log`，下载日志仅保存在忽略目录。三job均completed/success：

- repository-safety（job101272885767）：`SAFETY_RESULT`为passed、Tracked、files_scanned=197、text_files=197、issue_count=0。
- lightweight-tests（job101272885594）：基础268 passed/1 deselected（13.02s），ASR91 passed/2 deselected（1.57s），仅audioop弃用警告；pip check无破损依赖；三个 `SOURCE_ONLY_STAGE_EXIT` 均0，最终status=passed。安装锁定依赖与editable包步骤成功。
- task-report-gate（job101272885733）：实际日志 `Task report gate passed with 1 report file(s).`，没有报告门禁错误。

日志只有source-only阶段显式打印数字退出码；safety/gate没有单独打印数字，不虚构原始日志中存在exit=0文本，其成功由脚本完成与job结果确认。绿色Actions证明所运行门禁通过，不能覆盖本报告已复现的缺陷。

## 发布与交接约束

仅用 `Publish-CodexAudit.ps1 -ConfirmScope -CommitMessage "audit: review TASK-005-FIX preview proxy"` 发布本报告；发布前检查除本报告外无改动并复跑source-only。发布后的新提交SHA不能自引用写入本提交，本报告不预先宣称后续Actions成功；后续由本次最终交接消息提供审核提交SHA、最新HEAD、最新三job实际日志和完整PR_HANDOFF。

结论保持不通过，B1/B2/B3均未修复。即使审核提交Actions全绿，也不得Ready、merge、auto-merge。本任务只发布审核证据，不代为修复，不修改任何其他项目文件。
