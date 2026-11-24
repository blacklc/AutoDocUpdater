---
name: exporting-doc
description: 从 MAC OS 备忘录应用导出文章到本地文件中.支持导出 Markdown 和 PDF 格式。例如用户可能会说"帮我导出备忘录里标签为xxx的文章"、"把某篇备忘录文章保存为md文件"、"批量导出备忘录中的工作文档"、"将备忘录中带有xxx标签的文章导出为md文件"等场景时，应该使用此 skill 来完成操作.
即使用户没有明确说出"skill"或"导出"这个词，只要意图是从MAC OS 备忘录中保存文章，就应该触发此 skill。
metadata:
  author: lichen
  create_date: 2026-4-7
---

## 如何使用此 Skill

1. 脚本路径：`.agents/skills/exporting-doc/scripts/doc_exporter.py`（相对于项目根目录）
2. 调用示例：`python3 .agents/skills/exporting-doc/scripts/doc_exporter.py -t "标签名"`
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
3. **PDF 导出**：PDF 导出会等待“保存”面板就绪，使用默认文章标题作为文件名自动保存，再移动到目标目录。桌面上已有同名 PDF 时会安全拒绝，不会自动覆盖；保存失败会关闭残留面板并报告原因。
4. **查询超时**：标签/文件夹查询最多等待 120 秒；超时、AppleScript 失败和文章不存在会返回不同错误，不会把查询失败误报为“未找到文章”。
5. **AppleScript 传输稳定性**：脚本通过临时文件执行 AppleScript，并对 `hiservices-xpcservice` 连接失效等瞬时错误进行一次底层重试；导出业务层仍保持不重试。
6. **禁止并发**：导出进程会获取 `tmp/notes_exporter.lock` 全局锁，并在访问备忘录前执行健康检查。已有其他导出任务运行时，新任务会明确报错退出，避免多个 AppleScript 任务并发导致 XPC 通信异常。

---

## 兼容性

- 仅支持 macOS（需要 AppleScript 访问备忘录应用）
- Python 3.x

## 依赖

- 无需安装第三方库，使用 macOS 内置 Python
