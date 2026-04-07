# 51CTO 博客批量上传工具

将本地 Markdown 文件批量发布到 51CTO 博客。

## 功能特性

- 支持单个 Markdown 文件上传
- 支持目录批量上传（逐个加载，避免内存溢出）
- 使用 Selenium 自动化操作浏览器（XPath 元素定位）
- 自动检测登录状态（支持 60 秒等待用户登录）
- Chrome 用户数据目录复用（登录状态持久化）
- 详细的日志记录
- 上传结果汇总报告

## 安装

```bash
pip install selenium
```

## Chrome Driver

下载 Chrome driver 并放置到 `51cto_uploader/drivers/chromedriver-mac-x64/` 目录：

- macOS: [ChromeDriver for Mac](https://chromedriver.chromium.org/downloads)
- Windows: [ChromeDriver for Windows](https://chromedriver.chromium.org/downloads)

确保 Chrome driver 版本与本地安装的 Chrome 浏览器版本匹配。

## 使用方法

```bash
# 上传单个文件
python -m 51cto_uploader.51cto_uploader /path/to/article.md

# 上传整个目录
python -m 51cto_uploader.51cto_uploader /path/to/articles/
```

## 命令行参数

| 参数 | 说明 |
|------|------|
| `path` | 要上传的 Markdown 文件路径或目录路径 |
| `-l, --log` | 日志文件路径，默认：`logs/51cto_uploader.log` |
| `--driver-dir` | Chrome driver 目录，默认：`51cto_uploader/drivers/chromedriver-mac-x64` |

## 操作流程

1. 程序会提示登录 51CTO 博客
2. 请在浏览器中完成登录操作（如已登录可跳过）
3. 程序自动检查登录状态，最多等待 60 秒
4. 自动逐个上传 Markdown 文件
5. 上传完成后显示结果汇总

## 项目结构

```
51cto_uploader/
├── __init__.py
├── 51cto_uploader.py     # 主程序
├── drivers/
│   └── chromedriver-mac-x64/   # Chrome driver 目录
└── README.md
```

## 日志

日志保存在 `logs/51cto_uploader.log`，JSON 格式：

```json
{
  "timestamp": "2026-04-07T14:00:15.585245",
  "level": "info",
  "event": "upload_start",
  "file": "etcd mvcc"
}
```

## 注意

- 请确保 Chrome driver 与 Chrome 浏览器版本匹配
- 上传前请先在浏览器中登录 51CTO 博客
- 程序检测到未登录状态时会终止运行并提示
- 批量上传时文件逐个加载，避免内存溢出
- 登录状态通过 Chrome 用户数据目录持久化

## License

MIT
