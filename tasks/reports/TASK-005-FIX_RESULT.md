# TASK-005-FIX RESULT｜审核页预览兼容性与轻量代理

## 1. 结果

审核页继续先加载原视频；浏览器不能解码视频轨、播放报错或播放启动超时时，页面会自动请求一个
本地完整时长预览代理，并切换到代理继续审核。代理只用于审核预览，正式导出仍只接收绑定的原
视频。原片能正常显示视频轨时不生成代理。

本任务从包含 TASK-007、TASK-004-FIX 与已合并 PR #10 的最新 `master` 创建
`task/TASK-005-FIX-preview-proxy`。未修改 ASR、爆点分析、模型或 TASK-004-FIX，未执行
TASK-008。

## 2. 代理契约

- 缓存文件位于当前工作目录的 `.review_preview`，名称包含代理版本和完整原视频 SHA-256；
- FFmpeg 使用 CPU `libx264`、Main profile、yuv420p、`veryfast`、CRF 29 和 `-threads 2`；
- 最大尺寸为 1280×720，不放大，保持宽高比并输出偶数尺寸；
- 原片有音频时输出 AAC 96 kbps 双声道，无音频时不强造音轨；
- 视频和音频时间戳从 0 开始，生成完整源时长代理，候选 `start_ms/end_ms` 可直接复用；
- MP4 使用 `+faststart`；缓存必须再次通过 ffprobe 的编码、像素格式、尺寸、宽高比、时长和
  音频契约校验；
- 生成写入唯一 `.part.mp4`，输入哈希复核和代理校验全部成功后才原子发布。失败清理本次
  `.part`，不把损坏文件当缓存，也不覆盖已验证缓存。

服务端新增 token 保护的 `POST /api/preview-proxy` 与 `GET/HEAD /media/preview`。代理媒体沿用
原媒体的 Range 行为，包括 206、416 和 `Accept-Ranges: bytes`。同一审核服务以锁串行代理请求，
第二个请求在首个生成完成后直接命中缓存。

## 3. 浏览器 fallback

页面加载时仍把视频源设为 `/media`。以下任一情况进入同一个去重后的 fallback：

- 原媒体触发 `error`；
- 点击“预览调整后片段”时 `play()` 拒绝或 3 秒内未启动；
- 浏览器跳过不支持的视频轨、只播放音频，导致元数据完成但 `videoWidth/videoHeight` 为 0。

代理准备好后页面切换到 `/media/preview`，保留当前候选和人工调整后的毫秒范围。切换候选不会
切回原片；播放到 `end_ms` 仍自动暂停。代理失败时页面显示明确失败状态，不允许把失败冒充为
可预览状态。

人工 UAT 先后暴露了两个前端状态问题并已修复：代理 ready 后的重复预览失败路径仍可能绕回
fallback；从较晚候选切换到较早候选时，旧候选排队中的 `timeupdate` 会用新候选 `end_ms`
再次暂停播放器并覆盖新起点。最终实现分别用 `proxyReady` / `usingProxy` 的不可递归守卫、
共享中的 `proxyPromise`、`rangePreviewActive` 和 `pendingStartMs` 隔离生成状态、代理播放错误、
区间播放状态与候选切换定位。代理自身播放失败只显示“兼容预览播放失败”，不会再次请求生成。

## 4. 自动测试

review/proxy 专项最终结果：69 passed、0 failed。覆盖：

- 原片优先、三种 fallback 入口、音频可播但视频轨不可解码；
- H.264、yuv420p、AAC/无音频、最大尺寸、宽高比、完整时长和 2 编码线程；
- 首次生成、缓存复用、损坏缓存重建、生成失败回滚和 `.part` 清理；
- 两个并发 HTTP 请求只启动一个 FFmpeg；
- 同候选重复预览、连续点击、A→B→A 候选切换、旧 `timeupdate` / media error 隔离和新候选
  `start_ms` 确定性定位；
- token、GET、HEAD、Range 206/416、路径穿越拒绝和响应不泄露路径/token；
- 正式导出即使代理存在也只接收 `ReviewInputs.video_path` 原视频；
- 中文、空格、`&`、括号和单引号组合路径；
- 字幕烧录、独立 SRT 和既有审核行为继续通过。

最终完整 source-only：

- base-schema-media：268 passed、1 deselected、0 failed；
- asr-experiments：91 passed、2 deselected、0 failed；只有既有 `audioop` deprecation warning；
- `pip check`：`No broken requirements found.`；
- 三个 stage 退出码均为 0，`SOURCE_ONLY_RESULT.status=passed`。

任务早期直接运行全量 `pytest tests -q` 时，19 个需要 FFmpeg 安装标记的 integration 用例因当前
公开工作副本缺少本地忽略的安装标记而失败；同时默认 C 盘临时目录触发跨盘硬链接限制。使用
已核对的本地忽略安装标记和 D 盘临时目录后，全量测试仍有 10 项 Windows PowerShell 集成失败：
多数断言受到 PTY 强制换行影响；非 PTY 定向复测的 5 个生产参数拒绝用例通过，但
`test_incomplete_archive_never_forms_stable_install` 仍因子 PowerShell 返回
`CommandNotFoundException` 而失败。因此没有把完整 pytest 记录为通过；本任务规定的
review/proxy 专项、统一 source-only、ASR experiments 和 `pip check` 均已通过。

## 5. 真实 Windows FFmpeg

全部媒体均为本地合成测试数据，位于 Git 忽略目录。没有读取或上传真实媒体、字幕、timeline、
analysis、review 或用户数据。

代理首次生成和缓存复用通过。高分辨率合成样本生成的代理为 H.264/yuv420p/AAC、1280×720、
28.032 秒，原片为 1920×1080；首次生成后第二次调用直接命中缓存。最终浏览器样本代理为：

- H.264 Main、yuv420p、320×180；
- AAC LC、双声道；
- 视频起点 0.000 秒、音频起点 0.000 秒、容器时长 28.010 秒；
- 933,333 bytes，SHA-256
  `a4a47d96c15d712a3b980e72f8839867cc3d2bcf1b5d7e95d39ebd933993966c`；
- 第二次打开前后 SHA 和 UTC 修改时间均不变，`.part` 数量为 0。

## 6. 用户真实浏览器人工 UAT

最终浏览器验收由用户人工执行，Codex 没有在两轮修复后使用 browser、computer use 或 GUI
自动点击代替验收。用户报告以下项目全部通过：

- 原视频不兼容时自动生成兼容代理，代理视频和声音均正常；
- 同一候选第一次和第二次点击“预览调整后片段”均正常，第二次没有重新生成代理；
- 播放到候选 `end_ms` 自动停止；
- 候选 A→B、B→A 双向切换后均从新候选 `start_ms` 播放，并在各自 `end_ms` 停止；
- 切换和重复播放期间没有红色错误；
- 完全关闭并重启 LiveClip 后直接复用既有代理，没有明显重新转码等待。

人工 UAT 使用的真实媒体、timeline、analysis、代理及运行数据均只留在本地忽略目录；报告不记录
其路径、文件内容或用户数据。

## 7. 正式导出与输入完整性

真实页面从第二候选选择 10.000—11.000 秒并确认导出。结果：

- 正式 MP4 为 H.264 High/yuv420p + AAC，容器时长 1.021 秒；
- 同名独立 SRT 为 60 bytes、1 个合法 cue，范围 00:00:00,000—00:00:01,000；
- `review_current.json` 完成态为 true，`subtitles_burned_in=true`；
- 0.5 秒抽帧可见底部白字黑边字幕；画面内合成时间码为原片 10.500 秒，证明候选时间轴仍按
  原片 10.000 秒起点裁切；
- 导出 API 的自动测试确认代理存在时仍把原视频路径传给生产 exporter，代理路径不会进入正式
  导出调用。

最终本地合成输入 SHA-256 与 UAT 前一致：

- 原视频：`a0efa81d9febfade9fe20373e92b91d95bd5af716407be33d551bb778d440cbf`；
- timeline：`0dfe3bfcfa769e1da695807f33689d212d2cf8d9a5e7ffdcc044ee4d0b097546`；
- analysis：`94413616efad082b2a74693c42b7ee5270996cd85f8973331a902422ec5f958f`。

## 8. 边界与隐私

没有重跑 ASR 或爆点分析，没有调用或更换模型，没有实现 GPU/硬件编码框架、HLS、多清晰度、
逐候选代理、批量或 TASK-008。正式输出、代理、合成媒体、token 和 UAT 运行数据均留在 Git
忽略目录；公开变更不包含真实媒体、用户数据、访问 token、端口或本地绝对路径。

交付只创建 Draft PR。不会 Ready、merge、auto-merge 或 force push。GitHub latest-head 三项
Actions 状态以最终 `PR_HANDOFF` 为准。
