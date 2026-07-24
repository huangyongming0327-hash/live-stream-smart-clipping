# TASK-GIT-001｜建立首次本地 Git 基线

## 目标

在 TASK-000 和 TASK-001 已通过验收的前提下，为项目创建第一次本地 Git 提交和带说明标签 `baseline-task-001`，使后续变更可以相对稳定基线审查和恢复。

## 允许范围

- 完整盘点本地仓库、候选文件、忽略内容、PATH 和现有 FFmpeg 安装标记；
- 核验并仅在必要时补强 `.gitignore` 安全规则；
- 运行完整测试、合成媒体验证和 `pip check`；
- 更新 `docs/CURRENT_STATUS.md`；
- 创建本任务记录与结果报告；
- 创建第一次本地提交和本地带说明标签。

## 禁止范围

- 不执行 TASK-002，不修改业务源码或测试逻辑；
- 不下载、安装或联网，不调用收费 API；
- 不创建远程仓库，不执行 `git push`；
- 不修改当前分支名称或全局 Git 配置；
- 不执行 `git reset --hard`、`git clean` 或宽范围删除；
- 不提交 `.venv`、runtime 产物、FFmpeg 二进制、模型、真实媒体、用户数据、缓存或密钥。

## 提交前门禁

1. TASK-001-FIX3-R 审核结论为通过；
2. 完整回归至少 148 passed，且 0 failed、0 skipped；
3. 媒体验证退出 0，`TRIM_VALID=True`、`BURN_VALID=True`；
4. 独立 `pip check` 通过；
5. 非忽略候选中没有大于 5 MiB 的文件、禁止类型或疑似真实凭据；
6. 暂存后清单、统计和 whitespace 检查全部通过；
7. 仓库无既有提交、无远程、目标标签不存在。

## 本地 Git 对象

- 提交信息：`baseline: TASK-000 and TASK-001 verified`
- 标签：`baseline-task-001`
- 标签说明：`Verified local baseline after TASK-000 and TASK-001`

## 结果

完整执行证据和安全核验见 `tasks/reports/TASK-GIT-001_RESULT.md`。本任务完成后停止，不自动进入 TASK-002。
