# AutoDocUpdater

将 macOS 备忘录中的技术文章导出为 Markdown，使用 LLM 优化排版和结构，并发布到 51CTO 博客的本地自动化工作流。

> AutoDocUpdater is a local workflow for exporting notes, optimizing Markdown, and publishing articles to 51CTO. The primary documentation is in Chinese.

## 功能

- 从 macOS 备忘录按标签或文章名称导出 Markdown/PDF
- 通过多阶段 LLM 优化 Markdown：前言、目录、章节、总结和代码格式
- 使用 Selenium 将 Markdown 批量发布到 51CTO
- 支持在完整发布流程的步骤1之前实时读取个人分类、由用户选择，并为整批文章使用同一个分类
- 支持自动创建用户指定但当前不存在的个人分类
- 支持登录状态持久化、提交前失败即时重试和失败文件重传清单
- 所有步骤均提供 JSON 日志和结构化执行结果

## 流程

```text
51CTO 登录与个人分类预检 → 备忘录 → 导出 Markdown → LLM 优化 → 51CTO 发布
```

项目包含三个独立 skill：

- `exporting-doc`：从 macOS 备忘录导出文章
- `optimizing-markdown`：调用 LLM 优化 Markdown
- `uploading-2-51cto`：通过 Chrome + Selenium 发布文章

更完整的流程图见 [`docs/README.md`](docs/README.md)。

## 环境要求

- macOS（备忘录导出依赖 AppleScript；上传脚本主要面向 macOS/Windows）
- Python 3.11+
- Google Chrome
- 可用的 LLM Provider，或本地 LiteLLM 代理
- 一个已登录的 51CTO 博客账号

## 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

使用 OpenAI、Azure OpenAI 或 Google Vertex AI 时，再安装可选依赖：

```bash
python3 -m pip install -r requirements-optional.txt
```

使用 SOCKS 代理时，`requirements-optional.txt` 中的 `httpx[socks]` 也需要安装。

## 配置

### LLM 配置

非敏感的模型参数位于：

```text
.agents/skills/optimizing-markdown/conf/config.yaml
```

密钥通过环境变量提供，不要写入配置文件：

```text
AUTODOC_LLM_PROVIDER
AUTODOC_LLM_MODEL
AUTODOC_LLM_API_BASE
AUTODOC_LLM_API_KEY
```

交互式配置：

```bash
python3 .agents/skills/optimizing-markdown/scripts/configure_env.py
```

脚本会隐藏输入密钥，写入 `~/.config/autodoc/env`（权限 `0600`），并按需在 Shell 配置中加入加载区块。执行前可检查配置：

```bash
python3 .agents/skills/optimizing-markdown/scripts/check_env.py
```

### 51CTO 登录

上传脚本使用独立的 Chrome 用户数据目录保存登录状态。首次运行或会话失效时，请在浏览器窗口中完成 51CTO 登录。登录态目录位于仓库外，不应复制到仓库或公开分享。

## 使用

### 0. 发布前预检（必须先于导出）

在导出文章之前，先检查 51CTO 登录状态并读取实时个人分类：

```bash
python3 .agents/skills/uploading-2-51cto/scripts/51cto_uploader.py --list-personal-categories
```

如果提示需要登录，请在打开的 Selenium Chrome 中完成登录。登录成功并显示分类列表后，必须由用户明确选择本批次使用的个人分类（已有分类、新分类名称或不设置）；用户确认后才能进入导出步骤。后续步骤不得再次询问分类。

### 1. 从备忘录导出

```bash
# 按标签导出
python3 .agents/skills/exporting-doc/scripts/doc_exporter.py -t "51upload"

# 导出到指定目录
python3 .agents/skills/exporting-doc/scripts/doc_exporter.py -t "51upload" -d tmp/articles

# 按文章名称导出
python3 .agents/skills/exporting-doc/scripts/doc_exporter.py -n "文章标题"

# 导出 PDF
python3 .agents/skills/exporting-doc/scripts/doc_exporter.py -n "文章标题" -f pdf
```

在 Codex 沙箱环境中，导出必须在沙箱外执行，否则 AppleScript 可能因 `hiservices-xpcservice` 隔离而失败。具体约束见 [`AGENTS.md`](AGENTS.md)。

### 2. 优化 Markdown

```bash
python3 .agents/skills/optimizing-markdown/scripts/markdown_gardener.py path/to/article.md
```

默认日志：`logs/markdown_gardener.log`。建议先使用 `check_env.py` 确认 LLM 配置完整。

### 3. 发布到 51CTO

```bash
# 上传单个文件
python3 .agents/skills/uploading-2-51cto/scripts/51cto_uploader.py path/to/article.md

# 上传整个目录
python3 .agents/skills/uploading-2-51cto/scripts/51cto_uploader.py tmp/articles

# 使用预检阶段已确认的分类上传整批文章
python3 .agents/skills/uploading-2-51cto/scripts/51cto_uploader.py tmp/articles --personal-category "人工智能"

# 重传失败保留文件
python3 .agents/skills/uploading-2-51cto/scripts/51cto_uploader.py --retry-manifest

# 放弃重传并删除保留文件
python3 .agents/skills/uploading-2-51cto/scripts/51cto_uploader.py --discard-manifest
```

上传成功后本地 Markdown 会按 skill 规则删除；失败或结果未知时会保留并写入 `tmp/51cto_retry.json`，需要用户确认是否重传。

### 使用 Codex 编排完整流程

根目录的 [`AGENTS.md`](AGENTS.md) 定义了 Codex 的“发布前预检 + 三步”工作流。发布前预检必须在步骤1之前完成；步骤1-3各使用独立 subagent，按顺序执行；不要在步骤1中并发启动多个备忘录导出任务。

## 日志与本地数据

默认日志目录为 `logs/`，临时文件目录为 `tmp/`。两者都被 `.gitignore` 忽略。

日志可能包含文章标题、文件路径、发布时间和 51CTO 结果 URL，请勿将日志、临时目录或 Chrome Profile 提交到 Git 或上传到公开位置。

## 安全与隐私

- API Key 由 `configure_env.py` 保存到仓库外的 `~/.config/autodoc/env`。
- 51CTO 登录 Cookie 保存在本地 Chrome Profile 中，不在仓库内。
- 不要把 `.env`、`.mcp.json`、Chrome Profile、日志或包含个人信息的文章提交到 Git。
- 发现安全问题时，请不要在公开 Issue 中粘贴密钥、Cookie 或完整日志；报告方式见 [`SECURITY.md`](SECURITY.md)。

## 已知限制

- 备忘录导出依赖 macOS Notes 和 AppleScript，不能在纯 Linux 环境运行。
- 51CTO 页面结构变化可能导致上传脚本失效。
- 51CTO 发布页偶发出现“请选择二级分类”提示，但文章可能已进入审核；此时以上传后的用户中心状态为准，不要盲目重传。详见 `references/README.md`。
- LLM 优化会产生 API 调用费用，并受 Provider 可用性影响。
- 当前没有自动化测试套件；正式使用前请先在小范围内验证。

## 开发与贡献

开发环境、代码风格、验证方式和 PR 要求见 [`CONTRIBUTING.md`](CONTRIBUTING.md)。参与项目即表示同意遵守 [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)。

## License

本项目使用 [MIT License](LICENSE)。
