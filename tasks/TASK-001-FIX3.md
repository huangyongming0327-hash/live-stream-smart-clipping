# TASK-001-FIX3 执行记录

## 任务目标

只完成三个窄范围目标：拒绝 UNC、远程 `file:` URI 和非本地固定磁盘测试路径；拒绝 junction/symlink 等重解析点逃逸；补齐“哈希匹配但归档损坏”的真实解压失败不发布测试。不得修改生产来源、媒体、混合编码、音画同步或 100/150/150 ms 容差，不执行 TASK-002。

## 开始状态与基线

- 已完整读取用户 TASK-001-FIX3 指令、`AGENTS.md`、状态/决策/媒体报告、FIX2 任务/结果/FIX2-R 审核、安装脚本、来源链测试和相关测试运行代码。
- 初始 Git：`No commits yet on master`，既有项目文件均未跟踪，无 remote。
- TASK-001-FIX2-R 结论不通过；FIX2 原两个来源语义问题已确认修复，仅剩本任务三个目标。
- 开始 SHA-256：`Install-FFmpeg.ps1=ec087b...02bde`，`test_ffmpeg_install_source.py=e92565...7728f`。
- 真实安装基线：标记 `7d624c...2353`；ffmpeg `ad8f21...942e`；ffprobe `9df3b0...5015`。
- Machine/User/Process PATH SHA-256 分别为 `015ee9...0b8`、`3dd925...e98`、`e59a49...bd23`，均不含项目 FFmpeg。
- `docs/CURRENT_STATUS.md` 已先记录 FIX3 进行中和不得进入 TASK-002。

## 实现

- 测试路径接受规则改为本地固定磁盘白名单；本地 `file:` URI只有 Host 为空时可转换后继续验证。
- UNC、远程 `file:` URI、网络/非固定/未知类型卷、设备路径和命名管道路径在任何资源访问前拒绝。
- 从卷根到目标的全部已存在路径组件检查 `FileAttributes.ReparsePoint`；隔离根、ProjectRoot、资源、目标、标记、partial、临时归档、解压和发布路径均纳入。
- 在目录创建、资源读取/复制、归档移动、解压前后和发布前后重复验证；解压树也拒绝重解析点。
- 清理函数在测试模式递归删除前再次拒绝重解析点，避免把不可信重解析目录当作普通目录递归清理。

## 自动化测试

- UNC：隔离根、归档和校验文本均无网络访问地拒绝。
- 远程 URI：`file://server/...` 与 `file://localhost/...` 均拒绝。
- 其他路径：设备、命名管道和固定磁盘判定语义覆盖。
- 重解析点：隔离根 junction、ProjectRoot junction、资源 junction、真实目标 junction、临时目录 junction、归档 symlink 和校验文本 symlink 均真实创建并拒绝；没有跳过。
- 正常 D 盘本地路径及 Host 为空的本地 `file:` URI继续通过。
- 损坏归档：非空无效 7z 的校验文本、固定预期值和实际 SHA-256 完全一致，真实进入 `tar.exe` 解压失败分支并验证不发布与清理。

## 最终结果

- 来源链专项：36 passed、0 failed、0 skipped；pytest 24.28 秒；`pip check` 通过。
- 完整回归：148 passed、0 failed、0 skipped；pytest 26.31 秒；`pip check` 通过。
- `Validate-Media.ps1`：退出 0；`TRIM_VALID=True`、`BURN_VALID=True`；17 项同步单元测试和 1 项关键集成测试通过。
- 真实安装标记、ffmpeg.exe、ffprobe.exe 以及 Machine/User/Process PATH SHA-256 前后完全一致。
- 未下载或重新安装 FFmpeg，未访问 UNC/网络共享，未安装 ASR/大型 AI 依赖，未调用收费 API，未操作真实视频，未修改媒体/编码/同步实现，未执行 TASK-002。

## 下一步

只建议 TASK-001-FIX3-R 最终定向只读复核；复核前不得宣称 TASK-001 最终验收通过，不得进入 TASK-002。
