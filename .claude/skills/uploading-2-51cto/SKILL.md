---
name: uploading-2-51cto
description: |
  将本地 Markdown 文件批量上传发布到 51CTO 博客平台。使用 Selenium 自动化浏览器操作，支持单个文件或整个目录批量上传，自动检测登录状态。
  当用户提到"上传到51cto"、"发布到51cto"、"51cto博客上传"、"批量上传博客"、"把md文件发布到51cto"或类似表达时，务必使用此 skill。
  即使用户没有明确说"skill"或"上传"这个词，只要意图是将 Markdown 文章发布到 51CTO 博客，就应该触发此 skill。
metadata:
  author: lichen
  create_date: 2026-4-8
---

# 51CTO 博客上传 Skill

将本地 Markdown 文件批量发布到 51CTO 博客平台。

## 使用方式

### 命令行调用

```bash
python3 {skill_path}/scripts/51cto_uploader.py "/path/to/article.md"
```

## Input

用户需提供要上传的 Markdown 文件路径或包含多个 Markdown 文件的目录路径。

## Output

上传完成后返回结果汇总：

```
==================================================
上传结果汇总
==================================================
成功: X 篇
失败: X 篇

成功列表:
  - article_name_1
  - article_name_2

失败列表:
  - article_name: 失败原因

请访问 51CTO 博客用户中心查看:
https://blog.51cto.com/creative-center/manager
==================================================
```

详细输出示例和日志格式请参考 `references/README.md`。

## 操作流程

1. 程序会提示登录 51CTO 博客
2. 请在浏览器中完成登录操作（如已登录可跳过）
3. 程序自动检查登录状态，最多等待 60 秒
4. 自动逐个上传 Markdown 文件
5. 上传完成后显示结果汇总

## 兼容性

- **操作系统**：仅支持 macOS 和 Windows（需要 Chrome 浏览器）
- **Python**：Python 3.x
- **依赖**：selenium (`pip install selenium`)
- **浏览器**：Google Chrome + ChromeDriver

## 注意事项

- 请确保 Chrome driver 与 Chrome 浏览器版本匹配
- 上传前请先在浏览器中登录 51CTO 博客
- 程序检测到未登录状态时会终止运行并提示
- 批量上传时文件逐个加载，避免内存溢出
- 登录状态通过 Chrome 用户数据目录持久化
- 上传成功的文章会自动删除本地文件，节省存储空间；上传失败的文章会保留本地文件

详细文档和参数说明请参考 `references/README.md`。
