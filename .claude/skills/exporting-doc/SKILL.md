---
name: exporting-doc
description: 从 MAC OS 备忘录应用导出文章到本地文件中.支持导出 Markdown 和 PDF 格式。例如用户可能会说"帮我导出备忘录里标签为xxx的文章"、"把某篇备忘录文章保存为md文件"、"批量导出备忘录中的工作文档"、"将备忘录中带有xxx标签的文章导出为md文件"等场景时，应该使用此 skill 来完成操作.
即使用户没有明确说出"skill"或"导出"这个词，只要意图是从MAC OS 备忘录中保存文章，就应该触发此 skill。
metadata:
  author: lichen
  create_date: 2026-4-7
---

## 如何使用此 Skill

1. 脚本路径：`.claude/skills/exporting-doc/scripts/doc_exporter.py`（相对于项目根目录）
2. 调用示例：`python3 .claude/skills/exporting-doc/scripts/doc_exporter.py -t "标签名"`
3. 详细用法参考 `references/README.md` 中的「使用方法」章节

如果 skills 目录位置有变动，请相应调整路径。

---

## Input
用户需要提供需要导出的文章名称或是文章所带有的tag名称.用户可以一次性提供多篇文章的名称,也可以提供一个tag标签名来指定需要导出的多篇文章.

```关于所支持的参数描述请参考references/README.md中的“命令行参数“这一章节的描述```.

---

## Output

1. 导出的文章会存放在指定的目录中.默认存放在当前项目目录下的tmp目录中.

2. 功能执行完成后会返回给用户一份详细的导出结果.

```关于导出目录以及导出结果的详情请参考references/README.md中的”输出示例“和”命令行参数“这些章节的描述```.

---

## 注意事项

1. **辅助功能权限**：导出 PDF 功能需要 macOS 辅助功能权限，请在 `系统设置 > 隐私与安全性 > 辅助功能` 中授权。
2. **参数要求**：`--names` 和 `--tag` 至少需要指定一个。
3. **PDF 导出**：PDF 导出使用备忘录应用的原生导出功能，会临时在桌面生成文件后移动到目标目录。

---

## 兼容性

- 仅支持 macOS（需要 AppleScript 访问备忘录应用）
- Python 3.x

## 依赖

- 无需安装第三方库，使用 macOS 内置 Python