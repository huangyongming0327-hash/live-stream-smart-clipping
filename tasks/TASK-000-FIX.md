# TASK-000-FIX 执行记录

## 目标

修复 TASK-000 独立审核发现的 Schema 与项目基础规则问题，不进入媒体、界面、ASR、分析或导出业务开发。

## 修复前状态记录

- TASK-000 独立审核未通过；
- 存在会阻断可靠 JSON 契约的 Schema 问题；
- 本记录对应的进行中任务仅为 TASK-000-FIX。

## 边界核验

- [x] 只执行 TASK-000-FIX，未执行 TASK-001。
- [x] 未安装 FFmpeg，未下载大型模型。
- [x] 未调用网络或收费 API。
- [x] 未删除原始视频、用户文件或无关项目文件。
- [x] 未安装 PyTorch、FunASR、SenseVoice、Whisper 或 PySide6。

## 完成项

- [x] 所有时间、时长、置信度、评分和风险扣分拒绝非有限值。
- [x] 三个顶层 `schema_version` 冻结为字符串 `"1.0"`。
- [x] 启用严格类型并继续拒绝未知字段。
- [x] 风险、内容类型、字幕可靠性、分析状态和审核状态冻结为稳定内部值。
- [x] `updated_at` 强制带时区并规范为 UTC。
- [x] 移除全局字符串裁剪，文本 JSON 往返保持原样。
- [x] 补齐 ID 唯一、topic 引用、范围嵌套、视频边界和评分等级校验。
- [x] 明确 segment 最多允许 `0.05` 秒边界重叠。
- [x] 新增实际中文/空格路径上的三个 JSON 文件往返测试。
- [x] 新增 `requirements-dev.lock.txt` 与 `tools/Run-Tests.ps1`。
- [x] 加强 `.gitignore` 的媒体工具、模型、密钥和缓存兜底。
- [x] 同步更新数据契约、决策、环境报告和当前状态。

## 本地验证

- 完整 pytest：65 passed，0 failed，0 skipped。
- `pip check`：`No broken requirements found.`
- 安全探针：未发现疑似密钥、项目网络调用代码、FFmpeg 二进制或禁用的大型依赖。

## 验收状态

TASK-000-FIX 的实现和本地验证已完成；独立只读复核仍待进行。在复核通过前，不将 TASK-000 标记为最终验收通过。

## 回滚原则

本次没有创建提交。回滚前先保存用户后续改动，然后仅还原本记录所列修改文件并删除本任务新增的四个文件：`requirements-dev.lock.txt`、`tools/Run-Tests.ps1`、`tests/test_schema_regressions.py` 和本执行记录。不要删除整个项目目录、原视频、`runtime` 用户数据或其他无关文件。
