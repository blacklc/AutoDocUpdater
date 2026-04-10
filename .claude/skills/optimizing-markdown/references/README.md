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
| `-l, --log` | 日志文件路径，默认：skill 目录所在目录的 logs 目录 |
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
optimizing-markdown/
├── SKILL.md
├── scripts/
│   ├── markdown_gardener.py  # 入口脚本
│   └── llm_client.py        # LLM 客户端
├── conf/
│   └── config.yaml          # LLM 配置
├── prompts/
│   └── optimize.yaml        # 优化提示词模板
└── references/
    └── README.md            # 本文档
```

## 扩展：新增 LLM Provider

本工具采用**开闭原则**设计，新增 Provider 无需修改现有代码，只需实现抽象接口并注册即可。

### 步骤说明

#### 1. 创建 Provider 类

继承 `LLMProvider` 抽象基类，实现两个抽象方法和一个类方法：

```python
from llm_client import LLMProvider
from typing import Optional

class MyProvider(LLMProvider):
    """自定义 LLM 提供者"""

    # 定义 Provider 标识名
    PROVIDER_NAME = "my_provider"

    @classmethod
    def build_params_from_config(cls, config: dict, model_config: dict, override_kwargs: dict) -> dict:
        """从配置构建 Provider 初始化参数

        实现配置解析逻辑，将 YAML 配置转换为初始化参数。
        """
        # 获取当前 Provider 的配置段
        provider_config = config.get(cls.PROVIDER_NAME, {})

        params = {
            # 从 model_config 获取模型名，提供默认值
            "model_name": override_kwargs.pop(
                "model_name",
                model_config.get(cls.PROVIDER_NAME, "default-model")
            ),
            # Provider 特有配置项
            "api_key": override_kwargs.pop("api_key", provider_config.get("api_key", "")),
            "api_base": override_kwargs.pop("api_base", provider_config.get("api_base", "")),
            # 其他配置...
        }
        return params

    def __init__(self, model_name: str, api_key: str, api_base: str, **kwargs):
        """初始化 Provider"""
        self.model_name = model_name
        self.api_key = api_key
        self.api_base = api_base
        self.kwargs = kwargs
        self._client = None

    def generate(self, prompt: str, **kwargs) -> str:
        """实现文本生成逻辑"""
        # 调用 LLM API 生成文本
        # response = self._client.generate(prompt, **kwargs)
        # return response.content
        pass

    def get_model_name(self) -> str:
        """返回当前模型名称"""
        return self.model_name
```

#### 2. 注册 Provider

在 `LLMClient.PROVIDER_CLASSES` 字典中注册新 Provider：

```python
# llm_client.py

class LLMClient:
    PROVIDER_CLASSES = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "azure_openai": AzureOpenAIProvider,
        "google_vertexai": GoogleVertexAIProvider,
        "litellm": LiteLLMProvider,
        # 注册新 Provider
        "my_provider": MyProvider,
    }
```

#### 3. 添加配置

在 `conf/config.yaml` 中添加新 Provider 的配置：

```yaml
# 设置默认 Provider
provider: my_provider

# Provider 特有配置
my_provider:
  api_base: "https://api.example.com/v1"
  api_key: "your-api-key-here"

# 模型映射
model:
  my_provider: my-model-name

# 生成参数（通用）
generation:
  max_tokens: 131072
  temperature: 0.7
```

### 设计原则

| 特性 | 说明 |
|------|------|
| **开闭原则** | 新增 Provider 无需修改 `LLMClient`，仅需实现接口并注册 |
| **配置自治** | 每个 Provider 负责解析自己的配置，避免集中式 if-else |
| **类型安全** | 抽象基类强制要求实现必要方法，编译期即可发现问题 |
| **易于测试** | 可独立测试每个 Provider 的配置解析和生成逻辑 |

## 为文章添加配图操作流程

1. 检测原文内是否已经包含有配图.此时可通过使用正则匹配检查原文中是否存在以“![]( data:image/webp;base64,”为开头的文段;如果存在则表示原文中带有配图.
2. 如果原文中带有配图, 则应该将加载到原文内容中的配图数据全部清除后再发送给llm做内容优化.```务必要保证发送给llm的原文内容中不包含这些配图```.
3. 如果原文中不带有配图, 则应该准许以下原则: 1.**优先成品图片**：先尝试在互联网寻找合适的图片链接; 2.**兜底 ASCII 图形**：若找不到成品图片，自动生成 ASCII 字符图形;3.**嵌入章节**：配图嵌入到相关章节中，不占用独立章节

## 日志

日志保存在 skill 目录所在目录的 logs 目录中，JSON 格式：

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
