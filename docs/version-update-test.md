# 版本更新验收约定

## 输入与基线

版本更新继续使用同一个 GitLab 源仓库和同一个 GitHub 目标仓库。原始交付的程序版本为 0.1.0；保留其提交历史，不补设 1.0.0。

每个后续版本独立提交、创建附注 Tag、更新 `CHANGELOG.md`，并在 `docs/releases/` 中保留各自公告。GitLab Release 应关联相应 Tag，公告正文来自同名 Markdown 文件。

本次依次制作 `v1.0.1` 和 `v1.1.0`，只将最终 `v1.1.0` 交给自动化平台。`v1.0.1` 用来检查中间版本历史、Tag 和公告是否也能被保留或导入，无需单独执行一次平台发布。

| 版本 | 程序版本输出 | 可观察变化 |
| --- | --- | --- |
| v1.0.1 | `manifest-kit 1.0.1` | 完善 CLI 帮助和版本说明，无 `summary` 命令 |
| v1.1.0 | `manifest-kit 1.1.0` | 新增 `summary` 命令，支持统计 JSON 和 Markdown |

## 更新前留存

记录已发布 GitHub 仓库的地址、仓库 ID、默认分支提交、已有 Tag 的目标提交，以及已有 Release 的标题、正文和附件列表。这样可以在更新后区分历史保留、版本导入和公告同步三种能力。

## 更新后检查

| 检查对象 | 预期 |
| --- | --- |
| 仓库 | 更新到原来的目标仓库，仓库 ID 保持不变 |
| 提交历史 | 新版本位于旧版本之后，原有提交仍在目标分支历史中 |
| Tag | 旧标签不被移动或删除，新标签对应正确的源版本 |
| 变更说明 | `CHANGELOG.md` 同时保留旧版本和新版本条目 |
| Release | 旧公告不被新公告替换；如平台承诺迁移历史公告，源端历史公告也应出现 |
| 可运行性 | 在相应 Tag 下运行 `--version`、自动化测试及完整示例，得到对应版本的结果 |

只显示最新版本或只保留一份包含旧文字的 `CHANGELOG.md`，都不能单独证明 Git 历史、Tag 和 Release 已完整保留。

如果目标仓库原本没有 Tag 或 Release，本次可以检查其导入结果，但不能声称已测试过“目标旧 Tag / Release 在更新后保留”。GitHub Release 公告迁移也应与仅发布最新公告分开记录。

## 从 v1.1.0 发起一次平台测试

1. 留存当前已发布 GitHub 仓库的上述基线信息。
2. 将同一个 GitLab 项目地址交给平台，版本选择 `v1.1.0`；若平台只接收默认分支，使用已指向 v1.1.0 的 `main`。
3. 检查四类扫描和正常发布是否成功。
4. 在原 GitHub 仓库核对提交历史、两个标签、完整 `CHANGELOG.md` 和两份 Release 正文。两份正文分别与 `docs/releases/v1.0.1.md`、`docs/releases/v1.1.0.md` 比较。
5. 单独记录“旧记录保留”“历史版本导入”“最新公告发布”的结果。只有最新公告时，不应把它记为全部历史公告已迁移。

在包含完整 Git 引用的仓库内可使用：

```text
git log --oneline --decorate
git show-ref --tags
git merge-base --is-ancestor v1.0.1 v1.1.0
git diff v1.0.1 v1.1.0 --stat
python -B -m manifestkit --version
python -B scripts/run_demo.py
```

`merge-base --is-ancestor` 应返回 0，说明 v1.0.1 位于 v1.1.0 的历史中；仅能通过旧提交链接访问到代码，不足以证明它仍在默认分支历史中。Tag 对应提交、Release 正文也需要分别核对，不能只看版本号文字。
