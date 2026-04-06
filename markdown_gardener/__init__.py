"""
Markdown 文档优化工具包
"""

from .markdown_gardener import (
    MarkdownGardener,
    main,
)
from .llm_client import (
    LLMClient,
    LLMProvider,
    PromptTemplate,
)

__all__ = [
    "MarkdownGardener",
    "main",
    "LLMClient",
    "LLMProvider",
    "PromptTemplate",
]
__version__ = "1.0.0"
