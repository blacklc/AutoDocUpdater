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
import sys
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


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
            from .llm_client import LLMClient

            # 获取配置文件路径
            config_path = Path(__file__).parent / "conf" / "config.yaml"

            # 如果提供了 api_key，传递给 LLMClient
            if self._api_key:
                self._llm_client = LLMClient(
                    config_path=str(config_path),
                    api_key=self._api_key
                )
            else:
                self._llm_client = LLMClient(config_path=str(config_path))

        return self._llm_client

    def _get_prompt_template(self) -> "PromptTemplate":
        """获取 Prompt 模板管理器实例

        @return: Prompt 模板管理器
        @rtype:  PromptTemplate
        """
        from .llm_client import PromptTemplate

        if self._prompt_template_dir:
            return PromptTemplate(self._prompt_template_dir)
        else:
            template_dir = Path(__file__).parent / "prompts"
            return PromptTemplate(str(template_dir))

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

    # 分块处理阈值（字符数），留出余量避免接近限制
    MAX_CHUNK_SIZE = 100000

    def _remove_base64_images(self, content: str) -> tuple[str, int]:
        """删除文章中的 base64 图片信息

        @param content: 文章内容
        @type  content: str
        @return: (删除图片后的内容, 删除的图片数量)
        @rtype:  tuple[str, int]
        """
        import re

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
        """使用单个 LLM 调用完成所有优化，支持长文章分块处理

        @param article_content: 文章完整内容
        @type  article_content: str
        @return: 优化后的文章内容
        @rtype:  str
        @raises RuntimeError: LLM 调用失败时抛出
        """
        # 先删除 base64 图片，避免内容过长
        cleaned_content, removed_count = self._remove_base64_images(article_content)

        # 检查内容长度，决定是否需要分块
        if len(cleaned_content) <= self.MAX_CHUNK_SIZE:
            return self._optimize_single_chunk(cleaned_content)

        # 长文章分块处理
        return self._optimize_with_chunking(cleaned_content)

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


    def _split_into_chunks(self, content: str) -> list[str]:
        """将长文章分割成多个块，在标题处分割以保持结构完整

        @param content: 文章内容
        @type  content: str
        @return: 内容块列表
        @rtype:  list[str]
        """
        lines = content.split("\n")
        chunks = []
        current_chunk = []
        current_size = 0

        for line in lines:
            line_size = len(line) + 1  # +1 for newline
            # 检查是否在标题处分割
            is_heading = line.startswith("#")

            if is_heading and current_chunk and current_size + line_size > self.MAX_CHUNK_SIZE:
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


FORMAT = "%(asctime)s [%(levelname)s] %(funcName)s:%(lineno)d %(message)s"


def setup_logging(log_file: str = "logs/markdown_gardener.log") -> logging.Logger:
    """配置日志系统

    @param log_file: 日志文件路径，默认保存在项目根目录的 logs 目录
    @type  log_file: str
    @return: 配置好的日志记录器
    @rtype:  logging.Logger
    """
    logger = logging.getLogger("markdown_gardener")
    logger.setLevel(logging.INFO)

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
        default="logs/markdown_gardener.log",
        help="日志文件路径, 默认: logs/markdown_gardener.log"
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
