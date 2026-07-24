# TASK-001-FIX 执行记录

## 任务目标

只修复 TASK-001 独立只读复核的三个阻断项：FFmpeg 来源与发布方校验链、Windows UTF-8/GBK 混合输出、音画同步自动验收闭环。未执行 TASK-002，未扩展到 UI、ASR 或爆点分析。

## 开始状态

- 已完整读取用户提供的 TASK-001-FIX 指令和其指定的全部项目文件。
- 初始 Git 状态：仓库无提交，既有项目文件均未跟踪；没有通过 Git 清理、删除、移动或覆盖用户文件。
- `docs/CURRENT_STATUS.md` 在修复开始时先标记：TASK-001 独立复核未通过；阻断项为来源校验、混合编码和音画同步；TASK-001-FIX 进行中。

## 已完成

- [x] 复核 FFmpeg 官方页、官方列出的 Windows 提供方、gyan.dev 下载页、固定 8.1.2 直接 URL 和发布方 `.sha256`。
- [x] 加固 `Install-FFmpeg.ps1`：实际读取发布方 SHA-256，依次比对发布方值、固定值和本地值；partial 下载、临时解压、同卷原子发布、同版本跳过、未知目录保护和 JSON 摘要。
- [x] 新增来源链离线测试：字段、哈希格式、不匹配失败、截断下载不发布、同版本跳过、未知目录不覆盖。
- [x] 子进程输出继续二进制捕获、argv 和 `shell=False`；新增 UTF-8、BOM、CP936 和替换降级的结构化解码元数据。
- [x] 新增编码测试：UTF-8 中文、CP936/GBK 中文、UTF-8 BOM、混合字节、中文路径错误、安全降级和替换标记。
- [x] 新增 ffprobe JSON 同步层，测量首视频帧 PTS、首音频包 PTS、两路流时长和容器时长，拒绝缺失值和非有限数。
- [x] 冻结 MVP 容差：A/V 起始差 100 ms、流时长差 150 ms、目标时长差 150 ms。
- [x] `ExportValidation` 增加任务规定的同步字段、布尔判定和 warnings。
- [x] 关键集成测试实际生成 12 秒合成 H.264/AAC 样本，裁切 2.3—8.7 秒并自动验证输入/输出同步；测试未跳过。
- [x] 发现旧字幕烧录 A/V 起始差 -101.333 ms 后，以 `setpts/asetpts` 和 `-avoid_negative_ts make_zero` 修正；回归后为 -22.000 ms。
- [x] 更新示例配置、状态、技术决策、媒体报告和完整结果报告。

## 关键实测

| 指标 | 输入 | 精准裁切输出 |
|---|---:|---:|
| 首视频帧 PTS | 0.000000 s | 0.080000 s |
| 首音频包 PTS | -0.021333 s | 0.018000 s |
| A/V 起始差（音频－视频） | -21.333 ms | -62.000 ms |
| 视频流时长 | 12.000000 s | 6.360000 s |
| 音频流时长 | 12.000000 s | 6.421333 s |
| 流时长差（音频－视频） | 0.000 ms | +61.333 ms |
| 容器时长 | 12.000000 s | 6.422000 s |
| 目标时长差 | 0.000 ms | +22.000 ms |
| 判断 | 通过 | 通过 |

裁切输出的 80 ms 视频首帧、18 ms 音频首包和 -62 ms A/V 差已如实披露；没有写成 0，也没有放宽 100 ms 容差。

## 测试结果

- 完整命令：`powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Run-Tests.ps1 -ra --durations=10`
- 结果：117 passed、0 failed、0 skipped；最终 pytest 3.88 秒；`pip check` 通过。
- 媒体命令：`powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Validate-Media.ps1`
- 结果：强制能力、合成媒体端到端验证、17 项同步单元测试和 1 项关键 FFmpeg 集成测试全部通过；关键测试未跳过。

## 安全边界

- [x] 未安装或下载 ASR 模型、Whisper Python 包、FunASR、SenseVoice、PyTorch、PySide6 或大型 AI 依赖。
- [x] 未调用收费 API，未新增业务网络客户端，未写入密钥。
- [x] 未操作用户真实直播视频；只使用 D 盘 runtime 合成媒体。
- [x] 未修改系统或用户 PATH，未永久修改环境变量。
- [x] 未执行 TASK-002，未创建远程仓库或提交。
- [x] 未删除用户文件，未覆盖已有输出；FFmpeg 二进制和 runtime 生成物继续被 Git 忽略。

## 验收状态

TASK-001-FIX 实现和本地测试完成；TASK-001-FIX-R 独立只读复核仍待进行。当前只报告本地验证状态，不自动继续 TASK-002。

## 详细报告

完整 17 项结果见 `tasks/reports/TASK-001-FIX_RESULT.md`。
