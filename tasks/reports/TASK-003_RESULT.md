# TASK-003 RESULT｜MP4 生成本地字幕时间轴

## 1. 任务状态

- 本地实现、fake adapter 单测、两模型真实短视频验证、中断恢复验证、较长视频验证和
  source-only 回归已完成。
- 分支：`task/TASK-003-asr-production-pipeline`。
- 基线：PR #4 合并提交 `cbdf5632cc53e49ee1477797ba46d07f3fd62d74`。
- 等待通过任务发布脚本创建 Draft PR，并核验 latest-head 三项 GitHub Actions。

## 2. 实现范围

只实现单 MP4 的本地分块转写和四个输出。没有 GUI、队列、模型管理器、插件系统、
语义分段、爆点识别、候选审核、视频导出或 TASK-004。

## 3. CLI 命令

```powershell
$env:LIVECLIP_ASSETS_ROOT = "<LOCAL_ASSETS_ROOT>"
python -m liveclip transcribe `
  --input "<VIDEO_PATH>\sample.mp4" `
  --engine paraformer `
  --output "<OUTPUT_PATH>\sample_liveclip"
```

主入口只有 `python -m liveclip transcribe`。未指定输出目录时使用视频旁的
`<video_stem>_liveclip`。

## 4. 默认和低资源模型

- 默认：`paraformer`。
- 手动低资源：`sensevoice`。
- CLI 不自动选择、切换、下载或更新模型。
- 模型加载和每次推理期间 socket 连接被主动阻断；相关环境变量同时设置为离线模式，
  云端和收费 API 未调用。

## 5. 音频提取

复用项目 `FFmpegPaths`、安全 argv 子进程和非覆盖原子发布。每块直接从 MP4 提取
PCM s16le、16 kHz、单声道 WAV 到输出目录的 `.work`，不会一次加载完整长音频，
也不生成代理视频、波形或缩略图。

## 6. 分块策略

- 默认 60 秒；允许 1—600 秒显式参数，供验证或特殊输入使用。
- 单任务顺序执行，不并行加载模型。
- 模型在一次运行内只加载一次，每个 WAV 块识别后立即删除。
- 最长视频限制为 3 小时。

## 7. 恢复机制

- 每块成功后原子更新 `task_state.json`。
- 状态按完成块连续索引保存块时间、文本、耗时和完成时间。
- 源 SHA-256、源大小、时长、引擎、分块长度和本地模型关键文件身份共同形成任务指纹。
- 状态损坏或任一指纹要素变化时拒绝复用，不静默覆盖旧状态。
- 完成态再次运行直接复核并返回，不重复识别或覆盖正式输出。

## 8. timeline schema

`schema_version=1.0`，包含源文件名、毫秒时长、源 SHA-256、ASR 引擎、语言、
完成标记和 segments。segment 使用连续整数 ID，保留 `text_raw`，`text` 只压缩空白；
`speaker=null`，疑问句只按结尾问号轻量标记，不翻译、不伪造置信度。

校验强制要求时间非负、`end_ms > start_ms`、升序、无重叠、不超视频总时长。

## 9. SRT/TXT 输出

- `subtitles.srt`：UTF-8、标准毫秒时间、连续序号、与 timeline 同一批 segments。
- `transcript.txt`：UTF-8、每段一行，格式为
  `[00:00:00.000 - 00:00:02.350] 文本`。
- 全部块成功后先暂存和校验，再发布 SRT/TXT，最后发布 `timeline.json`。

## 10. 错误处理

明确处理不存在或非 MP4、FFmpeg/ffprobe 缺失、无音轨/视频轨、超过 3 小时、
模型文件或运行时缺失、模型加载/分块识别失败、输出不可写、状态损坏/不匹配、
磁盘不足和源文件处理中变化。失败会保留已完成块状态，不发布伪完成 timeline。

## 11. 单元测试

新增 `tests/test_asr_production.py` 共 18 项，使用 fake adapter，不下载或运行模型。
覆盖清单要求的 15 项以及完成态幂等、异常 FFmpeg partial 清理和 socket 阻断。

## 12. source-only 回归

命令：`.\tools\github\Invoke-SourceOnlyTests.ps1`

```text
base-schema-media: 128 passed, 1 deselected, 0 failed
asr-experiments: 91 passed, 2 deselected, 1 existing warning, 0 failed
pip check: No broken requirements found.
SOURCE_ONLY_RESULT.status=passed
```

## 13. Paraformer 本地验证

- 真实 MP4 时长：22.067 秒；3/3 块。
- 结果：12 个合法 timeline segments、12 条可读取 SRT。
- 总耗时：33.586606 秒；块提取与识别合计 2.334609 秒。
- 峰值工作集：6,421,196,800 bytes，约 5.98 GiB。
- 输出：timeline 3,321 bytes、SRT 752 bytes、TXT 714 bytes。
- socket 守卫启用时成功；模型和输入均为既有本地资产。

## 14. SenseVoice 本地验证

- 同一真实 22.067 秒 MP4；3/3 块。
- 结果：6 个合法 timeline segments、6 条可读取 SRT。
- 总耗时：5.527051 秒；块提取与识别合计 2.544111 秒。
- 峰值工作集：380,526,592 bytes，约 362.90 MiB。
- 输出：timeline 2,136 bytes、SRT 536 bytes、TXT 519 bytes。

## 15. 中断恢复验证

- SenseVoice 使用 5 秒块处理同一真实 MP4。
- 在 2/5 块已原子落盘后强制终止精确验证进程，状态保持 `running`，未伪装完成。
- 重跑显示“从分块 3/5 继续”，只识别剩余 3 块。
- 首块记录恢复前后 SHA-256 均为
  `2a453f3bc2ecbef29ffc3f8cd322780d67cd252b0c6111199e04926daac1812a`。
- 最终 5/5 完成、6 个 timeline/SRT 条目；异常终止残留的受控 `.part.wav`
  在成功恢复后已清理。

## 16. 性能和资源记录

| 验证 | 时长 | 块 | 总耗时 | 峰值工作集 | 正式输出合计 |
|---|---:|---:|---:|---:|---:|
| Paraformer 短视频 | 22.067 s | 3 | 33.59 s | 5.98 GiB | 4,787 bytes |
| SenseVoice 短视频 | 22.067 s | 3 | 5.53 s | 362.90 MiB | 3,191 bytes |
| SenseVoice 较长视频 | 827.766 s | 14 | 38.54 s | 408.63 MiB | 95,837 bytes |

较长视频生成 169 个合法 timeline segments 和 169 条可读 SRT；`.work` 成功后不存在。
性能为本机本次近似值，不外推到其他硬件或负载。

## 17. 隐私与 Git 边界

- 真实视频、提取 WAV、timeline、SRT、TXT、task state、模型、环境、日志和
  `local-data/` 均保持 Git 忽略。
- 原 827.766 秒 MP4 验证前后 SHA-256 均为
  `DA2CD4041C7FB59A1DFC08C80B0358C28DBBDC59608A469EB1A0A8AC63694BFF`。
- 未删除或修改原视频；未下载模型，未调用云端或收费 API，未写入密钥。
- 公开文档不含真实本机媒体路径、用户名或私有资产根。

## 18. 修改文件

- 正式实现：`src/liveclip/__main__.py`、`cli.py`、`asr/`、媒体音频分块函数。
- 复用改造：TASK-002 Paraformer、SenseVoice 和离线守卫改为调用正式 adapter。
- 测试：`tests/test_asr_production.py`。
- 安全：`.gitignore` 增加 ASR 正式输出规则。
- 文档：README、CURRENT_STATUS、DECISIONS、TASK 和本 RESULT。

## 19. 已知限制

- Paraformer 首次模型加载和约 6 GiB 峰值内存明显高于 SenseVoice。
- 分块边界不会做语义拼接；本任务只保证时间合法、无重叠和原话保留。
- 状态恢复粒度为完整块，不支持任意毫秒暂停。
- 跨多个正式文件的发布不是通用文件系统事务，但本次创建的部分输出会在失败时清理，
  且绝不覆盖预先存在的正式输出。

## 20. 未实现范围

GUI、批量视频、多任务、队列、托盘、Windows 服务、模型管理/下载/更新/自动选择、
复杂 GPU/CPU 调度、说话人分离、翻译、语义分段、爆点识别、候选审核、
复杂字幕样式、视频剪辑导出、云同步和 TASK-004。

## 21. 下一步

下一步只建议对 Draft PR 最新 head 执行独立审核，重点复核恢复指纹、异常终止、
时间轴边界、真实两模型离线证据、正式输出发布和隐私扫描。继续禁止 TASK-004。

## 22. 回滚方法

PR 合并前关闭 Draft PR 并删除精确任务分支；合并后通过新的回滚 PR 执行
`git revert`，不重写公开历史。真实媒体和模型不属于 Git 回滚范围，任何本地清理
都必须由用户另行明确授权，绝不删除原视频。
