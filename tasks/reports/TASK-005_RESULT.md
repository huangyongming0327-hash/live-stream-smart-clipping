# TASK-005 RESULT｜候选审核与单片段导出

## 1. 任务状态与范围

- TASK-004 PR #6 已确认合并，本任务从最新 `master` 创建规定分支。
- 单视频、单 timeline、单 analysis、单次审核、单片段导出已经实现。
- fake 工具自动测试、完整 source-only 和一组真实浏览器/媒体闭环均已完成。
- 当前等待 Draft PR latest-head 三项 Actions 和独立审核；没有执行 TASK-006。

## 2. CLI 与三个输入

```powershell
python -m liveclip review `
  --video "<PATH>\source.mp4" `
  --timeline "<PATH>\timeline.json" `
  --analysis "<PATH>\current_analysis.json" `
  --output "<OPTIONAL_OUTPUT_DIR>"
```

`--output` 省略时，输出目录为原视频旁的 `<视频名>_exports`。启动前校验 MP4、视频流、
时长、completed timeline、completed analysis、视频 SHA、timeline SHA 和 candidate 范围；
不匹配时 CLI 单行失败、非零退出且不显示 traceback。

## 3. 页面、预览与入出点调整

- 页面只使用项目内 HTML/CSS/JavaScript，无前端框架和外部资源；
- 左侧显示排名、标题、总分、时长、理由、风险和“待审核/已导出”状态；
- 右侧使用原生 `<video controls>` 预览服务启动时绑定的唯一 MP4；
- 点击候选跳到入点，“预览调整后片段”从最终入点播放并在最终出点暂停；
- 显示当前时间和最终片段时长；
- 两个原生滑块、两个数字输入、±1 秒、±0.1 秒和恢复 AI 范围均已提供；
- 服务端再次约束 `0 <= start < end <= 视频时长` 和 1—180 秒，保存到毫秒。

浏览器必须能够直接解码输入 MP4；不兼容时页面明确提示，本任务不会生成代理。

## 4. 人工确认门禁

所有 AI 候选默认都是“待审核”。可以默认选中第一项用于预览，但确认框默认未勾选、
导出按钮默认禁用。排名、分数和 `recommended=true` 都不会自动批准。浏览器和服务端均
要求用户明确勾选“我已人工预览并确认导出这个片段”；服务端只接受严格布尔 true。
页面固定提醒发布前人工复核内容、营销表述、隐私和健康风险。

## 5. localhost、token 与 Range

- 临时服务仅绑定 `127.0.0.1` 的系统分配端口，不监听 `0.0.0.0`；
- 每次启动生成随机访问 token，页面、session、视频、heartbeat、shutdown 和导出 API
  均校验 token；
- URL 不能选择本地路径，媒体端点只读取启动时绑定的一个视频；
- `..` 路径穿越、额外 token 参数、错误 token 和非法 Range 均拒绝；
- 视频端点支持普通、显式区间和后缀字节 Range，真实浏览器可拖动并播放；
- 请求日志关闭，避免记录 token；错误不打印本地绝对路径或 traceback；
- 页面关闭事件会请求停止，心跳超时覆盖浏览器硬关闭；`Ctrl+C` 也可停止；
- 页面和服务不访问互联网，电池供电时不检查、不暂停。

## 6. MP4 导出与发布顺序

输出名为 `<视频名>_<candidate_id>.mp4` 和同名 `.srt`。FFmpeg 使用：

```text
-c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p
-c:a aac -b:a 160k -movflags +faststart
```

先生成临时 MP4，再由 ffprobe 验证文件非空、视频/音频流、H.264/AAC 与目标时长误差
不超过 1 秒。正式 MP4/SRT 使用无覆盖发布；同名存在或发布竞态都清楚失败。成功发布
两个媒体输出后，才原子替换 analysis 同级 `review_current.json`。FFmpeg、ffprobe、写入
或发布失败会清理本次临时/已发布输出，不生成 completed review，并保留旧 review。
原视频导出前后再次计算 SHA，变化即阻断发布。

## 7. SRT 裁剪与平移

SRT 只从 timeline 生成，不依赖旧 SRT。所有与最终范围相交的 segment 会裁剪到范围，
整体减去 `final_start_ms`，从序号 1 连续编号并强制时间不重叠。文本保持 timeline 原值，
使用 UTF-8 和标准 `HH:MM:SS,mmm`。范围内没有字幕时仍导出 MP4 和合法空 SRT，并在
页面提示。

## 8. review_current.json

review 只记录一个明确确认且成功导出的候选，包括：

- analysis/timeline/video 文件名；
- 程序计算的 analysis 和 timeline SHA-256；
- candidate ID、原始与最终毫秒范围、UTC 审核时间；
- `approved=true`；
- MP4/SRT 文件名和 `completed=true`。

不写 API Key、字幕全文或本地绝对路径；不修改 `current_analysis.json`；新导出成功前不
覆盖旧 review。

## 9. 自动测试与 source-only

- TASK-005 专项：38 passed、0 failed；使用临时文件和 fake FFmpeg/ffprobe，不处理真实媒体。
- 覆盖输入绑定、SHA、completed 状态、空候选、候选字段、默认待审核、确认、时间边界、
  恢复 AI 范围的页面控制、SRT 裁剪/平移/空结果/格式、命名、无覆盖、失败回滚、旧 review、
  源视频不变、无音轨输入、H.264/AAC 校验、localhost、token、Range、路径穿越、重复导出、
  页面关闭、服务启动时序、CLI 安全错误和 TASK-006 未实现。
- 最终 source-only：
  - base-schema-media：196 passed、1 deselected、0 failed；
  - asr-experiments：91 passed、2 deselected、1 个既有 deprecation warning、0 failed；
  - `pip check`：`No broken requirements found.`；
  - 三阶段退出码均为 0，`SOURCE_ONLY_RESULT.status=passed`。
- GitHub latest-head 的 `repository-safety`、`lightweight-tests` 和 `task-report-gate` 由
  Draft PR 执行；提交前不伪造状态，最终证据以 PR handoff 为准。

## 10. 真实浏览器与导出验证

一组 Git 忽略的真实 827.766 秒 MP4、169-segment timeline 和 6-candidate analysis 完成：

- 本地审核页面正确显示 6 个候选，全部默认待审核；
- 原视频浏览器元数据就绪、时长正确、无播放错误，候选预览能从入点连续播放；
- 确认框初始未选且按钮禁用；
- 使用数字输入把一个候选出点手动减少 0.500 秒，滑块同步；
- 原候选时长：51.776 秒；最终目标时长：51.276 秒；
- 本地导出计时：约 18.573 秒；
- MP4 大小：27,639,402 bytes；
- ffprobe：51.321 秒，目标误差约 +45 ms，视频 H.264、音频 AAC；
- 导出 MP4 在真实浏览器播放到中段，`readyState=4` 且无解码错误；
- SRT：14 条，首条从 `00:00:00,000` 开始，末条结束于最终范围；编号和时间单调；
- SRT 与程序从真实 timeline 对最终范围重新渲染的结果逐字节一致，文本未改写；
- review 的 SHA、原始/最终范围、approved/completed、文件名和无绝对路径均正确；
- 原视频、timeline、analysis 前后 SHA-256 分别一致；
- 浏览器硬关闭后服务自动停止，最终无监听端口和无残留 Python 审核进程。

公开报告不包含真实路径、候选标题、字幕、用户内容或运行 token。

## 11. 隐私与 Git 边界

真实视频、字幕、timeline、analysis、review 和导出全程留在 D 盘本地，没有发送到互联网。
`.gitignore` 覆盖媒体、SRT、`timeline.json`、`current_analysis.json`、
`review_current.json`、`*_exports/`、`local-data/`、运行状态和项目本地 FFmpeg。真实输入、
输出和运行数据均不在本次 Git 候选中。

## 12. 修改文件

- 实现：`src/liveclip/review/`、`src/liveclip/cli.py`；
- 打包：`pyproject.toml`；
- 测试：`tests/test_review_and_export.py`；
- 安全：`.gitignore`；
- 文档：README、CURRENT_STATUS、DECISIONS、TASK 和本 RESULT。

## 13. 已知限制与未实现范围

- 只支持浏览器可直接播放的 MP4，不生成代理；
- 单个进程只审核一组三输入并最多成功导出一个片段；
- 不提供批量、多片段拼接、队列、代理、波形、缩略图、帧级编辑、键盘快捷键系统、
  GPU 选择、stream copy、字幕样式或烧录、竖屏、水印、封面、发布文案、自动上传、
  完整启动器或安装包；
- 不修复 TASK-003/TASK-004 非阻断 backlog，不执行 TASK-006。

## 14. 下一步与回滚

下一步只建议对 Draft PR 最新 head、完整 diff、RESULT、真实验证边界和三项 Actions 日志
做独立审核；继续禁止 TASK-006。

若独立审核要求回滚，使用普通 Git revert 回退 TASK-005 提交，不重写历史、不 force push。
Git 回滚不会触碰任何 Git 忽略的真实输入或导出；这些本地文件继续由用户自行保留和管理。
