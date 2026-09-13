# TASK-005-FIX-R2｜审核页预览代理阻断修复复审

总分：79/100
审核结论：不通过

审核日期：2026-09-13 至 2026-09-14（北京时间）。B3 原音频相对偏移阻断已关闭；B1、B2 仍有可确定复现的问题，blocker 未全部关闭。低于 85 分门槛，且存在阻断，不允许据此 Ready 或合并。

## 审核对象与独立性

- 仓库：`huangyongming0327-hash/live-stream-smart-clipping`，PR #11，分支 `task/TASK-005-FIX-preview-proxy`。
- 审核实现 HEAD：`f1371503b8ad114c7ed8b6adef175c761a1a1f4a`。
- 基线 master：`0e38465d51f94c0cd69c450504f2f1d5c20e4481`。
- 开始前执行 `gh pr view 11 --repo huangyongming0327-hash/live-stream-smart-clipping --json headRefOid,headRefName,isDraft,title,body,url`，退出码 0，HEAD 完全匹配，Draft=true。补充探针后再次核对仍一致，autoMergeRequest=null。
- 原主工作区在旧 master，并有既存未跟踪的其他审核文件，未动它。使用已有 PR worktree，确认干净后仅快进到指定实现提交。普通 fetch 失败；HTTP/1.1 重试也失败；最后单命令使用系统已有本地代理完成 fetch（退出码 0）。没有改变全局 Git 配置或 force push。
- 独立读取目标版本 AGENTS、PR 信息与完整 15 文件 diff、TASK、RESULT、前次 AUDIT、CURRENT_STATUS、preview/server/schema/probe、完整生产 review.js、相关生产 exporter/process runner/outputs 和 B1/B2/B3 测试；实际执行测试与额外探针，没有依据 RESULT 推定通过。
- 本次唯一发布文件为本报告。遵从本次用户明确限制，不更新 CURRENT_STATUS、TASK、RESULT、旧 AUDIT、PR 描述、生产代码或测试代码。
- 没有 browser、computer use 或 GUI 自动化。用户既有真实 GUI UAT 仅作为既有产品验收证据；本次不将 Node 模拟媒体元素当作真实浏览器验收。
- 临时脚本、合成媒体、日志均在被忽略的 `runtime/temp/audit005r2/`。沿用 D 盘现有 Python 环境及 FFmpeg 8.1.2；对已有二进制创建 D 盘硬链接并复制忽略的安装标记供测试定位，未下载工具、模型或安装依赖。报告不包含本机绝对路径或运行 token。

## 分维度评分

| 维度 | 得分 | 依据 |
| --- | ---: | --- |
| fallback 与前端状态正确性 | 18/25 | 原片成功路径、一般迟到结果和 end 停止通过；同轮 Promise 完成及新请求 pending 仍被旧回调暂停 |
| 代理编码、尺寸和低资源设计 | 19/20 | 真实延迟音轨、无音、HD 降采样、faststart 通过；特殊时间轴/显示比例覆盖仍有限 |
| 缓存、并发、原子发布及输入安全 | 8/15 | 静态 junction/symlink 拒绝和输入 SHA 复核有效；变化后的清理越界、未知新文件覆盖未关闭 |
| token、Range、路径和本地服务安全 | 12/15 | token/GET/HEAD/206/416/穿越通过；服务只记路径，验证后替换文件仍可读取 |
| 正式导出隔离及字幕/SRT 回归 | 10/10 | exporter 无改动，API 保持原输入，相关回归及媒体集成通过 |
| 自动测试、独立探针与 Actions | 8/10 | 必需测试实跑；扩展调度和目录变化探针暴露现有测试盲点，全量失败如实记录 |
| 范围、隐私、代码与交付文档 | 4/5 | 范围和安全扫描通过；PR 描述数字过期，关闭阻断声明过强 |
| 合计 | 79/100 | 不通过 |

## 阻断问题

### B1 / P1：路径发生变化后，清理仍可越界；发布未保护未知新文件

定位：`src/liveclip/review/preview.py:310-361`，特别是发布前普通文件检查、`os.replace` 与 `finally: discard_temporary(temporary)`；`src/liveclip/media/outputs.py:39` 的清理直接按路径 unlink。

静态防护确实改进：`lstat`、Windows `FILE_ATTRIBUTE_REPARSE_POINT`、普通目录/文件检查以及 v2 标记能拒绝事先存在的 junction、文件 symlink、目录占位、无标记目录、异常目标。五项 Windows 定向测试实际全部通过，外部哨兵在这些静态场景中未变化。缓存命中前也复核三项输入 SHA。

但所有权标记只证明目录内容有固定文本，没有固定本次操作使用的目录或文件身份。独立真实 Windows 文件系统探针在生产 `process_function` 注入点完成以下调度（编码字节/probe 使用现有 fake，路径校验、发布和 finally 均执行未修改的生产代码）：

1. 让 process 正常写出本次 UUID `.part.mp4`。
2. 将其 v2 目录移到同一合成工作区的 `v2-owned-moved`；在原 v2 位置创建指向另一个合成目录的真实 junction。
3. 外部合成目录预放一个与本次 part 同名的哨兵。
4. process 返回；生产校验拒绝 junction，但 finally 没有安全检查，沿旧路径删除了外部哨兵。原目录中的本次 part 仍在。

实际输出：`rejected=true, external_sentinel_exists=false, owned_part_remains=true`。没有接触用户原视频或用户文件；被删除的是探针专用合成哨兵。这同时否定了“外部哨兵不变”和“失败后无本次 part 残留”的无条件声明。发布前复核不能替代清理前的安全边界。

另一确定性探针：初始目标不存在，process 写完临时代理后，在最终缓存路径新建普通文件 `unknown-file-created-during-encode`。返回后，发布前只检查它是普通文件，`os.replace` 将其覆盖。结果：`unknown_preserved=false, published=true, parts=0`。该文件并非先前确认拥有的损坏缓存；目录标记无法确认这个新出现文件的所有权。

关联服务缺口：`server.py:353-380` 只登记 `preview_path`，每次 GET 的 `validate_preview_media_path` 仅检查路径/类型/标记。先 POST 成功，再将普通代理文件替换为未验证字节，GET 仍返回 200 和该字节。独立结果：启动前 GET=404，POST=200，替换后 GET=200，`unvalidated_body_served=true`。因此“启动时不直接服务预存文件”已修复，“当前提供的文件确曾被本服务验证”仍未完整成立。

修复要求：将创建、校验、发布、读取和失败清理绑定到同一受控目录/文件身份；对发布期间新出现或身份变化的目标停止，不覆盖；清理不能沿已变化的父路径删除文件；读取时识别已验证对象被替换。加入上述调度的回归。仅再次添加路径 exists/lstat 不能证明检查与后续使用之间没有变化。

### B2 / P1：旧 play 回调仍能暂停当前新请求

定位：`src/liveclip/review/static/review.js:77-117`。旧 Promise 成功回调以 `state.activePlayRequestId !== state.playRequestId` 决定 pause；但新请求只有在 `await Promise.race` 恢复后才设置 activePlayRequestId。新请求 pending 或其成功 continuation 尚未执行时，旧回调仍获准暂停共用 video。

独立 Node VM 直接读取目标生产 review.js，复用现有 fake DOM/deferred 工具，另行增加完成顺序；生产文件和提交内测试均未修改。既有测试中 `current.resolve(); await currentPending; old.resolve()` 强制等到新状态生效，掩盖这一空档；且部分断言只看最终停止状态，不能证明播放期间未被错误暂停。

复现：A 请求超时，启动 B 请求；在同一同步轮依次 `current.resolve(); old.resolve();`，然后等待两请求及微任务结束。实际 `paused=true, rangePreviewActive=true, proxyPosts=1`。新播放被旧回调暂停，但状态仍认为当前播放有效。未先超时、直接连续点击的相同调度也复现。另一顺序是新请求仍 pending 时先 resolve 旧请求，实际 `extraPause=1`；真实媒体元素的 pause 还可能使 pending play 拒绝，不能依赖 fake 后续 resolve 能恢复来认定安全。

已确认通过的分支：独立超时后迟到成功被暂停、迟到失败被消费；新请求完全启动后再返回旧成功不干扰；切换发生在超时前的 A→B→A 后旧失败不覆盖新状态；当前 A/B 在自己的 end_ms 停止；所有代理场景 POST=1，无递归；原片兼容场景 POST=0。B2 原来的“迟到成功无人管理”情形有所修复，但用户要求的旧 Promise 不暂停当前有效请求尚未满足。

修复要求：分离新请求已经开始等待和已完成启动两种所有权状态，使旧结果无法暂停较新请求；处理同轮完成顺序，避免 paused 与 active 状态矛盾。测试应在播放中间检查 paused、pause 次数、代次及消息，再验证 end，不只检查最后的停止状态。

## B3 与其他重点复核

| 项目 | 独立结果 |
| --- | --- |
| 延迟音轨的可听内容 | 真实 3 秒 1920×1080/12fps 视频，音频 `-itsoffset 0.6`、2.4 秒正弦音；源音频 start=0.576009，生产代理 silencedetect 的 silence_end=0.599229 秒。不是只看流 start=0；原 B3 延迟偏移已关闭 |
| 零起点伪缓存 | 正常代理 stream-copy 加 `-output_ts_offset 0.5`，生产 validator 返回无效 |
| 音频早于视频 | 另合成视频 start=0.583008、音频 start=0；执行真实生产裁剪/补齐路径，代理音频尾部静音从 3.016961 秒开始。代码实际使用相对差 atrim 后再归零。此样本没有独立可辨识语音事件，不扩大为所有早起点媒体的逐内容同步验收 |
| 编码和尺寸 | 延迟样本代理 H.264 Main/yuv420p、1280×720、AAC；普通无音样本 320×180、无音轨、未放大；早起点样本640×360。普通方形像素比例保持 |
| 低资源/faststart/时长 | 生产命令固定 libx264/veryfast/CRF29/threads=2、AAC96k；独立检查三个 MP4 的 moov 均在 mdat 前。前两代理完整3秒；早起点样本容器3.6秒，保留现有容器时长口径 |
| 缓存与重启 | 三个真实样本第二次 cached=true。新服务先 GET=404，首次 POST=200且cached=true，之后HEAD=200；验证重启后复用，非仅同一 Python 对象复用 |
| 输入与临时文件 | 三个正常合成样本视频/timeline/analysis SHA 前后不变，无本次part；路径变化负面样本的清理失败另见B1，不混称全部无残留 |
| 原片可播放 | 独立执行生产JS：播放中paused=false/active=true，到B的end停止；usingProxy=false、POST=0 |
| token/HTTP | 专项实际覆盖token、GET/HEAD、206、416、穿越、安全响应；固定白名单、constant-time token比较和localhost绑定仍在。预存文件启动时404，验证后替换缺口见B1 |
| 并发与原子性 | 两真实HTTP并发请求走生产preview_lock，仅一次fake process；同服务去重通过。普通路径验证后os.replace发布、失败不生成completed review；未知新目标覆盖见B1 |
| 正式导出 | API传self.app.inputs，exporter的-i始终inputs.video_path；exporter相对基线diff为空，不引用preview。代理存在时原片参数测试、字幕滤镜/独立SRT/回滚/完成态检查通过；媒体集成2项通过。既有用户字幕视觉验收保留，没有重做GUI |
| 范围与隐私 | 完整15文件diff仅review/proxy、probe、测试、任务/报告/状态与GUI边界说明；ASR、analysis算法、模型、批量、HLS、GPU系统、TASK-008无修改。媒体/二进制/模型/环境文件tracked清单为空；repository safety 199文本、0问题 |

## 实际命令、退出码和结果

命令均在目标worktree运行；`python`为既有D盘Python 3.12.10，Node v24.15.0，FFmpeg 8.1.2。进程级PATH/PYTHONPATH指向现有环境和本次src，TEMP/TMP指向忽略的D盘审核目录，PYTHONUTF8=1。未修改永久环境。为显示pytest数量使用 `-o addopts=` 覆盖项目默认的额外 `-q`，不改变测试选择。

| 命令 | 退出码 | 实际结果 |
| --- | ---: | --- |
| `python -m pytest tests/test_review_and_export.py -q`，随后显式计数 `python -m pytest tests/test_review_and_export.py -o addopts= -q` | 0 / 0 | 78 passed，8.31s，无skip |
| `python -m pytest tests/test_media_unit.py -o addopts= -q` | 0 | 29 passed，0.31s |
| `python -m pytest tests/test_media_integration.py -o addopts= -q` | 0 | 2 passed，2.80s |
| `python -m pytest tests/test_review_and_export.py -o addopts= -q -k 'rejects_junction or rejects_file_symlink or rejects_unowned or rejects_abnormal or never_serves_unvalidated'` | 0 | 5 passed，73 deselected；真实Windows junction和symlink创建成功 |
| `python -m pytest tests/test_review_and_export.py -o addopts= -q -k deferred_play` | 0 | 1 passed，77 deselected；执行生产JS |
| `node tests/review_deferred_play_test.cjs src/liveclip/review/static/review.js` | 0 | 现有五组结果满足现有断言；不覆盖同轮settlement空档 |
| `python -m pytest tests/test_review_and_export.py -o addopts= -q -k real_ffmpeg` | 0 | 2 passed，76 deselected，1.26s；未skip |
| `python runtime/temp/audit005r2/probe.py` | 0 | 确定复现未知新目标覆盖、验证后替换文件被HTTP提供；退出0表示探针完成，不表示安全通过 |
| `python runtime/temp/audit005r2/junction-race.py` | 0 | 拒绝发布但删除外部合成哨兵、本次原part残留；B1复现 |
| `node runtime/temp/audit005r2/independent.cjs src/liveclip/review/static/review.js` | 0 | 连续点击三种顺序、A→B→A；同轮完成paused=true/active=true |
| `node runtime/temp/audit005r2/timeout-order.cjs src/liveclip/review/static/review.js` | 0 | 先超时后新请求的三种顺序；同轮完成同样复现B2 |
| `node runtime/temp/audit005r2/original.cjs src/liveclip/review/static/review.js` | 0 | 原片成功、end停止、POST=0 |
| `python runtime/temp/audit005r2/media.py` | 0 | 三个真实合成媒体及重启HTTP缓存复用，量化结果见上表 |
| `.\tools\github\Invoke-SourceOnlyTests.ps1` | 0 | 基础277 passed/1 deselected（11.71s）；ASR91 passed/2 deselected（1.36s）；pip check通过；三stage退出0 |
| 上述入口的ASR实际子命令：`python -m pytest .\experiments\asr\tests -k not existing_399_sentence_info_result_is_byte_for_byte_reproducible` | 0 | 91 passed/2 deselected，只有既有audioop弃用警告；未运行模型识别 |
| 上述入口的 `python -m pip check` | 0 | No broken requirements found. |
| `python -m pytest tests -q`；显式计数复跑 `python -m pytest tests -q -o addopts=` | 1 / 1 | 314 passed, 2 failed，计数复跑40.18s；没有声称全量通过 |
| `node --check src/liveclip/review/static/review.js` | 0 | 语法通过 |
| `node --check tests/review_deferred_play_test.cjs` | 0 | 语法通过 |
| `git diff --check`；`git diff --check 0e38465d...HEAD` | 0 / 0 | 无输出 |
| `.\tools\github\Invoke-RepositorySafetyCheck.ps1 -RepositoryRoot . -Scope Tracked` | 0 | passed，files_scanned=199，text_files=199，issue_count=0 |
| `git diff --stat 0e38465d...HEAD`；`git diff --numstat 0e38465d...HEAD` | 0 / 0 | 15文件，2454插入/26删除；逐项读diff |
| `git ls-files '*.mp4' '*.wav' '*.mp3' '*.srt' '*.exe' '*.onnx' '*.safetensors' '*.env'` | 0 | 无tracked匹配；结合全文安全扫描和diff审阅未发现真实媒体/凭据/本机路径/运行数据进入PR |
| `git diff --name-only 0e38465d...HEAD -- experiments src/liveclip/asr src/liveclip/analysis tools/Install-FFmpeg.ps1` | 0 | 无越界修改 |
| `git diff 0e38465d...HEAD -- tools/Install-FFmpeg.ps1 tests/test_ffmpeg_install_source.py src/liveclip/review/exporter.py` | 0 | 三者均无变化 |
| `git status --short` | 0 | 报告写入前为空；发布范围仅本报告 |

全量两项失败分别是 `test_incomplete_archive_never_forms_stable_install` 和 `test_matching_hash_corrupt_archive_fails_extraction_without_publication`。实际子PowerShell在安装器Get-FileHash步骤报CommandNotFoundException，未抵达预期SHA mismatch或解压失败文本，导致测试断言失败。相关测试与安装器、其process解码实现未在PR改变，前次审核也已记录同类Get-FileHash失败；本次独立复现与历史一致，没有证据将它归因于预览改动。具体环境为何缺该命令尚未修复/查定，不将其写成所有机器必现或安装器业务断言已通过；本次不修改无关安装器。

## 指定 HEAD 的 Actions 实际证据

读取 `gh run view 34760743156 --repo huangyongming0327-hash/live-stream-smart-clipping --json headSha,status,conclusion,jobs` 及 `--log`，命令退出码0。run headSha与审核SHA完全一致，三job均completed/success。日志checkout的是PR测试merge ref `54b15556295f342ab12e370923a15900ac12e2a8`，明确由指定实现HEAD与指定master组成，不混称直接checkout实现HEAD。

| job | 实际日志 |
| --- | --- |
| task-report-gate / 103733024972 | Task report gate passed with 2 report file(s).；13:46:07Z完成 |
| lightweight-tests / 103733024986 | 275 passed, 2 skipped, 1 deselected（15.04s）；ASR91 passed/2 deselected/1 warning；pip check无破损；三个SOURCE_ONLY_STAGE_EXIT均0；13:46:45Z完成 |
| repository-safety / 103733024988 | SAFETY_RESULT passed，Tracked，199文件/199文本，issue_count=0；13:46:09Z完成 |

run链接：https://github.com/huangyongming0327-hash/live-stream-smart-clipping/actions/runs/34760743156 。CI没有本地忽略FFmpeg，两个real_ffmpeg用例具有缺工具skip分支；日志未打印逐用例skip原因，不能把CI写成277全通过。本文本地通过既有FFmpeg实际运行了这两项，277与275+2必须区分。

## 交付一致性、已知限制与非阻断 backlog

1. PR描述仍写69 passed / 268 passed；TASK与RESULT新增FIX2节写78 / 277。独立本地实跑确认78 / 277。RESULT前面的“最终”章节及CURRENT_STATUS历史段仍保留69 / 268，虽追加新版说明，交付口径仍不统一。本报告如实记录，不修改PR描述或其他报告。
2. RESULT/TASK宣称三个阻断关闭，现有测试确实绿，但独立反例证明B1/B2不能关闭。此点不是只需改数字的文档问题。
3. 转码取消/关闭等待未新增机制；同服务锁不等于跨服务全局唯一。未进行四小时转码超时、全长峰值资源或进程强杀压力验收。
4. 缓存validator仍以元信息为主，不验证整段可解码或每次复用faststart；早视频起点、旋转/SAR、超小/奇数尺寸等不扩大宣称。B3通过仅代表原延迟偏移和非零起点伪缓存阻断按实测关闭。
5. HEAD错误响应/session响应仍沿用发送JSON正文的实现，既有协议细节不在本次修改。核心token/媒体HEAD/Range通过不意味着覆盖所有HTTP边界。
6. 所有独立探针只保留本地忽略目录；公开报告提供调度、位置与真实结果。没有新建生产回归测试，因为本次只允许发布审核报告。下一实现任务应把反例落为正式测试。

## 发布与停止条件

发布仅本报告，使用审计发布脚本的仅AUDIT范围门禁，发布前重跑source-only、差异及隐私检查。审核提交后的SHA不能自引用写入本提交，本文不预先宣布后续Actions成功；最终消息提供最新HEAD三项Actions完成状态与实际 `Get-PRHandoff.ps1` 输出。

PR保持Draft，不Ready、不merge、不auto-merge、不force push、不执行TASK-008。即便报告提交后的Actions全绿，本次结论仍为不通过，B1/B2仍未关闭。

发布证据补记：报告写入后source-only再次为277 passed/1 deselected、ASR91 passed/2 deselected、pip check通过；PublishCandidates扫描200文本、0问题。首个仅报告提交 `9c62269857be5127f7763b48e05c53add4ce6540` 的push出现远端ref锁错误，但随后Git远端与REST ref均确认该提交已存在，普通重推退出0、Everything up-to-date；PR API仍滞留旧HEAD。手动触发现有workflow得到run `34767566644`，其headSha确为该审核提交，三job均success：基础275 passed/2 skipped/1 deselected，ASR91 passed/2 deselected，pip check通过，safety200文件/0问题。该次为workflow_dispatch，报告门禁按全仓40报告通过，不冒充PR差异门禁。本补记仍仅修改本报告；继续以最终PR同步后的最新HEAD检查及handoff为准，不把旧HEAD的PR状态作为交付成功。
