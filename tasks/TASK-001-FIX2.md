# TASK-001-FIX2 执行记录

## 任务目标

只修复 TASK-001-FIX-R 指出的两个 FFmpeg 来源链阻断问题：冻结生产安装来源并隔离测试注入；区分历史安装时发布方哈希验证与本次运行实际检查。同步修正安装摘要、专项测试和文档，不执行 TASK-002。

## 开始状态

- 已完整读取用户提供的 TASK-001-FIX2 指令及其指定的全部项目文件。
- 初始 Git 状态：仓库无提交，既有项目文件均未跟踪。
- 已记录关键文件 SHA-256、现有安装标记、项目内 FFmpeg 版本和进程/用户/机器 PATH 状态。
- TASK-001-FIX-R 结论为不通过；混合编码和音画同步已独立复核通过，仅剩两个来源链阻断问题。
- `docs/CURRENT_STATUS.md` 已先标记 TASK-001-FIX2 进行中；不得进入 TASK-002。

## 边界

- 不重新下载或重新安装 FFmpeg；不修改现有 FFmpeg 二进制。
- 不修改混合编码、音画同步、媒体裁切、SRT 或字幕烧录实现。
- 不安装或下载 ASR 模型、大型 AI 依赖；不调用收费 API。
- 不操作用户真实直播视频；不修改系统 PATH 或永久环境变量。
- 完成后只建议 TASK-001-FIX2-R 独立只读复核，不自动继续下一任务。

## 完成状态

TASK-001-FIX2 实现和本地测试于 2026-07-19 完成，仍待 TASK-001-FIX2-R 独立只读复核；复核前不得写 TASK-001 最终验收通过。

## 已完成

- [x] 生产 gyan.dev 8.1.2 full build 的提供方、页面、归档名、下载 URL、校验 URL 和固定 SHA-256 改为不可由命令行覆盖的受审计常量。
- [x] 离线注入隔离到显式 `-TestMode`，仅允许带哨兵的隔离根内本地资源，拒绝远程 URL、隔离根外路径和真实安装目标。
- [x] 生产与测试摘要分别如实标记 `gyan.dev` / `test_fixture`，测试模式不能写入真实安装标记。
- [x] 用五个新字段分离历史安装验证、本次发布方读取、本次匹配、本次归档重算和本次归档下载。
- [x] 同版本分支采用完全离线安全跳过；旧标记兼容读取但不迁移、不覆盖、不伪造缺失的发布方哈希。
- [x] 来源链专项 21 passed、0 failed、0 skipped；完整回归 133 passed、0 failed、0 skipped；`pip check` 通过。
- [x] 强制媒体验证、17 项同步单元测试和 1 项关键合成媒体集成测试通过；未修改媒体实现与容差。
- [x] 已更新状态、决策、媒体报告和完整结果报告。

## 同版本实测摘要

- `status=already_installed`
- `publisher_hash_verified_at_install=true`
- `publisher_hash_checked_this_run=false`
- `publisher_hash_match_this_run=null`
- `archive_hash_recomputed_this_run=false`
- `archive_downloaded_this_run=false`

实测前后现有安装标记和 `ffmpeg.exe` SHA-256 均不变，未下载归档、未重装 FFmpeg、未修改 PATH。

## 下一步

只建议 TASK-001-FIX2-R 独立只读复核；停止，不执行 TASK-002。
