# MAC OS 备忘录导出工具

从 MAC OS 备忘录应用导出文章到本地文件，支持 Markdown 和 PDF 格式。

## 功能特性

- 导出备忘录文章为 Markdown 或 PDF 格式
- 支持按文章名称筛选（多个名称用逗号分隔）
- 支持按标签/文件夹筛选
- 命令行参数灵活配置
- JSON 格式日志记录
- 详细的导出结果统计

## 安装

无需安装，直接使用脚本路径调用。

## 使用方法

### 基本用法

```bash
# 导出单篇文章（Markdown 格式）
python3 .agents/skills/exporting-doc/scripts/doc_exporter.py -n "文章标题"

# 导出多篇文章
python3 .agents/skills/exporting-doc/scripts/doc_exporter.py -n "文章1,文章2,文章3"

# 按标签导出
python3 .agents/skills/exporting-doc/scripts/doc_exporter.py -t "工作"

# 导出为 PDF 格式
python3 .agents/skills/exporting-doc/scripts/doc_exporter.py -n "文章标题" -f pdf
```

### 命令行参数

| 参数 | 说明 |
|------|------|
| `-n, --names` | 要导出的备忘录文章名称，多个名称用逗号分隔 |
| `-t, --tag` | 文章标签，用于筛选指定标签下的文章 |
| `-f, --format` | 导出格式：`md`（默认）或 `pdf` |
| `-d, --dir` | 导出文件存放目录，默认：当前项目目录下的tmp目录中 |
| `-l, --log` | 日志文件路径，默认：当前项目目录下的logs目录中 |

### 参数组合

```bash
# 同时指定文章名称和标签：导出该标签下匹配名称的文章
python3 .agents/skills/exporting-doc/scripts/doc_exporter.py -n "文章1,文章2" -t "工作"

# 只指定标签：导出该标签下的所有文章
python3 .agents/skills/exporting-doc/scripts/doc_exporter.py -t "工作"
```

## 输出示例

```
==================================================
开始导出 2 篇文章
==================================================

[1/2] 正在导出: 文章1
[1/2] 完成: 文章1
[2/2] 正在导出: 文章2
[2/2] 失败: 文章2 - 未找到文章

==================================================
导出完成
==================================================

总文章数: 2
成功导出: 1
导出失败: 1

成功列表: 文章1

失败详情:
  - 文章2: 未找到文章

结果 JSON:
{
  "input": {
    "doc_nums": 2,
    "docs": ["文章1", "文章2"],
    "dir": "/path/to/output"
  },
  "export": {
    "doc_nums": 1,
    "docs": ["文章1"]
  },
  "failed": {
    "doc_nums": 1,
    "err_info": [
      {"文章2": "未找到文章"}
    ]
  }
}
```

## 日志

日志默认保存在 `logs/doc_exporter.log`，每条日志为 JSON 格式：

```json
{
  "timestamp": "2026-04-03T10:30:00.123456",
  "level": "info",
  "event": "export_complete",
  "note_name": "文章标题",
  "output_path": "/path/to/article.md",
  "progress": "1/5"
}
```

## 注意事项

1. **辅助功能权限**：导出 PDF 功能需要 macOS 辅助功能权限，请在 `系统设置 > 隐私与安全性 > 辅助功能` 中授权。
2. **参数要求**：`--names` 和 `--tag` 至少需要指定一个。
3. **PDF 导出**：PDF 导出使用备忘录应用的原生导出功能。程序最多等待 10 秒检测“保存”面板，就绪后自动保存，再移动到目标目录；桌面已存在同名 PDF 时会安全拒绝，不会自动覆盖。保存失败会关闭残留面板并报告原因。

## 查询可靠性

- 标签/文件夹查询最多等待 120 秒，超时会返回明确的查询超时错误。
- 按名称读取正文时不再扫描全部备忘录。
- 名称包含特殊字符时会进行 AppleScript 字符串转义。
- 模糊匹配只查询名称包含目标文本的笔记，不再拉取全部笔记名称。
- 多个模糊匹配结果中没有标准化精确匹配时，不会随意选择文章。
- AppleScript 返回非零状态时记录 stderr，并区分“查询失败”和“文章不存在”。
- AppleScript 通过临时脚本文件执行，避免多行脚本参数引号问题。
- `hiservices-xpcservice` 连接失效等瞬时传输错误会进行一次底层重试，导出业务层仍不重试。
- 导出开始前会执行 Notes 健康检查，确认 AppleScript 通信正常。
- 使用 `tmp/notes_exporter.lock` 获取跨进程锁；已有导出任务运行时不会并发访问 Notes，而是明确报错退出。

## License

MIT
