# TASK-005-FIX：审核页预览兼容性与轻量代理

## 任务目标

修复 TASK-005 真实 UAT 阻断：审核页仍优先播放原视频；浏览器无法播放原视频时，自动在本地生成、校验并缓存一个完整时长的兼容预览代理，审核页切换到代理播放。正式导出始终使用原视频。

## 基线与分支

- 仓库：`huangyongming0327-hash/live-stream-smart-clipping`
- 基线：最新 `master`，包含 PR #10 / TASK-004-FIX
- 分支：`task/TASK-005-FIX-preview-proxy`
- Draft PR 标题：`TASK-005-FIX: add browser-compatible review preview proxy`

## 实现范围

- 原视频继续由 token 保护的 `/media` 提供，页面初次加载不生成代理。
- 视频 `error`、预览按钮播放失败或本地播放启动停滞时，只进入同一个 fallback 流程。
- `POST /api/preview-proxy` 在本地确保代理存在；服务端同一审核 session 只允许一个生成任务。
- `GET /media/preview` 使用现有随机 token，并支持 GET、HEAD、Range、206 和 416。
- 代理位于当前 LiveClip 工作目录的 `.review_preview`，文件名绑定代理版本和原视频 SHA-256。
- 有效缓存必须通过 ffprobe、视频流、H.264、yuv420p、尺寸、宽高比、时长和音频契约校验。
- FFmpeg 使用 CPU `libx264`、Main profile、yuv420p、veryfast、CRF 29、`-threads 2`；最大 1280×720，不放大，保持宽高比；有音频时转 AAC 96 kbps 双声道；MP4 使用 `+faststart`。
- 生成写入唯一 `.part.mp4`，校验通过后原子发布；失败清理本次临时文件且不覆盖有效缓存。
- 代理保持从 0 开始的完整源时间轴，候选 `start_ms/end_ms` 直接用于代理。
- 代理 ready 后，重复预览、暂停后重播和候选切换只复用当前代理；旧候选的延迟媒体事件不能
  覆盖新候选起点或递归触发代理生成。
- `/api/export` 与 `export_review_clip()` 继续只使用 `inputs.video_path` 原视频，保留字幕烧录和独立 SRT。

## 明确不做

- 不重跑或修改 ASR。
- 不重跑或修改爆点分析，不修改 TASK-004-FIX。
- 不修改模型，不下载大模型。
- 不做 GPU/硬件编码系统、HLS、DASH、多清晰度、逐候选代理、批量或 TASK-008。
- 不上传真实媒体、字幕、timeline、analysis、review 或用户数据。

## 验收清单

- [x] 从最新 master 创建指定任务分支。
- [x] 页面默认先使用原视频，正常可播路径不请求代理。
- [x] 原视频失败时自动请求代理，前后端双重去重。
- [x] 代理编码、尺寸、宽高比、有/无音频和时间轴契约已实现。
- [x] 有效缓存复用，损坏缓存重建，`.part` 不作为缓存。
- [x] token、Range、HEAD、路径穿越和安全响应已覆盖。
- [x] 正式导出继续使用原视频的自动测试已覆盖。
- [x] 中文、空格、`&`、括号和单引号路径已纳入自动测试及本地 FFmpeg 验证目录。
- [x] review/proxy 专项自动测试最终复跑：78 passed。
- [x] 真实 Windows FFmpeg 已验证代理首次生成、缓存命中、H.264/yuv420p/AAC、最大尺寸、零起点时间轴、输入哈希不变和无残留 `.part`。
- [x] 用户真实浏览器人工 UAT：自动 fallback、视频与声音、同候选重复预览、end 自动停止、
  A→B 与 B→A 候选切换、无红色错误及完全重启后的代理缓存复用均通过。
- [x] 完整 source-only：277 passed / 1 deselected；91 passed / 2 deselected；`pip check` 通过。
- [x] 正式导出真实验证：原视频输入、烧录字幕、独立 SRT 和输入哈希不变。
- [x] 更新 `docs/CURRENT_STATUS.md` 和 `tasks/reports/TASK-005-FIX_RESULT.md`。
- [x] 继续使用指定标题的 Draft PR #11；FIX2 latest-head 三项 GitHub Actions 待推送后确认。
- [ ] 运行 `tools/github/Get-PRHandoff.ps1` 并输出完整 `PR_HANDOFF`。

## 完成约束

- PR 保持 Draft；不执行 Ready、merge 或 auto-merge。
- 不执行 TASK-008。

## TASK-005-FIX2：独立审核阻断修复

针对 `TASK-005-FIX-R` 提出的 B1、B2、B3，当前分支完成以下收尾：

- B1：把 `analysis_path.parent` 的严格解析结果作为受控根目录；缓存提升为带固定所有权标记的
  `.review_preview/v2` 普通目录。缓存读取、临时输出校验、发布和媒体提供都会用 `lstat` 检查
  目录与文件类型，Windows 额外拒绝 reparse point。未知目录、未知同名文件、junction、文件
  symlink 和异常文件类型均停止且不删除；只有已确认拥有的损坏缓存可以原子重建。服务启动时
  不再因固定路径存在就开放 `/media/preview`，只有本次服务成功验证的代理才能读取。
- B2：每次区间播放使用单调递增的播放请求代次；超时、候选切换、媒体源切换和新预览请求都会
  使旧请求失效并清理区间状态。旧 `play()` 的迟到成功只会在没有新有效播放时暂停，迟到失败
  不覆盖当前状态；当前有效候选仍由 `end_ms` 停止。代理请求继续共享一个 Promise，连续点击和
  A→B→A 不会新增代理 POST 或递归生成。
- B3：ffprobe 模型记录容器及音视频流起点。视频代理归零；音频按相对视频起点裁剪过早部分，或
  为延迟音频补开头静音，再补齐/裁剪到完整视频时长。代理校验现在检查 H.264 Main、视频零起点、
  必要音频零起点、完整时长及不得大于原视频尺寸；缓存版本提升至 v2，旧时间轴契约不再命中。
- 直接相关问题一并关闭：缓存命中前复核视频、timeline、analysis SHA；删除未使用的
  `proxyRequested`；`/media/preview` 拒绝未经当前服务验证的现存文件。转码取消、硬件编码、HLS、
  多清晰度、批量处理、多候选导出和 TASK-008 保留为 backlog。

FIX2 验证：review/proxy 专项 `78 passed`；Windows 路径安全定向 `5 passed`；实际执行生产
`review.js` 的 Node deferred-play 定向 `1 passed`；真实 FFmpeg 时间轴定向 `2 passed`；媒体
解析 `29 passed`；JavaScript 两个文件语法检查通过。完整 source-only 为基础
`277 passed, 1 deselected`、ASR `91 passed, 2 deselected`，`pip check` 通过。直接执行完整 `pytest tests -q`
为 `314 passed, 2 failed`；两项失败仍是既有 FFmpeg 安装器隔离测试中的子 PowerShell
`CommandNotFoundException`，本任务未修改无关安装器。
