# TASK-001 执行记录

## 目标

以 Windows 项目内便携方式安装可信 FFmpeg，建立安全媒体调用层，并用小型合成媒体验证探测、WAV、精准裁切、SRT、中文字幕烧录和导出校验。

## 开始状态

- 已完整读取 TASK-001 指令和其要求的全部项目文件。
- 初始 Git 状态：仓库无提交，已有项目文件均未跟踪；没有删除、移动或覆盖用户文件。
- TASK-000 / TASK-000-FIX 已通过独立只读复核；`docs/CURRENT_STATUS.md` 先标记 TASK-001 开始，没有提前写完成。

## 完成项

- [x] 从 FFmpeg 官方下载页列出的 gyan.dev 下载一次稳定 Windows 64 位 release full 8.1.2 构建。
- [x] 将本地 SHA-256 与发布方公开值比对，一致。
- [x] 便携安装到 `tools/ffmpeg/bin`，不使用安装器、不修改或依赖 PATH。
- [x] 验证 ffmpeg、ffprobe、H.264、AAC、SRT、WAV、libass、subtitles、ass 和 libx264。
- [x] 检测 AMF 列表并执行非阻断合成探针；构建包含编码器，但实际初始化失败并如实记录。
- [x] 实现安全 argv 子进程层、超时、退出码、混合编码输出和结构化错误。
- [x] 实现 ffprobe JSON 探测、16 kHz 单声道 PCM WAV、非整数精准裁切、SRT 重计时、字幕烧录和导出校验。
- [x] 在中文与空格路径生成并处理 12 秒合成 MP4 和 UTF-8 中文 SRT。
- [x] 实现同名保护、临时文件清理和非覆盖原子发布。
- [x] 创建 `Install-FFmpeg.ps1`、`Validate-Media.ps1` 并增强 `Run-Tests.ps1`。
- [x] 更新配置、架构、决策、状态和媒体报告。
- [x] 完整 pytest 90 项通过、0 失败、0 跳过；`pip check` 通过。

## 关键实测

- 合成源：12.000 秒，H.264/AAC，640×360，25 fps，1 个视频轨和 1 个音频轨。
- WAV：PCM s16le，16,000 Hz，单声道，12.010688 秒。
- 裁切：2.3—8.7 秒，目标 6.4 秒，实际 6.422 秒，误差 0.022 秒。
- SRT：3 条均按片段边界裁剪并重置为 0.000—0.700、1.200—5.200、5.700—6.400 秒。
- 烧录成片：6.440 秒，H.264/AAC，音视频轨保留，ffprobe 与结构化导出校验通过。

## 边界核验

- [x] 未操作真实直播视频或用户字幕。
- [x] 未安装 FunASR、SenseVoice、Whisper Python 包、PyTorch、PySide6 或 ASR 模型。
- [x] 未调用收费 API，未写入密钥，未上传媒体。
- [x] 除一次 FFmpeg 构建外未执行其他下载。
- [x] 未修改系统或用户 PATH、未永久修改环境变量。
- [x] 未开发 UI、ASR、爆点分析或审核导出界面。
- [x] 未执行 TASK-002、未创建远程仓库或提交。

说明：提供方 full 静态 FFmpeg 的构建配置自带 `--enable-whisper` 组件，但没有下载模型、没有执行该功能，也没有新增任何 Python/AI 依赖。

## 验收状态

TASK-001 实现和本地测试完成；仍待 TASK-001-R 独立只读复核。在复核前不得写最终验收通过，也不直接进入 TASK-002。

## 回滚原则

本仓库仍无提交。回滚前先核对没有用户在本任务文件或 `runtime` 验证目录中加入数据，再仅删除 TASK-001 新增的媒体模块、两个媒体测试、三个新工具脚本/安装目录和本任务合成产物/日志，并手工还原本任务修改的 `README.md`、`config.example.json`、`Run-Tests.ps1`、`ARCHITECTURE.md`、`DECISIONS.md`、`CURRENT_STATUS.md` 与媒体 `__init__.py`。不要删除整个项目、原视频、用户项目或其他任务文件。
