---
name: optimizing-markdown
description: |
  对 Markdown 文档进行深度优化，使其更适合在技术博客平台（如 51CTO、掘金、CSDN 等）上展示。
  当用户提到"优化 Markdown"、"优化这些md文件"、"美化文章格式"、"优化技术博客文章"、"让Markdown更好看"、"优化md文件"或直接提供 .md 文件路径并要求优化时，务必使用此 skill。
  即使用户没有明确说出"skill"或"优化"这个词，只要意图是改善 Markdown 文章的展示效果，就应该触发此 skill。
  完整的 12 项优化能力详见 references/README.md。
---

# Optimizing Markdown Skill

对 Markdown 格式的技术文档进行深度优化，使其在互联网技术博客平台上具有更好的展示效果。

## 核心能力

通过多阶段 LLM 调用完成 12 项自动化优化（详细说明见 `references/README.md`）：

- 删除多余空白、转换 tips/注意 格式
- 自动生成前言和总结章节、添加目录
- 提升标题级别、添加章节分隔符
- 代码高亮、重点语句高亮、配图支持
- 自动移除 base64 图片以避免 context 溢出

## 使用方式

### 命令行调用

```bash
python3 {skill_path}/scripts/markdown_gardener.py "/path/to/article.md"
```

### 参数说明

| 参数 | 说明 |
|------|------|
| `file` | 要优化的 Markdown 文件路径（必填） |
| `-l, --log` | 日志文件路径，默认项目根目录的 `logs/` 目录 |

### 执行前环境检查

执行优化前必须先检查 LLM 环境变量：

```bash
python3 {skill_path}/scripts/check_env.py
```

- 返回码 `0`：环境已配置，可以继续。
- 返回码 `2`：缺少必要变量，不得继续调用 LLM。
- 缺少配置时，运行交互式配置脚本：

```bash
python3 {skill_path}/scripts/configure_env.py
```

配置脚本使用隐藏输入获取密钥，不会回显，并要求用户确认后写入 `~/.config/autodoc/env` 和 Shell 配置。

如果当前会话无法提供交互式终端，应要求用户在自己的终端中运行该脚本，而不是让用户把密钥粘贴到聊天窗口。

后续运行会自动读取 `~/.config/autodoc/env`。如需在当前普通终端中立即使用，可执行：

```bash
source ~/.config/autodoc/env
```

或重新打开终端。

**禁止要求用户在聊天窗口中粘贴 API Key。**

## 工作流程

采用 6 阶段优化流程：

1. **阶段0：删除原文第一行** — 删除原文的第一行内容（通常是标题行），避免重复
2. **阶段1：移除 base64 图片** — 删除 base64 图片，避免 LLM context 溢出
3. **阶段2：优化正文** — 根据文章长度决定是否分块处理，短文章直接优化，长文章在标题处分割
4. **阶段3：生成摘要** — 对优化后的正文生成分段摘要
5. **阶段4：生成前言和总结** — 基于摘要和正文上下文生成前言和总结
6. **阶段5：组装最终结果** — 拼接前言、目录、正文、总结，保存到原文件

## 长文章分块策略

分块阈值根据 `conf/config.yaml` 中的 `generation.max_tokens` 和 `chunking` 配置动态计算：
- 正文优化 chunk：`max_tokens * chunking.body_ratio`
- 摘要生成 chunk：`max_tokens * chunking.summary_ratio`
- 前言总结输入：`max_tokens * chunking.intro_summary_input_ratio`

默认 `max_tokens=131072`，各 chunk 阈值约为 59K、13K、20K 字符。

## 输出格式

优化后的文档结构：
```markdown
# 前言
[前言内容]

---

@[toc](目录)

---

# 1.章节标题
[内容]

---

# 总结
[总结内容]
```

## 注意事项

- **为文章添加配图**: 该操作的具体细节请参考`references/README.md中"为文章添加配图操作流程"这一章节.`
- **长文章处理**：分块阈值由配置文件的 `max_tokens` 动态计算，默认超过约 59K 字符的正文会自动分块处理

## 依赖

```bash
# 在项目根目录执行
pip install -r requirements.txt
```

OpenAI、Azure OpenAI 或 Google VertexAI Provider 还需要：

```bash
pip install -r requirements-optional.txt
```

## 配置方式

`conf/config.yaml` 只保存非敏感参数，例如 Provider、模型、API 地址、分块比例和生成长度，不得写入任何密钥。

密钥和运行环境通过 `AUTODOC_LLM_*` 环境变量提供：

```text
AUTODOC_LLM_PROVIDER
AUTODOC_LLM_MODEL
AUTODOC_LLM_API_BASE
AUTODOC_LLM_API_KEY
```

Azure 和 Google Vertex AI 的专属变量详见 `references/README.md`。支持 OpenAI / Anthropic / Azure OpenAI / Google VertexAI / LiteLLM。

## 项目结构

```
optimizing-markdown/
├── SKILL.md
├── scripts/
│   ├── markdown_gardener.py  # 主入口脚本
│   ├── llm_client.py         # LLM 客户端封装
│   ├── env_config.py         # 环境变量合并与预检
│   ├── check_env.py          # 环境预检命令
│   └── configure_env.py      # 交互式环境配置命令
├── conf/
│   └── config.yaml           # LLM 提供者和模型配置
├── prompts/
│   ├── optimize_body.yaml    # 正文优化 prompt
│   ├── summary.yaml          # 摘要生成 prompt
│   └── intro_summary.yaml    # 前言/总结生成 prompt
└── references/
    └── README.md             # 完整的 12 项优化说明
```

## 触发场景示例

- "优化一下这篇 Markdown 文章"
- "帮我美化这个 md 文件的格式"
- "把这个文章优化成博客风格"
- "优化 ./*.md 文件"
- 用户提供一个 `.md` 文件路径并要求优化格式
