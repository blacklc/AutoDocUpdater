#!/usr/bin/env python3
"""
MAC OS 备忘录导出工具

该模块提供从 MAC OS 备忘录应用中导出文章到本地文件的功能。
支持导出为 Markdown 和 PDF 格式，支持按文章名称或标签筛选导出。
"""

import argparse
import json
import logging
import logging.handlers
import os
import shutil
import subprocess
import sys
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class ExportFormat(Enum):
    """导出格式枚举"""

    MARKDOWN = "md"
    PDF = "pdf"


@dataclass
class ExportResult:
    """导出结果数据类"""

    input: dict = field(default_factory=dict)
    export: dict = field(default_factory=dict)
    failed: dict = field(default_factory=dict)


class NotesExporter:
    """备忘录导出器

    负责从 MAC OS 备忘录应用获取文章内容并导出为指定格式。
    使用 AppleScript 与备忘录应用交互，支持导出多篇文章。
    支持按文章名称或标签筛选。
    """

    def __init__(self, output_dir: str = "."):
        """初始化导出器

        @param output_dir: 导出文件存放目录
        @type  output_dir: str
        """
        self.output_dir = Path(output_dir)
        self._ensure_output_dir()

    def _ensure_output_dir(self) -> None:
        """确保输出目录存在，不存在则创建"""
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _html_to_markdown(self, html_content: str) -> str:
        """将 HTML 内容转换为 Markdown

        @param html_content: HTML 格式内容
        @type  html_content: str
        @return: Markdown 格式内容
        @rtype:  str
        """
        import re

        md = html_content

        def merge_h_tags(match):
            h_tags = re.findall(r'<h([1-6])>(.*?)</h\1>', match.group(0))
            if h_tags:
                level = h_tags[0][0]
                content_parts = []
                for _, tag_content in h_tags:
                    clean_content = re.sub(r'<br\s*/?>', '', tag_content).strip()
                    if clean_content:
                        content_parts.append(clean_content)
                if content_parts:
                    content = ' '.join(content_parts)
                    return f'{"#" * int(level)} {content}'
            return match.group(0)

        md = re.sub(r'<div>((?:<h[1-6]>.*?</h[1-6]>)+)</div>', merge_h_tags, md)

        md = re.sub(r'<br\s*/?>', '\n', md)
        md = re.sub(r'<p>(.*?)</p>', r'\1\n\n', md)
        md = re.sub(r'<h1>(.*?)</h1>', r'# \1\n', md)
        md = re.sub(r'<h2>(.*?)</h2>', r'## \1\n', md)
        md = re.sub(r'<h3>(.*?)</h3>', r'### \1\n', md)
        md = re.sub(r'<h4>(.*?)</h4>', r'#### \1\n', md)
        md = re.sub(r'<div>(.*?)</div>', r'\1\n', md)
        md = re.sub(r'<img[^>]*src="([^"]*)"[^>]*>', r'![]( \1)', md)
        md = re.sub(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', r'[\2](\1)', md)
        md = re.sub(r'<li>(.*?)</li>', r'- \1\n', md)
        md = re.sub(r'<[^>]+>', '', md)
        md = re.sub(r'&\n', '', md)
        md = re.sub(r'&lt;', '<', md)
        md = re.sub(r'&gt;', '>', md)
        md = re.sub(r'&amp;', '&', md)
        md = re.sub(r'&nbsp;', ' ', md)
        md = re.sub(r'\n{3,}', '\n\n', md)
        md = md.strip()

        return md

    def export_note_to_markdown(self, note_name: str) -> str:
        """导出单篇文章为 Markdown 格式

        @param note_name: 文章名称
        @type  note_name: str
        @return: 导出后的文件路径
        @rtype:  str
        @raises: Exception 导出失败时抛出异常
        """
        content = self._get_note_content(note_name)
        if content is None:
            raise ValueError(f"未找到文章: {note_name}")

        safe_name = self._sanitize_filename(note_name)
        output_path = self.output_dir / f"{safe_name}.md"

        markdown_content = self._html_to_markdown(content)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        return str(output_path)

    def export_note_to_pdf(self, note_name: str) -> str:
        """导出单篇文章为 PDF 格式

        @param note_name: 文章名称
        @type  note_name: str
        @return: 导出后的文件路径
        @rtype:  str
        @raises: Exception 导出失败时抛出异常
        """
        content = self._get_note_content(note_name)
        if content is None:
            raise ValueError(f"未找到文章: {note_name}")

        safe_name = self._sanitize_filename(note_name)
        pdf_path = self.output_dir / f"{safe_name}.pdf"

        self._export_note_to_pdf_via_notes(note_name, pdf_path)
        return str(pdf_path)

    def _sanitize_note_name(self, note_name: str) -> str:
        """清理文章名称中的多余空白和特殊字符

        用于解决备忘录中文章名称与搜索时输入的名称格式不完全匹配的问题。
        例如：多余的空格、特殊空白字符等。

        @param note_name: 原始文章名称
        @type  note_name: str
        @return: 清理后的文章名称
        @rtype:  str
        """
        import re
        # 移除多余空白字符（保留单个空格）
        note_name = re.sub(r'\s+', ' ', note_name)
        # 移除首尾空白
        note_name = note_name.strip()
        return note_name

    def _normalize_for_matching(self, note_name: str) -> str:
        """标准化文章名称用于匹配搜索

        移除所有空白字符并转为小写，用于模糊匹配。

        @param note_name: 原始文章名称
        @type  note_name: str
        @return: 标准化后的名称
        @rtype:  str
        """
        import re
        # 移除所有空白字符并转为小写
        return re.sub(r'\s+', '', note_name).lower()

    def _find_note_by_fuzzy_match(self, note_name: str) -> Optional[str]:
        """通过模糊匹配查找备忘录文章

        当精确匹配失败时，使用标准化后的名称进行模糊匹配。

        @param note_name: 文章名称
        @type  note_name: str
        @return: 匹配到的实际文章名称，匹配失败时返回 None
        @rtype:  Optional[str]
        """
        script = '''
        tell application "Notes"
            set allNotes to every note
            return name of allNotes
        end tell
        '''

        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=60
            )
            all_names = result.stdout.strip()
            if not all_names or all_names == "{}":
                return None

            target_normalized = self._normalize_for_matching(note_name)

            # 遍历所有文章名称进行模糊匹配
            for name in all_names.split(","):
                name = name.strip()
                if self._normalize_for_matching(name) == target_normalized:
                    return name

            return None
        except Exception:
            return None

    def _get_note_content(self, note_name: str) -> Optional[str]:
        """通过 AppleScript 获取备忘录文章内容

        @param note_name: 文章名称
        @type  note_name: str
        @return: 文章内容，文章不存在时返回 None
        @rtype:  Optional[str]
        """
        # 先尝试清理后的精确名称
        sanitized_name = self._sanitize_note_name(note_name)

        script = f'''
        tell application "Notes"
            set theNote to first note whose name is "{sanitized_name}"
            if exists theNote then
                return body of theNote
            else
                return "NOTE_NOT_FOUND"
            end if
        end tell
        '''

        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=30
            )
            content = result.stdout.strip()

            if content == "NOTE_NOT_FOUND":
                # 尝试模糊匹配
                matched_name = self._find_note_by_fuzzy_match(note_name)
                if matched_name:
                    return self._get_note_content(matched_name)
                return None
            return content
        except Exception:
            # 尝试模糊匹配作为最后的备选方案
            matched_name = self._find_note_by_fuzzy_match(note_name)
            if matched_name:
                return self._get_note_content(matched_name)
            return None

    def get_notes_by_tag_or_folder(self, tag_or_folder: str) -> list[str]:
        """通过 AppleScript 获取指定标签或文件夹下的所有文章名称

        @param tag_or_folder: 标签或文件夹名称
        @type  tag_or_folder: str
        @return: 文章名称列表
        @rtype:  list[str]
        """
        script = f'''
        tell application "Notes"
            try
                set targetFolder to folder "{tag_or_folder}"
                return name of every note of targetFolder
            on error
                set noteList to every note
                set matchingNotes to {{}}
                repeat with eachNote in noteList
                    try
                        set noteTags to tags of eachNote
                        if noteTags contains "{tag_or_folder}" then
                            set end of matchingNotes to name of eachNote
                        end if
                    end try
                end repeat
                return matchingNotes as string
            end try
        end tell
        '''

        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=60
            )
            output = result.stdout.strip()

            if not output or output == "{}":
                return []
            return [name.strip() for name in output.split(",")]
        except Exception:
            return []

    def _export_note_to_pdf_via_notes(self, note_name: str, output_path: Path) -> str:
        """通过备忘录 App 导出 PDF

        @param note_name: 文章名称
        @type  note_name: str
        @param output_path: 输出文件路径
        @type  output_path: Path
        @return: 生成的 PDF 文件路径
        @rtype:  str
        @raises: Exception 导出失败时抛出异常
        """
        desktop_path = Path.home() / "Desktop" / output_path.name

        script = f'''
        tell application "Notes"
            activate
            set theNote to first note whose name is "{note_name}"
            show theNote
            delay 0.5
        end tell

        tell application "System Events"
            tell process "Notes"
                set frontmost to true
                tell menu 1 of menu bar item "文件" of menu bar 1
                    click menu item "导出为"
                end tell
            end tell
        end tell
        delay 0.3
        tell application "System Events"
            tell process "Notes"
                tell menu 1 of menu bar item "文件" of menu bar 1
                    tell menu of menu item "导出为"
                        click menu item "PDF"
                    end tell
                end tell
            end tell
        end tell
        delay 0.5
        tell application "System Events"
            keystroke return
        end tell
        delay 0.5
        '''

        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.stderr and "not allow" in result.stderr.lower():
                raise RuntimeError("需要辅助访问权限，请在系统设置 > 隐私与安全性 > 辅助功能 中授权")

            import time
            time.sleep(1)

            if desktop_path.exists():
                shutil.move(str(desktop_path), str(output_path))
                return str(output_path)

            if output_path.exists():
                return str(output_path)

            raise RuntimeError("PDF 导出失败，文件未生成")

        except subprocess.TimeoutExpired:
            raise RuntimeError("PDF 导出超时")
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"PDF 导出失败: {e}")

    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名中的非法字符

        @param filename: 原始文件名
        @type  filename: str
        @return: 清理后的文件名
        @rtype:  str
        """
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, "_")
        return filename.strip()


FORMAT = "%(asctime)s [%(levelname)s] %(funcName)s:%(lineno)d %(message)s"


def setup_logging(log_file: str = None) -> logging.Logger:
    """配置日志系统

    @param log_file: 日志文件路径，默认保存在项目根目录的 logs 目录
    @type  log_file: str
    @return: 配置好的日志记录器
    @rtype:  logging.Logger
    """
    logger = logging.getLogger("doc_exporter")
    logger.setLevel(logging.INFO)

    if log_file is None:
        # 基于脚本文件位置计算路径，logs 目录与 skills 目录平级
        script_path = Path(__file__)
        # .claude/skills/exporting-doc/scripts/ -> .claude/skills/
        logs_dir = script_path.parents[2] / "logs"
        log_file = logs_dir / "doc_exporter.log"

    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
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
    @raises: ValueError 文章名称和标签都未输入时抛出异常
    """
    if not args.names and not args.tag:
        raise ValueError("错误: 文章名称和标签至少需要输入一个")


def parse_arguments() -> argparse.Namespace:
    """解析命令行参数

    @return: 解析后的命令行参数对象
    @rtype:  argparse.Namespace
    """
    parser = argparse.ArgumentParser(
        description="MAC OS 备忘录导出工具 - 将备忘录文章导出为本地文件"
    )

    parser.add_argument(
        "-n", "--names",
        type=str,
        help="要导出的备忘录文章名称，多个名称用逗号分隔"
    )

    parser.add_argument(
        "-t", "--tag",
        type=str,
        help="文章标签，用于筛选指定标签下的文章"
    )

    parser.add_argument(
        "-f", "--format",
        choices=["md", "pdf"],
        default="md",
        help="导出文件格式: md (Markdown) 或 pdf, 默认: md"
    )

    parser.add_argument(
        "-d", "--dir",
        default="",
        help="导出文件存放目录, 默认: 当前项目目录下的tmp目录中"
    )

    parser.add_argument(
        "-l", "--log",
        default=None,
        help="日志文件路径, 默认: 项目根目录下的 logs/doc_exporter.log"
    )

    return parser.parse_args()


def parse_doc_names(names_str: str) -> list[str]:
    """解析文章名称字符串

    @param names_str: 逗号分隔的文章名称字符串
    @type  names_str: str
    @return: 文章名称列表
    @rtype:  list[str]
    """
    if not names_str:
        return []
    return [name.strip() for name in names_str.split(",") if name.strip()]


def export_single_note(
    exporter: NotesExporter,
    note_name: str,
    export_format: ExportFormat,
    logger: logging.Logger,
    current: int,
    total: int
) -> tuple[Optional[str], Optional[dict]]:
    """导出单个备忘录文章

    @param exporter: 备忘录导出器实例
    @type  exporter: NotesExporter
    @param note_name: 文章名称
    @type  note_name: str
    @param export_format: 导出格式
    @type  export_format: ExportFormat
    @param logger: 日志记录器
    @type  logger: logging.Logger
    @param current: 当前进度序号
    @type  current: int
    @param total: 总数
    @type  total: int
    @return: 成功时返回 (文件路径, None)，失败时返回 (None, 错误信息字典)
    @rtype:  tuple[Optional[str], Optional[dict]]
    """
    print(f"\n[{current}/{total}] 正在导出: {note_name}")

    log_json(logger, "info", {
        "event": "export_start",
        "note_name": note_name,
        "format": export_format.value,
        "progress": f"{current}/{total}"
    })

    try:
        if export_format == ExportFormat.MARKDOWN:
            result_path = exporter.export_note_to_markdown(note_name)
        else:
            result_path = exporter.export_note_to_pdf(note_name)

        print(f"[{current}/{total}] 完成: {note_name}")

        log_json(logger, "info", {
            "event": "export_complete",
            "note_name": note_name,
            "output_path": result_path,
            "progress": f"{current}/{total}"
        })
        return result_path, None

    except Exception as e:
        print(f"[{current}/{total}] 失败: {note_name} - {e}")

        error_info = {
            "event": "export_failed",
            "note_name": note_name,
            "error": str(e),
            "progress": f"{current}/{total}"
        }
        log_json(logger, "error", error_info)
        return None, {note_name: str(e)}


def export_all_notes(
    doc_names: list[str],
    export_format: ExportFormat,
    output_dir: str,
    logger: logging.Logger
) -> ExportResult:
    """串行导出所有指定的备忘录文章

    @param doc_names: 要导出的文章名称列表
    @type  doc_names: list[str]
    @param export_format: 导出格式
    @type  export_format: ExportFormat
    @param output_dir: 输出目录
    @type  output_dir: str
    @param logger: 日志记录器
    @type  logger: logging.Logger
    @return: 导出结果统计
    @rtype:  ExportResult
    """
    exporter = NotesExporter(output_dir)
    total = len(doc_names)

    log_json(logger, "info", {
        "event": "export_batch_start",
        "total_notes": total,
        "format": export_format.value,
        "output_dir": output_dir
    })

    print(f"\n{'=' * 50}")
    print(f"开始导出 {total} 篇文章")
    print(f"{'=' * 50}")

    exported_docs = []
    failed_docs = []

    for i, note_name in enumerate(doc_names, 1):
        result_path, error = export_single_note(
            exporter, note_name, export_format, logger, i, total
        )
        if result_path:
            exported_docs.append(note_name)
        if error:
            failed_docs.append(error)

    result = ExportResult(
        input={
            "doc_nums": total,
            "docs": doc_names,
            "dir": os.path.abspath(output_dir)
        },
        export={
            "doc_nums": len(exported_docs),
            "docs": exported_docs
        },
        failed={
            "doc_nums": len(failed_docs),
            "err_info": failed_docs
        }
    )

    log_json(logger, "info", {
        "event": "export_batch_complete",
        "result": {
            "input": result.input,
            "export": result.export,
            "failed": result.failed
        }
    })

    return result


def print_progress(result: ExportResult) -> None:
    """打印导出结果

    @param result: 导出结果
    @type  result: ExportResult
    """
    print(f"\n{'=' * 50}")
    print("导出完成")
    print(f"{'=' * 50}")

    print(f"\n总文章数: {result.input['doc_nums']}")
    print(f"成功导出: {result.export['doc_nums']}")
    print(f"导出失败: {result.failed['doc_nums']}")

    if result.export["docs"]:
        print(f"\n成功列表: {', '.join(result.export['docs'])}")

    if result.failed["err_info"]:
        print("\n失败详情:")
        for err in result.failed["err_info"]:
            for doc, reason in err.items():
                print(f"  - {doc}: {reason}")

    print("\n结果 JSON:")
    print(json.dumps({
        "input": result.input,
        "export": result.export,
        "failed": result.failed
    }, ensure_ascii=False, indent=2))


def main() -> int:
    """主入口函数

    @return: 程序退出码，0 表示成功，非 0 表示有错误
    @rtype:  int
    """
    try:
        args = parse_arguments()
        validate_arguments(args)

        if not args.dir:
            # 默认保存到与 skills 目录平级的 tmp 目录
            script_path = Path(__file__)
            args.dir = str(script_path.parents[2] / "tmp")

        logger = setup_logging(args.log)

        doc_names = parse_doc_names(args.names) if args.names else []
        tag_name = args.tag

        if tag_name and doc_names:
            log_json(logger, "info", {
                "event": "fetching_notes_by_tag_with_names",
                "tag": tag_name,
                "names": doc_names
            })
            exporter = NotesExporter(args.dir)
            all_tag_notes = exporter.get_notes_by_tag_or_folder(tag_name)
            doc_names = [n for n in doc_names if n in all_tag_notes]

            if not doc_names:
                log_json(logger, "warning", {
                    "event": "no_matching_notes",
                    "tag": tag_name,
                    "reason": "指定名称的文章不在该标签下"
                })
        elif tag_name:
            log_json(logger, "info", {
                "event": "fetching_notes_by_tag",
                "tag": tag_name
            })
            exporter = NotesExporter(args.dir)
            doc_names = exporter.get_notes_by_tag_or_folder(tag_name)
            log_json(logger, "info", {
                "event": "notes_fetched_by_tag",
                "tag": tag_name,
                "count": len(doc_names),
                "notes": doc_names
            })

        log_json(logger, "info", {
            "event": "script_start",
            "doc_names": doc_names,
            "tag": tag_name,
            "format": args.format,
            "output_dir": args.dir
        })

        if not doc_names:
            result = ExportResult(
                input={
                    "doc_nums": 0,
                    "docs": [],
                    "dir": os.path.abspath(args.dir)
                },
                export={
                    "doc_nums": 0,
                    "docs": []
                },
                failed={
                    "doc_nums": 0,
                    "err_info": []
                }
            )
            print_progress(result)
            return 0

        export_format = ExportFormat.MARKDOWN if args.format == "md" else ExportFormat.PDF

        result = export_all_notes(
            doc_names,
            export_format,
            args.dir,
            logger
        )

        print_progress(result)

        return 0 if result.failed["doc_nums"] == 0 else 1

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
