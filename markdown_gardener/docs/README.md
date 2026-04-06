# Markdown 文档优化工具

对已有的 Markdown 格式文件进行优化，使文档内容能够更好地在互联网技术博客平台上展示。

## 功能特性

通过单次 LLM 调用完成所有优化，最小化 token 消耗：

1. 删除多余空白内容（词语间空格、过多空行）
2. 将 `tips:` 内容转换为 `> Tips:` 引用格式
3. 将 `注意:` 内容转换为 `> 注意:` 引用格式
4. 自动生成前言章节（删除原文第一个标题）
5. 提升文章标题级别（`#` → `##`）
6. 在大章节之间添加分隔符 `---`
7. 在前言与第一章节之间添加目录 `@[toc](目录)`
8. 为代码段添加高亮显示
9. 自动生成总结章节
10. 为无图片文章添加配图（优先成品图片，兜底生成 ASCII 图形）
11. 智能高亮重点语句
12. 自动移除 base64 图片数据（避免 LLM context 溢出）

## 安装

```bash
pip install pyyaml langchain-core langchain-anthropic
```

## LLM 配置

所有配置集中在 `conf/config.yaml`：

```yaml
provider: litellm

litellm:
  api_base: "http://localhost:4000"
  api_key: ""  # 填写你的密钥

model:
  litellm: minimax-m2.7

generation:
  max_tokens: 131072  # 128K, within minimax-2.7 limit
```

支持多种 LLM 提供者：OpenAI、Anthropic、Azure OpenAI、Google VertexAI、LiteLLM。

## 使用方法

```bash
# 基本用法
python -m markdown_gardener.markdown_gardener /path/to/document.md

# 指定 API 密钥
python -m markdown_gardener.markdown_gardener /path/to/doc.md --api-key "your-key"
```

## 命令行参数

| 参数 | 说明 |
|------|------|
| `file` | 要优化的 Markdown 文件路径（必填） |
| `-l, --log` | 日志文件路径，默认：`logs/markdown_gardener.log` |
| `--api-key` | LLM API 密钥，覆盖配置文件中的设置 |

## 优化示例

**输入：**
```markdown
# etcd mvcc

本文介绍etcd mvcc模块。

## 什么是 MVCC

MVCC是多版本并发控制。

tips:

    MVCC实现原理
    支持事务隔离
```

**输出：**
```markdown
# 前言

本文将介绍etcd中MVCC模块的核心概念与实现原理...

@[toc](目录)

---

# 什么是 MVCC

MVCC是多版本并发控制。

> Tips: `MVCC实现原理`支持事务隔离。

## 1.1 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                      MVCC 模块                              │
├────────────────────────┬────────────────────────────────────┤
│      treeIndex         │            Backend                 │
└────────────────────────┴────────────────────────────────────┘
```

---

# 总结

...
```

## 项目结构

```
markdown_gardener/
├── __init__.py
├── markdown_gardener.py     # 主程序（~370行）
├── llm_client.py            # LLM 客户端
├── conf/
│   └── config.yaml          # LLM 配置
├── prompts/
│   └── optimize.yaml        # 综合优化模板
└── docs/
    └── README.md
```

## 配图规则

1. **优先成品图片**：先尝试在互联网寻找合适的图片链接
2. **兜底 ASCII 图形**：若找不到成品图片，自动生成 ASCII 字符图形
3. **嵌入章节**：配图嵌入到相关章节中，不占用独立章节
4. **保留原文图片**：如果原文已包含 base64 图片，保留不变

## 日志

日志保存在 `logs/markdown_gardener.log`，JSON 格式：

```json
{
  "timestamp": "2026-04-05T10:30:00.123456",
  "level": "info",
  "file": "/path/to/doc.md",
  "event": "llm_optimize_complete",
  "operations": ["llm_full_optimize"]
}
```

## 自定义 Prompt

修改 `prompts/optimize.yaml` 可自定义优化行为和输出格式。

## 注意

- 脚本直接修改原文件，使用前请备份重要文档
- base64 图片会在优化前自动移除，避免 LLM context 溢出
- 配图优先使用互联网成品图片，兜底生成 ASCII 图形

## License

MIT
