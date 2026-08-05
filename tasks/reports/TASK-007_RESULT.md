# TASK-007 RESULT｜首次试用修复：字幕烧录与启动器稳健性

## 1. 状态与边界

- 从包含 TASK-006 合并提交的最新 `master` 使用规定脚本创建任务分支；
- 默认字幕烧录、同名独立 SRT、审核状态/页面提示和启动器稳健性修复已完成；
- 没有下载或移动模型，没有修改 TASK-003/TASK-004 核心逻辑，没有执行 TASK-008；
- 真实媒体、用户字幕正文、候选内容和本地绝对路径不进入本报告或 Git；
- GitHub latest-head 三项 Actions 不在提交前预先宣称，最终状态以 PR handoff 为准。

## 2. 正式导出

服务端从最终人工裁剪范围重新生成 timeline 派生 SRT，但不调用 ASR 或文本模型。SRT 先写入
临时文件：非空时 FFmpeg 在同一次精确裁剪、H.264/AAC 重编码中烧录字幕；同时保留同名独立
SRT。合法空字幕范围不会强造文本，仍导出视频和空 SRT，并记录未烧录。

发布前依次验证 FFmpeg 成功、MP4/SRT 非空规则、ffprobe 的 H.264/AAC/双流/时长，以及原视频、
timeline、analysis SHA 未变。正式文件只用无覆盖移动发布，最后才原子写入 review。失败不会留下
伪完成 MP4、SRT 或 review，也不会删除或覆盖用户已有输出。

## 3. 固定字幕样式

- 微软雅黑优先、白色文字、黑色描边、无阴影、底部居中并保留安全边距；
- 视频高度 `<=720`、`721..1440`、`>1440` 分别使用 24、28、32 px 目标字号；
- 目标像素按视频高度换算为 libass 的 SRT 脚本坐标，避免竖屏内容被异常放大；
- 不提供字体、颜色、位置、动画或字幕编辑器，不翻译、纠错或改写字幕。

## 4. 审核完成态与页面

`review_current.json` 新增严格布尔 `subtitles_burned_in`。非空字幕成功烧录后为 true；合法空字幕
为 false；旧的缺字段完成态不会被 runner 静默复用。页面在成功后明确显示“视频字幕：已烧录”
和“独立字幕：已生成”，空字幕片段显示对应的未烧录原因。

## 5. Windows 启动器

Python 选择顺序为仓库 `.venv`、资产根 `.venv`、PATH 中第一个真实 Application。解析器忽略
WindowsApps 路径并只返回一个可执行文件，不再要求关闭 Windows 应用执行别名。资产根未配置且
仓库资产不完整时，提示会列出缺失项并给出可复制的用户级 `LIVECLIP_ASSETS_ROOT` 设置命令；
示例不含任何用户本地硬编码路径。

本机 PATH 包含 WindowsApps，但当前应用执行别名文件不存在；因此另以受控 WindowsApps 路径
可执行文件与真实 Python 同时进入 PATH。生产解析器看到两个 Application，只选择非 WindowsApps
的真实 Python，返回单行路径，并以该解释器成功运行 `liveclip --help`。该结论不冒充本机别名
文件实际存在。

## 6. 自动测试

- 字幕导出、review、runner 与 Windows 启动器定向回归：66 passed、0 failed；
- source-only base-schema-media：224 passed、1 deselected、0 failed；
- source-only asr-experiments：91 passed、2 deselected、1 个既有 deprecation warning、0 failed；
- `pip check`：`No broken requirements found.`；
- 三阶段退出码均为 0，`SOURCE_ONLY_RESULT.status=passed`。

测试覆盖特殊字符路径、三档字号及坐标换算、空/非空 SRT、FFmpeg/ffprobe 失败、无覆盖、输入
哈希变化、review 严格字段与复用、页面文本、仓库/资产根优先级、WindowsApps 排除和资产提示。

## 7. 真实媒体验证

复用 Git 忽略目录中既有 827.766 秒真实 MP4、169-segment timeline 和 completed analysis，未重跑
ASR 或文本模型。通过真实审核页面选择、预览、确认并导出到包含中文、空格、`&` 和括号的输出
目录：

- 正式 MP4 为 28,054,570 bytes；独立 SRT 为 1,260 bytes、14 cues；review completed 且
  `subtitles_burned_in=true`，无 `.part` 残留；
- ffprobe 为 H.264 1080x1920 + AAC，容器时长 51.821016 秒；目标 51.776 秒，相差约 45 ms；
- 在约 1.0 秒、26.5 秒和 49.0 秒抽帧，三处均可见底部居中白字黑边字幕；最长抽查 cue 自然
  换为两行，安全边距存在且未明显遮挡主体；
- 浏览器实际播放输出时音视频加载正常、时间持续前进；三点画面落在现有 SRT 活跃 cue 内，
  沿用 timeline 时间并表现出基本同步。没有以二次 ASR 冒充同步验证；
- 原视频、原/复用 timeline、原/复用 analysis 的 SHA-256 前后一致；正式 MP4/SRT 均被
  `git check-ignore` 命中。

## 8. 隐私、Git 与产品边界

原视频、timeline、analysis 始终只读；真实 review、MP4、SRT、抽帧和验证副本均留在 Git 忽略
目录。公开改动不包含真实路径、标题、字幕正文、访问 token、端口或密钥。LiveClip 不自动上传
或发布视频。

本任务仍只处理单视频、单候选导出；不做批量、多片段拼接、字幕编辑、翻译/纠错/改写、竖屏
转换、队列、安装包或自动发布。Draft PR 保持 Draft，不启用 auto-merge、不 merge、不 force push。

## 9. 下一步

发布 Draft PR 后只验证 latest-head 三项 Actions 并生成完整 PR handoff；是否进入独立审核、何时
Ready 或合并继续由用户决定。本任务不执行 TASK-008。
