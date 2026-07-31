# TASK-005｜候选审核与单片段导出

## 目标

实现一个本地优先的最小人工审核与导出闭环：

```text
原视频 + timeline.json + current_analysis.json
→ localhost 候选审核页面
→ 视频预览与入出点调整
→ 明确人工确认
→ 一个 H.264 + AAC MP4 与独立 SRT
→ review_current.json
```

## 范围

- 单视频、单 timeline、单 analysis、单次审核；
- 左侧待审核候选列表，右侧浏览器原生视频预览；
- 原生滑块、数字输入、±1 秒与 ±0.1 秒微调，毫秒级保存；
- 调整后范围必须位于视频内且为 1—180 秒；
- 明确勾选人工预览确认后才允许一次导出；
- 项目本地 FFmpeg 精确重编码为 H.264 + AAC；
- 从 timeline 裁剪、平移并连续编号一个 UTF-8 SRT；
- 临时文件、ffprobe 校验、无覆盖发布和成功后 review 原子替换；
- 服务仅绑定 `127.0.0.1`，页面、媒体和 API 使用运行时随机 token；
- 页面关闭或 `Ctrl+C` 后停止临时服务，电池供电不暂停。

## 验收

- fake FFmpeg/ffprobe 自动测试覆盖输入、确认、范围、失败、发布和原文件保护；
- localhost、token、路径穿越和浏览器 Range 请求测试通过；
- 真实浏览器显示候选、预览原视频并完成一次手动入出点调整；
- 导出并播放一个真实 MP4，验证 H.264/AAC、时长和非空文件；
- 验证真实 SRT 从 0 开始、单调、与 timeline 裁剪结果完全一致；
- 原视频、timeline 和 analysis 前后 SHA-256 一致；
- 完整 source-only、`pip check` 与 Draft PR 三项 Actions 通过；
- 真实媒体、timeline、analysis、review、导出和运行状态不进入 Git。

## 不做

多候选批量导出、多片段拼接、队列、代理、波形、缩略图、帧级编辑、字幕样式或烧录、
竖屏转换、封面、发布文案、自动上传、安装包、TASK-003/TASK-004 非阻断 backlog 和
TASK-006。
