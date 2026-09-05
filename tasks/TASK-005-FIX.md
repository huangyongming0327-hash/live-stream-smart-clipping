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
- [x] review/proxy 专项自动测试最终复跑：69 passed。
- [x] 真实 Windows FFmpeg 已验证代理首次生成、缓存命中、H.264/yuv420p/AAC、最大尺寸、零起点时间轴、输入哈希不变和无残留 `.part`。
- [x] 用户真实浏览器人工 UAT：自动 fallback、视频与声音、同候选重复预览、end 自动停止、
  A→B 与 B→A 候选切换、无红色错误及完全重启后的代理缓存复用均通过。
- [x] 完整 source-only：268 passed / 1 deselected；91 passed / 2 deselected；`pip check` 通过。
- [x] 正式导出真实验证：原视频输入、烧录字幕、独立 SRT 和输入哈希不变。
- [x] 更新 `docs/CURRENT_STATUS.md` 和 `tasks/reports/TASK-005-FIX_RESULT.md`。
- [ ] 创建指定标题的 Draft PR，等待三项 GitHub Actions 全部 SUCCESS。
- [ ] 运行 `tools/github/Get-PRHandoff.ps1` 并输出完整 `PR_HANDOFF`。

## 完成约束

- PR 保持 Draft；不执行 Ready、merge 或 auto-merge。
- 不执行 TASK-008。
