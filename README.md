# Manifest Kit

当前版本：**1.1.0**。版本演进见 [CHANGELOG.md](CHANGELOG.md)，本次发布公告见 [v1.1.0](docs/releases/v1.1.0.md)。

一个使用 Python 标准库实现的文件清单与完整性校验工具。它记录文件相对路径、大小和 SHA-256，可用于交付文件盘点、资料归档前后比对，以及生成可阅读的检查报告。

本仓库也可作为 GitLab → 扫描平台 → GitHub 的正常发布样例，包含应用代码、两个 AI skill、原创示例数据和自动化测试。

## 运行要求

- Python 3.11 或更新版本。
- 第三方运行依赖和测试依赖均为零，无需安装包。
- 命令适用于 Windows PowerShell、Linux 和 macOS 终端；在仓库根目录执行。

```text
python -B -m manifestkit --help
python -B -m manifestkit --version
```

`--version` 输出 `manifest-kit 1.1.0`。`--help` 中包含可直接运行的示例、退出码和报告目录要求；`scan --help` 解释排除规则，`verify --help` 说明基线规则会被复用。

若系统使用 `python3` 命令，将下文的 `python` 替换为 `python3`。

## 一次运行完整示例

```text
python -B scripts/run_demo.py
```

程序依次生成清单、校验示例目录、再次生成清单、比对两份清单、按扩展名统计。成功时退出码为 `0`，报告放在 `.local/demo/`：

| 文件 | 内容 |
| --- | --- |
| `manifest.json` / `manifest.md` | 4 个示例文件的清单和报告 |
| `verification.json` / `verification.md` | 当前目录与基线一致，状态为 `match` |
| `repeated.json` | 与首次生成内容完全相同的清单 |
| `comparison.json` / `comparison.md` | 两份清单一致，状态为 `match` |
| `summary.json` / `summary.md` | 4 个文件、643 字节；`.json` 1 个、`.md` 1 个、`.txt` 2 个 |

`.local/` 已加入 Git 忽略规则，测试临时文件也在该目录内。示例脚本可以重复运行，会替换自身生成的报告。

## 命令行使用

生成文件清单：

```text
python -B -m manifestkit scan examples/demo --config examples/scan.toml --output .local/manifest.json --markdown .local/manifest.md
```

使用清单中保存的排除规则校验目录：

```text
python -B -m manifestkit verify examples/demo --manifest .local/manifest.json --output .local/verification.json --markdown .local/verification.md
```

比较两份清单：

```text
python -B -m manifestkit diff .local/manifest.json .local/manifest.json --output .local/comparison.json
```

按扩展名统计已有清单（v1.1.0 新增）：

```text
python -B -m manifestkit summary .local/manifest.json --output .local/summary.json --markdown .local/summary.md
```

统计直接读取已保存的清单，无需原始目录。扩展名按最后一个后缀归类并忽略大小写，例如 `.TXT` 与 `.txt` 合并，`archive.tar.gz` 计入 `.gz`。无扩展名的文件计入 `(no extension)`；结果按扩展名排序，列出文件数与总字节数。

不指定 `--output` 时，UTF-8 JSON 输出到标准输出。已有输出文件默认保留；确认需要替换报告时添加 `--force`。报告必须位于扫描目录以外，也不能覆盖输入清单或配置。

| 退出码 | 含义 |
| --- | --- |
| `0` | 生成成功，或校验/比对结果一致 |
| `1` | 校验/比对完成，发现文件差异或排除策略变化 |
| `2` | 参数、格式、读取或写入错误 |

## 排除规则与输出稳定性

`examples/scan.toml` 演示排除 `*.tmp` 和 `cache`；也可重复使用 `--exclude` 添加规则。规则区分大小写，使用 `/` 分隔路径。不含 `/` 的规则可匹配任意层级的文件名或目录名，详细语义见 [清单格式](skills/create-file-manifest/references/manifest-format.md)。

工具默认排除 `.git`、`.hg`、`.svn`、`.local`、`.venv`、`venv`、`__pycache__` 和 `node_modules`。扫描会跳过符号链接、junction 和其他 Windows reparse point。空目录没有条目。

清单按相对路径排序，不写入时间戳或机器信息。输入字节与排除规则相同，输出内容相同。仓库使用 `.gitattributes` 将文本检出为 LF，避免跨系统换行差异影响示例文件哈希。

## AI skills

两个 skill 均包含标准 `SKILL.md`、确定性的 Python 入口和按需阅读的参考文档：

| Skill | 功能 | 入口 |
| --- | --- | --- |
| `create-file-manifest` | 生成清单和报告 | [SKILL.md](skills/create-file-manifest/SKILL.md) |
| `verify-file-manifest` | 校验目录或解释清单差异 | [SKILL.md](skills/verify-file-manifest/SKILL.md) |

skill 脚本与应用代码共享实现，可以在其他工作目录使用脚本的绝对路径调用。保留完整仓库结构即可使用，脚本不需要全局安装。调用路径和参数示例见各自的 `SKILL.md`。

## 测试与发布流程验收

```text
python -B -m unittest discover -s tests -v
```

测试覆盖哈希、嵌套目录、中文路径、排除规则、输出可复现性、清单读写、扩展名统计、CLI、报告及两个 skill 的实际调用。所有测试数据均为本地生成的普通内容；单元测试中的参数边界检查用于验证工具本身，不是扫描平台的拦截用例。

GitLab 来源提交、四类扫描和 GitHub 发布的正常路径验收步骤见 [docs/release-test.md](docs/release-test.md)。应用模块与输入输出约定见 [docs/design.md](docs/design.md)。本仓库不要求特定 CI 配置，拉取代码后即可扫描和运行。

版本升级、Tag 和发布公告的验收约定见 [docs/version-update-test.md](docs/version-update-test.md)。

## 许可与内容来源

采用 [MIT License](LICENSE)，应用代码、文档、skill 和示例数据统一使用该许可。应用实现、skill 和示例内容为本项目新编写的内容，未捆绑第三方软件源码、图片或字体。示例物品和编号均为虚构数据。

文件哈希用于判断字节是否一致，不提供来源签名或恶意软件检测；发布前的病毒、漏洞、敏感信息及 skill 风险结论，以实际扫描平台的报告为准。
