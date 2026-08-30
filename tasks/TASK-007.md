# TASK-007｜首次试用修复：字幕烧录与启动器稳健性

## 目标

修复首次真实使用暴露的三个问题：正式 MP4 缺少画面内字幕、多个 `python.exe` 可能被错误
组合、未配置资产根时普通用户缺少可执行提示。保持现有单视频人工审核闭环与本地优先边界。

## 范围

- 人工确认后的正式 MP4 默认烧录最终裁剪范围对应的现有 SRT，同时生成同名独立 SRT；
- 字幕固定为微软雅黑优先、白字、黑色描边、底部居中、安全边距和按视频高度三档字号；
- 使用 FFmpeg H.264/AAC 单次导出，ffprobe 与输入 SHA 校验成功后才无覆盖发布；
- `review_current.json` 增加严格布尔 `subtitles_burned_in`，完成页明确显示视频/独立字幕状态；
- Windows 启动器只选择一个真实 Python，排除 WindowsApps，并在资产根缺失时给出可复制的
  `LIVECLIP_ASSETS_ROOT` 用户级设置示例。

## 验收

- fake 测试覆盖三档样式、特殊路径转义、空/非空字幕、失败回滚、ffprobe、无覆盖、输入 SHA、
  review 字段/复用、页面提示和 Windows 启动器解析；
- 同时存在真实 Python 与 WindowsApps 路径 Python 时只选择真实 Python并成功启动 CLI；
- 复用既有真实视频、timeline 和 analysis，不调用 ASR 或文本模型，导出真实烧录 MP4 与 SRT；
- 开头、中间、结尾字幕可见且基本同步，不明显遮挡主体；ffprobe 为 H.264/AAC 且时长合理；
- 原视频、timeline、analysis SHA 不变；真实媒体和输出被 Git 忽略；source-only 0 failed；
- Draft PR 三项 GitHub Actions 通过后生成 PR handoff，仍由用户决定是否进入独立审核。

## 不做

不提供字体、颜色、位置、动画或字幕编辑器；不翻译、纠错或改写；不重新调用 ASR/文本模型；
不下载或移动模型；不硬编码本机路径；不修改 TASK-003/TASK-004 核心逻辑；不做批量、多片段
拼接、竖屏转换或自动发布；不执行 TASK-008；不 Ready、不 merge、不 auto-merge、不 force push。
