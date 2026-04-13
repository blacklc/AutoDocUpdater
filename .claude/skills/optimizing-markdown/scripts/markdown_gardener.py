#!/usr/bin/env python3
"""
Markdown 文档优化工具

该模块提供对 Markdown 文档进行优化处理的功能，使文档内容能够更好地
在互联网技术博客平台上展示。通过单次 LLM 调用完成所有优化操作。
"""

import argparse
import json
import logging
import logging.handlers
import re
import sys
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# 将 skill 根目录添加到 Python 路径，以便导入 llm_client
_SKILL_ROOT = Path(__file__).parent.parent
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))


@dataclass
class OptimizeResult:
    """优化结果数据类"""

    file_path: str = ""
    success: bool = False
    error: Optional[str] = None
    operations: list[str] = field(default_factory=list)


class MarkdownGardener:
    """Markdown 文档优化器

    通过单次 LLM 调用完成所有优化处理，包括：
    - 删除多余空白内容
    - 转换 tips 和注意格式为引用格式
    - 添加前言和总结章节
    - 提升标题级别
    - 添加分隔符和目录
    - 代码高亮处理
    - 重点语句高亮
    """

    def __init__(
        self,
        file_path: str,
        logger: Optional[logging.Logger] = None,
        llm_client: Optional["LLMClient"] = None,
        prompt_template_dir: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        """初始化优化器

        @param file_path: Markdown 文件路径
        @type  file_path: str
        @param logger: 日志记录器
        @type  logger: Optional[logging.Logger]
        @param llm_client: LLM 客户端实例，不提供则自动创建
        @type  llm_client: Optional[LLMClient]
        @param prompt_template_dir: Prompt 模板目录
        @type  prompt_template_dir: Optional[str]
        @param api_key: LLM API 密钥，用于覆盖配置文件中的设置
        @type  api_key: Optional[str]
        """
        self.file_path = Path(file_path)
        self.logger = logger
        self.content: list[str] = []
        self.operations: list[str] = []
        self._api_key = api_key

        # 初始化 LLM 客户端
        if llm_client is not None:
            self._llm_client = llm_client
        else:
            self._llm_client = None

        # 初始化 Prompt 模板管理器
        self._prompt_template_dir = prompt_template_dir

        # 加载配置并计算 chunk 大小
        self._config = None
        self._init_chunk_sizes()

    def _log(self, level: str, data: dict) -> None:
        """记录 JSON 格式日志

        @param level: 日志级别 (info, warning, error)
        @type  level: str
        @param data: 日志数据
        @type  data: dict
        """
        if self.logger:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "level": level,
                "file": str(self.file_path),
                **data
            }
            getattr(self.logger, level.lower())(json.dumps(log_entry, ensure_ascii=False))

    def _get_llm_client(self) -> "LLMClient":
        """获取 LLM 客户端实例

        @return: LLM 客户端
        @rtype:  LLMClient
        """
        if self._llm_client is None:
            from llm_client import LLMClient

            # 获取配置文件路径
            config_path = _SKILL_ROOT / "conf" / "config.yaml"

            # 如果提供了 api_key，传递给 LLMClient
            if self._api_key:
                self._llm_client = LLMClient(
                    config_path=str(config_path),
                    api_key=self._api_key
                )
            else:
                self._llm_client = LLMClient(config_path=str(config_path))

        return self._llm_client

    def _get_prompt_template(self, name: str = "optimize") -> "PromptTemplate":
        """获取 Prompt 模板管理器实例

        @param name: 模板名称，不含扩展名
        @type  name: str
        @return: Prompt 模板管理器
        @rtype:  PromptTemplate
        """
        from llm_client import PromptTemplate

        if self._prompt_template_dir:
            return PromptTemplate(self._prompt_template_dir)
        else:
            template_dir = _SKILL_ROOT / "prompts"
            return PromptTemplate(str(template_dir))

    def _load_prompt(self, name: str, **kwargs) -> str:
        """加载并渲染指定的 prompt 模板

        @param name: 模板名称（不含 .yaml 扩展名）
        @type  name: str
        @param kwargs: 模板变量
        @type  kwargs: dict
        @return: 渲染后的 prompt
        @rtype:  str
        """
        prompt_template = self._get_prompt_template(name)
        return prompt_template.render(name, **kwargs)

    def load(self) -> None:
        """加载 Markdown 文件内容

        @raises FileNotFoundError: 文件不存在时抛出
        @raises IOError: 读取文件失败时抛出
        """
        if not self.file_path.exists():
            raise FileNotFoundError(f"文件不存在: {self.file_path}")

        with open(self.file_path, "r", encoding="utf-8") as f:
            self.content = f.read().splitlines()

        self._log("info", {"event": "file_loaded", "lines": len(self.content)})

    def save(self) -> None:
        """保存优化后的内容到原文件

        @raises IOError: 写入文件失败时抛出
        """
        with open(self.file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(self.content))

        self._log("info", {
            "event": "file_saved",
            "operations": self.operations
        })

    def optimize(self) -> OptimizeResult:
        """使用 LLM 一次性完成所有优化操作

        @return: 优化结果
        @rtype:  OptimizeResult
        """
        try:
            self.load()

            # 构建完整文章内容
            article_content = "\n".join(self.content)

            if not article_content.strip():
                raise ValueError("文章内容为空")

            self._log("info", {
                "event": "llm_optimize_start",
                "content_length": len(article_content)
            })

            # 使用单个 LLM 调用完成所有优化
            optimized_content = self._optimize_all_with_llm(article_content)

            if not optimized_content or not optimized_content.strip():
                raise RuntimeError("LLM 返回内容为空")

            # 更新内容
            self.content = optimized_content.split("\n")

            self.operations.append("llm_full_optimize")
            self._log("info", {
                "event": "llm_optimize_complete",
                "operations": self.operations
            })

            self.save()

            return OptimizeResult(
                file_path=str(self.file_path),
                success=True,
                operations=self.operations.copy()
            )

        except Exception as e:
            error_msg = str(e)
            self._log("error", {"event": "optimize_failed", "error": error_msg})
            return OptimizeResult(
                file_path=str(self.file_path),
                success=False,
                error=error_msg,
                operations=self.operations.copy()
            )

    def _init_chunk_sizes(self) -> None:
        """从配置文件加载 max_tokens 并初始化 chunk 大小

        根据 max_tokens 动态计算各阶段的 chunk 大小阈值：
        - 正文优化 chunk：max_tokens 的约 45%（保留空间给 prompt）
        - 摘要 chunk：max_tokens 的约 10%
        - 前言总结输入：max_tokens 的约 15%
        """
        import yaml

        config_path = _SKILL_ROOT / "conf" / "config.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            self._config = yaml.safe_load(f)

        max_tokens = self._config.get("generation", {}).get("max_tokens", 131072)

        # 根据 max_tokens 计算 chunk 大小（按字符计，约等于 token 数的 1/4）
        self.MAX_CHUNK_SIZE = int(max_tokens * 0.45)          # 正文优化 chunk
        self.MAX_SUMMARY_CHUNK_SIZE = int(max_tokens * 0.10)  # 摘要生成 chunk
        self.MAX_INTRO_SUMMARY_INPUT = int(max_tokens * 0.15)  # 前言总结输入

        self._log("info", {
            "event": "chunk_sizes_initialized",
            "max_tokens": max_tokens,
            "max_chunk_size": self.MAX_CHUNK_SIZE,
            "max_summary_chunk_size": self.MAX_SUMMARY_CHUNK_SIZE,
            "max_intro_summary_input": self.MAX_INTRO_SUMMARY_INPUT
        })

    def _remove_base64_images(self, content: str) -> tuple[str, int]:
        """删除文章中的 base64 图片信息

        @param content: 文章内容
        @type  content: str
        @return: (删除图片后的内容, 删除的图片数量)
        @rtype:  tuple[str, int]
        """
        # 检查是否存在 base64 图片的特征（![] 或 data:image）
        if '![]' not in content or 'data:image' not in content:
            return content, 0

        # 匹配 base64 图片的正则表达式
        # 格式: ![alt](data:image/png;base64,xxxxx...) 或 ![alt]( data:image/png;base64,xxxxx...)
        # 也支持只有 ![](data:...) 或 ![]( data:...) 格式
        pattern = r'!\[[^\]]*\]\s*\(\s*data:image/[^;]+;base64,[^\)]+\)'

        # 计算图片数量
        images = re.findall(pattern, content)
        count = len(images)

        if count > 0:
            # 删除所有 base64 图片
            cleaned_content = re.sub(pattern, '', content)

            # 清理多余的空行
            cleaned_content = re.sub(r'\n{3,}', '\n\n', cleaned_content)

            self._log("info", {
                "event": "base64_images_removed",
                "count": count,
                "original_length": len(content),
                "cleaned_length": len(cleaned_content)
            })

            return cleaned_content, count

        return content, 0

    def _optimize_all_with_llm(self, article_content: str) -> str:
        """五阶段优化：
        阶段0：删除原文第一行（通常是标题行）
        阶段1：移除 base64 图片
        阶段2：优化正文（分块，不生成前言和总结）
        阶段3：生成摘要（分块）
        阶段4：生成前言和总结
        阶段5：组装最终结果

        @param article_content: 文章完整内容
        @type  article_content: str
        @return: 优化后的文章内容
        @rtype:  str
        @raises RuntimeError: LLM 调用失败时抛出
        """
        # 阶段0：删除原文第一行（通常是标题行）
        lines = article_content.split("\n")
        if lines:
            deleted_line = lines[0]
            article_content = "\n".join(lines[1:])
            self._log("info", {
                "event": "first_line_removed",
                "deleted_line": deleted_line[:50] + "..." if len(deleted_line) > 50 else deleted_line
            })

        # 阶段1：移除 base64 图片
        cleaned_content, _ = self._remove_base64_images(article_content)

        # 阶段1：优化正文（可能分块）
        self._log("info", {
            "event": "stage1_optimize_body_start",
            "content_length": len(cleaned_content)
        })

        if len(cleaned_content) <= self.MAX_CHUNK_SIZE:
            # 短文章：直接优化，不生成前言总结
            optimized_body = self._optimize_body_only(cleaned_content, is_single_chunk=True)
        else:
            # 长文章：分块优化
            optimized_body = self._optimize_body_with_chunking(cleaned_content)

        self._log("info", {
            "event": "stage1_optimize_body_complete",
            "optimized_body_length": len(optimized_body)
        })

        # 阶段2：生成摘要（分块）
        self._log("info", {
            "event": "stage2_generate_summary_start",
            "content_length": len(optimized_body)
        })

        if len(optimized_body) <= self.MAX_SUMMARY_CHUNK_SIZE:
            # 短文章：直接生成摘要
            summary = self._generate_summary_single(optimized_body)
        else:
            # 长文章：分块生成摘要
            summary = self._generate_summary_with_chunking(optimized_body)

        self._log("info", {
            "event": "stage2_generate_summary_complete",
            "summary_length": len(summary)
        })

        # 阶段3：生成前言和总结
        self._log("info", {
            "event": "stage3_generate_intro_summary_start"
        })

        intro_summary = self._generate_intro_summary(optimized_body, summary)

        self._log("info", {
            "event": "stage3_generate_intro_summary_complete"
        })

        # 阶段4：组装最终结果
        final_content = self._assemble_final_content(
            intro_summary["intro"],
            optimized_body,
            intro_summary["summary"]
        )

        self._log("info", {
            "event": "all_stages_complete",
            "final_content_length": len(final_content)
        })

        return final_content

    def _optimize_body_only(self, article_content: str, is_single_chunk: bool = False) -> str:
        """优化正文，不生成前言和总结

        @param article_content: 文章内容
        @type  article_content: str
        @param is_single_chunk: 是否为单个chunk（短文章）
        @type  is_single_chunk: bool
        @return: 优化后的正文
        @rtype:  str
        """
        prompt = self._load_prompt("optimize_body", article_content=article_content)

        llm_client = self._get_llm_client()
        llm_response = llm_client.generate(prompt)

        self._log("info", {
            "event": "llm_body_optimized",
            "model": llm_client.get_model_name(),
            "prompt_length": len(prompt),
            "response_length": len(llm_response),
            "is_single_chunk": is_single_chunk
        })

        return llm_response

    def _optimize_body_with_chunking(self, article_content: str) -> str:
        """分块优化正文（每个chunk不生成前言和总结）

        @param article_content: 文章完整内容
        @type  article_content: str
        @return: 优化后的正文
        @rtype:  str
        """
        chunks = self._split_into_chunks(article_content, self.MAX_CHUNK_SIZE)
        total_chunks = len(chunks)

        self._log("info", {
            "event": "body_chunking_started",
            "total_chunks": total_chunks,
            "total_length": len(article_content)
        })

        optimized_chunks = []
        for i, chunk in enumerate(chunks):
            self._log("info", {
                "event": "processing_body_chunk",
                "chunk_index": i + 1,
                "chunk_number": total_chunks,
                "chunk_length": len(chunk)
            })

            prompt = self._load_prompt("optimize_body", article_content=chunk)

            llm_client = self._get_llm_client()
            llm_response = llm_client.generate(prompt)

            optimized_chunks.append(llm_response)

            self._log("info", {
                "event": "body_chunk_processed",
                "chunk_index": i + 1,
                "response_length": len(llm_response)
            })

        result = "\n\n---\n\n".join(optimized_chunks)

        self._log("info", {
            "event": "body_chunking_completed",
            "total_chunks": total_chunks,
            "result_length": len(result)
        })

        return result

    def _generate_summary_single(self, content: str) -> str:
        """为短文章生成本段摘要

        @param content: 文章内容
        @type  content: str
        @return: 摘要内容
        @rtype:  str
        """
        # 限制输入长度
        max_input = self.MAX_SUMMARY_CHUNK_SIZE * 2
        content_input = content[:max_input] if len(content) > max_input else content

        prompt = self._load_prompt(
            "summary",
            chunk_index=1,
            total_chunks=1,
            content=content_input,
            summary_length=200
        )

        llm_client = self._get_llm_client()
        summary = llm_client.generate(prompt)

        self._log("info", {
            "event": "summary_single_generated",
            "summary_length": len(summary)
        })

        return summary

    def _generate_summary_with_chunking(self, content: str) -> str:
        """分块生成分段摘要，然后合并

        @param content: 文章完整内容
        @type  content: str
        @return: 合并后的摘要
        @rtype:  str
        """
        chunks = self._split_into_chunks(content, self.MAX_SUMMARY_CHUNK_SIZE)
        total_chunks = len(chunks)

        self._log("info", {
            "event": "summary_chunking_started",
            "total_chunks": total_chunks,
            "total_length": len(content)
        })

        chunk_summaries = []
        for i, chunk in enumerate(chunks):
            self._log("info", {
                "event": "processing_summary_chunk",
                "chunk_index": i + 1,
                "chunk_number": total_chunks,
                "chunk_length": len(chunk)
            })

            prompt = self._load_prompt(
                "summary",
                chunk_index=i + 1,
                total_chunks=total_chunks,
                content=chunk,
                summary_length=150
            )

            llm_client = self._get_llm_client()
            chunk_summary = llm_client.generate(prompt)
            chunk_summaries.append(chunk_summary)

            self._log("info", {
                "event": "summary_chunk_processed",
                "chunk_index": i + 1,
                "summary_length": len(chunk_summary)
            })

        # 合并所有摘要
        combined_summary = "\n".join(chunk_summaries)

        self._log("info", {
            "event": "summary_chunking_completed",
            "total_chunks": total_chunks,
            "combined_length": len(combined_summary)
        })

        return combined_summary

    def _generate_intro_summary(self, optimized_body: str, summary: str) -> dict:
        """基于摘要生成前言和总结

        @param optimized_body: 优化后的正文
        @type  optimized_body: str
        @param summary: 文章摘要
        @type  summary: str
        @return: {"intro": 前言, "summary": 总结}
        @rtype:  dict
        """
        # 限制输入长度
        summary_input = summary[:10000] if len(summary) > 10000 else summary
        body_for_context = optimized_body[:15000] if len(optimized_body) > 15000 else optimized_body

        prompt = self._load_prompt(
            "intro_summary",
            summary=summary_input,
            body_context=body_for_context,
            intro_length=100,
            summary_length=150
        )

        llm_client = self._get_llm_client()
        response = llm_client.generate(prompt)

        # 解析前言和总结
        intro = ""
        summary_text = ""

        lines = response.split("\n")
        current_section = None
        current_content = []

        for line in lines:
            if line.strip() == "# 前言":
                current_section = "intro"
                current_content = []
            elif line.strip() == "# 总结":
                if current_section == "intro" and current_content:
                    intro = "\n".join(current_content).strip()
                current_section = "summary"
                current_content = []
            elif current_section:
                current_content.append(line)

        if current_section == "summary" and current_content:
            summary_text = "\n".join(current_content).strip()

        # 如果解析失败，使用默认格式
        if not intro:
            intro = summary_text[:100] + "..." if summary_text else "本文介绍了相关技术内容。"
        if not summary_text:
            summary_text = intro + "通过本文，读者可以深入了解相关知识点。"

        self._log("info", {
            "event": "intro_summary_generated",
            "intro_length": len(intro),
            "summary_length": len(summary_text)
        })

        return {
            "intro": intro,
            "summary": summary_text
        }

    def _assemble_final_content(self, intro: str, optimized_body: str, summary: str) -> str:
        """组装最终内容

        @param intro: 前言
        @type  intro: str
        @param optimized_body: 优化后的正文
        @type  optimized_body: str
        @param summary: 总结
        @type  summary: str
        @return: 最终内容
        @rtype:  str
        """
        # 构建最终结构：
        # # 前言
        # [前言内容]
        # ---
        # @[toc](目录)
        # ---
        # [优化后的正文]
        # ---
        # # 总结
        # [总结内容]

        parts = []

        # 检查前言和正文是否已包含目录章节
        intro_has_toc = "@[toc](目录)" in intro
        body_has_toc = "@[toc](目录)" in optimized_body
        need_add_toc = not (intro_has_toc or body_has_toc)

        parts.append("# 前言")
        parts.append(intro)

        # 如果前言或正文没有目录章节，则添加
        if need_add_toc:
            parts.append("")
            parts.append("---")
            parts.append("")
            parts.append("@[toc](目录)")
            parts.append("")
            parts.append("---")
            parts.append("")

        parts.append(optimized_body)

        # 总结分隔
        parts.append("")
        parts.append("---")
        parts.append("")
        parts.append("# 总结")
        parts.append(summary)

        result = "\n".join(parts)

        self._log("info", {
            "event": "final_content_assembled",
            "result_length": len(result),
            "intro_length": len(intro),
            "body_length": len(optimized_body),
            "summary_length": len(summary)
        })

        return result

    def _optimize_single_chunk(self, article_content: str) -> str:
        """优化单个内容块

        @param article_content: 内容块
        @type  article_content: str
        @return: 优化后的内容
        @rtype:  str
        """
        prompt_template = self._get_prompt_template()
        prompt = prompt_template.render("optimize", article_content=article_content)

        llm_client = self._get_llm_client()
        llm_response = llm_client.generate(prompt)

        self._log("info", {
            "event": "llm_called",
            "model": llm_client.get_model_name(),
            "prompt_length": len(prompt),
            "response_length": len(llm_response)
        })

        return llm_response

    def _optimize_with_chunking(self, article_content: str) -> str:
        """分块处理长文章

        @param article_content: 文章完整内容
        @type  article_content: str
        @return: 优化后的文章内容
        @rtype:  str
        """
        chunks = self._split_into_chunks(article_content)
        total_chunks = len(chunks)
        self._log("info", {
            "event": "chunking_started",
            "total_chunks": total_chunks,
            "total_length": len(article_content)
        })

        optimized_chunks = []
        for i, chunk in enumerate(chunks):
            self._log("info", {
                "event": "processing_chunk",
                "chunk_index": i + 1,
                "chunk_length": len(chunk)
            })
            optimized = self._optimize_single_chunk(chunk)
            optimized_chunks.append(optimized)

        result = "\n\n---\n\n".join(optimized_chunks)

        self._log("info", {
            "event": "chunking_completed",
            "total_chunks": total_chunks,
            "result_length": len(result)
        })
        return result


    def _split_into_chunks(self, content: str, max_size: int = None) -> list[str]:
        """将长文章分割成多个块，在标题处分割以保持结构完整

        @param content: 文章内容
        @type  content: str
        @param max_size: 每个chunk的最大字符数，默认使用MAX_CHUNK_SIZE
        @type  max_size: int
        @return: 内容块列表
        @rtype:  list[str]
        """
        if max_size is None:
            max_size = self.MAX_CHUNK_SIZE

        lines = content.split("\n")
        chunks = []
        current_chunk = []
        current_size = 0

        for line in lines:
            line_size = len(line) + 1  # +1 for newline
            # 检查是否在标题处分割
            is_heading = line.startswith("#")

            if is_heading and current_chunk and current_size + line_size > max_size:
                # 保存当前块并开始新块
                chunks.append("\n".join(current_chunk))
                current_chunk = [line]
                current_size = line_size
            else:
                current_chunk.append(line)
                current_size += line_size

        # 添加最后一个块
        if current_chunk:
            chunks.append("\n".join(current_chunk))

        return chunks

    def _optimize_single_chunk(self, article_content: str) -> str:
        """优化单个内容块（保留用于兼容）

        @param article_content: 内容块
        @type  article_content: str
        @return: 优化后的内容
        @rtype:  str
        """
        prompt_template = self._get_prompt_template()
        prompt = prompt_template.render("optimize", article_content=article_content)

        llm_client = self._get_llm_client()
        llm_response = llm_client.generate(prompt)

        self._log("info", {
            "event": "llm_called",
            "model": llm_client.get_model_name(),
            "prompt_length": len(prompt),
            "response_length": len(llm_response)
        })

        return llm_response

    def _optimize_with_chunking(self, article_content: str) -> str:
        """分块处理长文章（保留用于兼容）

        @param article_content: 文章完整内容
        @type  article_content: str
        @return: 优化后的文章内容
        @rtype:  str
        """
        chunks = self._split_into_chunks(article_content)
        total_chunks = len(chunks)
        self._log("info", {
            "event": "chunking_started",
            "total_chunks": total_chunks,
            "total_length": len(article_content)
        })

        optimized_chunks = []
        for i, chunk in enumerate(chunks):
            self._log("info", {
                "event": "processing_chunk",
                "chunk_index": i + 1,
                "chunk_length": len(chunk)
            })
            optimized = self._optimize_single_chunk(chunk)
            optimized_chunks.append(optimized)

        result = "\n\n---\n\n".join(optimized_chunks)

        self._log("info", {
            "event": "chunking_completed",
            "total_chunks": total_chunks,
            "result_length": len(result)
        })
        return result


FORMAT = "%(asctime)s [%(levelname)s] %(funcName)s:%(lineno)d %(message)s"


def setup_logging(log_file: str = None) -> logging.Logger:
    """配置日志系统

    @param log_file: 日志文件路径，默认保存在 skill 目录所在目录的 logs 目录中
    @type  log_file: str
    @return: 配置好的日志记录器
    @rtype:  logging.Logger
    """
    logger = logging.getLogger("markdown_gardener")
    logger.setLevel(logging.INFO)

    if log_file is None:
        # 基于脚本文件位置计算路径，logs 目录与 skills 目录平级
        script_path = Path(__file__)
        # .claude/skills/optimizing-markdown/scripts/ -> .claude/skills/
        logs_dir = script_path.parents[2] / "logs"
        log_file = logs_dir / "markdown_gardener.log"

    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    rotating_handler = logging.handlers.TimedRotatingFileHandler(
        log_file,
        when="midnight",
        interval=1,
        backupCount=7,
        encoding="utf-8"
    )
    rotating_handler.setLevel(logging.INFO)
    rotating_handler.setFormatter(logging.Formatter(FORMAT, datefmt="%Y-%m-%d %H:%M:%S"))

    logger.addHandler(rotating_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(
        logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
    )
    logger.addHandler(console_handler)

    return logger


def log_json(logger: logging.Logger, level: str, data: dict) -> None:
    """以 JSON 格式记录日志

    @param logger: 日志记录器
    @type  logger: logging.Logger
    @param level: 日志级别 (info, warning, error)
    @type  level: str
    @param data: 日志数据
    @type  data: dict
    """
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "level": level,
        **data
    }
    getattr(logger, level.lower())(json.dumps(log_entry, ensure_ascii=False))


def validate_arguments(args: argparse.Namespace) -> None:
    """验证命令行参数

    @param args: 解析后的命令行参数
    @type  args: argparse.Namespace
    @raises ValueError: 文件路径未指定时抛出异常
    """
    if not args.file:
        raise ValueError("错误: 必须指定要优化的 Markdown 文件路径")


def parse_arguments() -> argparse.Namespace:
    """解析命令行参数

    @return: 解析后的命令行参数对象
    @rtype:  argparse.Namespace
    """
    parser = argparse.ArgumentParser(
        description="Markdown 文档优化工具 - 优化 Markdown 内容以便更好地在技术博客平台展示"
    )

    parser.add_argument(
        "file",
        type=str,
        help="要优化的 Markdown 文件路径"
    )

    parser.add_argument(
        "-l", "--log",
        default=None,
        help="日志文件路径, 默认: skill 目录所在目录的 logs 目录"
    )

    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="LLM API 密钥，用于覆盖配置文件中的设置"
    )

    return parser.parse_args()


def main() -> int:
    """主入口函数

    @return: 程序退出码，0 表示成功，非 0 表示有错误
    @rtype:  int
    """
    try:
        args = parse_arguments()
        validate_arguments(args)

        logger = setup_logging(args.log)

        log_json(logger, "info", {
            "event": "script_start",
            "file": args.file
        })

        gardener = MarkdownGardener(args.file, logger, api_key=args.api_key)
        result = gardener.optimize()

        if result.success:
            print(f"\n优化成功: {result.file_path}")
            print(f"执行的操作: {', '.join(result.operations) if result.operations else '无'}")

            log_json(logger, "info", {
                "event": "script_success",
                "result": {
                    "file_path": result.file_path,
                    "operations": result.operations
                }
            })
            return 0
        else:
            print(f"\n优化失败: {result.error}", file=sys.stderr)

            log_json(logger, "error", {
                "event": "script_failed",
                "error": result.error
            })
            return 1

    except ValueError as e:
        print(f"\n参数错误: {e}", file=sys.stderr)
        print("使用 --help 查看帮助信息", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\n\n操作已取消", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"\n未知错误: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
