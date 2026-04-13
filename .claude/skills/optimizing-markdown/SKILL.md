---
name: optimizing-markdown
description: |
  对 Markdown 文档进行深度优化，使其更适合在技术博客平台（如 51CTO、掘金、CSDN 等）上展示。
  当用户提到"优化 Markdown"、"优化这些md文件"、"美化文章格式"、"优化技术博客文章"、"让Markdown更好看"、"优化md文件"或直接提供 .md 文件路径并要求优化时，务必使用此 skill。
  即使用户没有明确说出"skill"或"优化"这个词，只要意图是改善 Markdown 文章的展示效果，就应该触发此 skill。
  完整的 11 项优化能力详见 references/README.md。
---

# Optimizing Markdown Skill

对 Markdown 格式的技术文档进行深度优化，使其在互联网技术博客平台上具有更好的展示效果。

## 核心能力

通过多阶段 LLM 调用完成 11 项自动化优化（详细说明见 `references/README.md`）：

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

> 注意: 该脚本的最大并行调用数为 3.

### 参数说明

| 参数 | 说明 |
|------|------|
| `file` | 要优化的 Markdown 文件路径（必填） |
| `--api-key` | LLM API 密钥，可覆盖配置文件中的设置 |
| `-l, --log` | 日志文件路径，默认 skill 目录所在目录的 logs 目录 |

## 工作流程

采用 6 阶段优化流程：

1. **阶段0：删除原文第一行** — 删除原文的第一行内容（通常是标题行），避免重复
2. **阶段1：移除 base64 图片** — 删除 base64 图片，避免 LLM context 溢出
3. **阶段2：优化正文** — 根据文章长度决定是否分块处理，短文章直接优化，长文章在标题处分割
4. **阶段3：生成摘要** — 对优化后的正文生成分段摘要
5. **阶段4：生成前言和总结** — 基于摘要和正文上下文生成前言和总结
6. **阶段5：组装最终结果** — 拼接前言、目录、正文、总结，保存到原文件

## 长文章分块策略

分块阈值根据配置文件中的 `max_tokens` 动态计算：
- 正文优化 chunk：`max_tokens * 45%`
- 摘要生成 chunk：`max_tokens * 10%`
- 前言总结输入：`max_tokens * 15%`

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
pip install pyyaml langchain-core langchain-anthropic
```

## 配置文件

优化的具体操作是通过调用llm来进行实现的, 因此功能中会涉及到调用llm. LLM的相关配置位于 `{skill_path}/conf/config.yaml`文件中.
支持 OpenAI / Anthropic / Azure OpenAI / Google VertexAI / LiteLLM。

## 项目结构

```
optimizing-markdown/
├── SKILL.md
├── scripts/
│   ├── markdown_gardener.py  # 主入口脚本
│   └── llm_client.py         # LLM 客户端封装
├── conf/
│   └── config.yaml           # LLM 提供者和模型配置
├── prompts/
│   ├── optimize.yaml         # 正文优化 prompt
│   ├── optimize_body.yaml    # 分块正文优化 prompt
│   ├── summary.yaml          # 摘要生成 prompt
│   └── intro_summary.yaml    # 前言/总结生成 prompt
└── references/
    └── README.md             # 完整的 11 项优化说明
```

## 触发场景示例

- "优化一下这篇 Markdown 文章"
- "帮我美化这个 md 文件的格式"
- "把这个文章优化成博客风格"
- "优化 ./*.md 文件"
- 用户提供一个 `.md` 文件路径并要求优化格式
