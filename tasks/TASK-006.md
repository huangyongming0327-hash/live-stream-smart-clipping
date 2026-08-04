# TASK-006｜端到端一键流程与 Windows 启动器

## 目标

把已经合并的单视频转写、语义分析和候选审核模块串成一个可恢复入口：

```text
选择一个 MP4
→ 本地字幕识别
→ 语义分析与爆点候选
→ 自动打开本地审核页面
→ 人工调整并确认
→ 导出一个 MP4 和对应 SRT
```

## 范围

- 新增 `python -m liveclip run --video ...`，默认 Paraformer、视频旁工作目录及其
  `exports`；允许 SenseVoice、自定义工作/导出目录和不自动打开浏览器；
- ASR 前检查 MP4、FFmpeg/ffprobe、本地模型、三个文本模型环境变量和目录写入；
- 顺序复用现有 transcribe、analyze、review，不复制核心算法；
- 通过视频 SHA、timeline SHA、analysis SHA 和输出存在性判断合法复用；
- 未完成状态交给原模块恢复，损坏或错配产物不删除、不覆盖；
- 原子写入不含绝对路径、密钥或用户文本的 `pipeline_status.json`；
- 新增 `Start-LiveClip.cmd` 和 Windows 原生文件选择/ASR 选择 PowerShell 启动器；
- 候选或范围变化后撤销确认；成功后显示两个文件名、最终范围、时长和输出文件夹名称。

## 验收

- fake 阶段测试覆盖 CLI、默认/自定义目录、两个 ASR 选择、ASR 前失败、阶段调用/复用/恢复、
  SHA 变化、损坏产物、状态重推导、中文空格路径、启动器取消、completed review 和页面提示；
- TASK-003/TASK-004/TASK-005 source-only 回归及 `pip check` 为 0 failed；
- Git 忽略目录中的真实 MP4 完成或恢复三个阶段、自动打开真实审核页、调整后重新确认并
  导出一个可播放 H.264/AAC MP4 和 timeline 派生 SRT；
- 同命令复跑不重复 ASR/文本模型，直接进入已完成审核；
- 原视频、timeline、analysis 不被修改，运行媒体、用户输出和凭据不进入 Git；
- Draft PR 三项 Actions 通过，等待独立审核和用户后续决定。

## 不做

多视频、批量或多片段导出、队列、自动开始下一任务、安装包、自动更新、托盘、Windows
服务、云存储、自动上传/发布、代理、波形、缩略图、新 ASR 模型、新 LLM provider、
TASK-003/TASK-004 非阻断 backlog 和 TASK-007。
