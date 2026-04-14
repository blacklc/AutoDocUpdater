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

已打包在 `drivers/chromedriver-mac-x64/` 目录（相对于 skill 根目录）。如需更新，请下载并替换：

- macOS: [ChromeDriver for Mac](https://chromedriver.chromium.org/downloads)
- Windows: [ChromeDriver for Windows](https://chromedriver.chromium.org/downloads)

**注意**：确保 Chrome driver 版本与本地安装的 Chrome 浏览器版本匹配。

## 使用方法

```bash
# 上传单个文件
python3 {skill_path}/scripts/51cto_uploader.py /path/to/article.md

# 上传整个目录
python3 {skill_path}/scripts/51cto_uploader.py /path/to/articles/
```

## 命令行参数

| 参数 | 说明 |
|------|------|
| `path` | 要上传的 Markdown 文件路径或目录路径（必填） |
| `-l, --log` | 日志文件路径，默认保存到 skill 目录所在目录的 logs 目录 |
| `--driver-dir` | Chrome driver 目录，默认 `drivers/chromedriver-mac-x64`（相对于 skill 根目录） |

## 操作流程

1. 程序会提示登录 51CTO 博客
2. 请在浏览器中完成登录操作（如已登录可跳过）
3. 程序自动检查登录状态，最多等待 60 秒
4. 自动逐个上传 Markdown 文件
5. 上传完成后显示结果汇总

## 项目结构

```
uploading-2-51cto/
├── SKILL.md
├── scripts/
│   └── 51cto_uploader.py     # 主程序
├── references/
│   └── README.md             # 详细使用文档
└── drivers/
    └── chromedriver-mac-x64/ # Chrome driver
        └── chromedriver      # 可执行文件
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

### 常见事件类型

| 事件 | 说明 |
|------|------|
| `upload_start` | 开始上传文件 |
| `file_loaded` | 文件加载成功 |
| `login_check_start` | 开始检查登录状态 |
| `login_verified` | 登录验证成功 |
| `not_logged_in` | 未检测到登录状态 |
| `publish_clicked` | 点击发布按钮 |
| `publish_success` | 发布成功 |
| `publish_failed` | 发布失败 |
| `batch_upload_complete` | 批量上传完成 |

## 输出示例

### 成功输出

```
==================================================
上传结果汇总
==================================================
成功: 3 篇
失败: 1 篇

成功列表:
  - etcd watch特性
  - etcd mvcc
  - etcd架构

失败列表:
  - etcd设计思想: 发布后未检测到成功提示

请访问 51CTO 博客用户中心查看:
https://blog.51cto.com/creative-center/manager
==================================================
```

### 登录提示

程序运行时显示：

```
==================================================
请事先在浏览器中完成 51CTO 博客的用户登陆操作
==================================================

请在浏览器中完成 51CTO 博客的登录操作...
等待登录完成（最多60秒）...
检测到登录成功！
```

## 页面用户登录状态实现原理

### 核心实现方式

通过 **Chrome 用户数据目录（User Data Dir）** 持久化 Cookie 来实现登录状态保持。

### 关键代码

```python
# 使用专门为 Selenium 创建的独立 Chrome 用户数据目录
selenium_profile_dir = os.path.expanduser(
    "~/Library/Application Support/Google/Chrome/SeleniumProfile"
)
options.add_argument(f"--user-data-dir={selenium_profile_dir}")
```

### 工作原理

1. **首次运行**：
   - 脚本使用一个独立于日常 Chrome 的用户数据目录 `SeleniumProfile`
   - 启动浏览器后，用户需手动登录 51CTO
   - 登录成功后，Chrome 自动将 Cookie 和 session 信息保存到该目录

2. **后续运行**：
   - 复用同一个用户数据目录
   - Chrome 启动时自动加载之前保存的 Cookie
   - 用户无需再次登录，可直接使用

### 登录检测机制

通过两种方式验证登录状态：

1. **URL 检测**：检查是否跳转到用户中心页面 `creative-center/manager`
2. **元素检测**：查找"写文章"按钮元素 `a.want-write`

### 流程图

```
┌─────────────────────────────────────────────┐
│  1. 启动 Chrome（使用 SeleniumProfile 目录） │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│  2. 访问 51CTO 管理页面                       │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│  3. 检查 URL / 元素 判断是否已登录             │
└─────────────────┬───────────────────────────┘
                  ↓
        ┌─────────┴─────────┐
        ↓                   ↓
   [未登录]            [已登录]
        ↓                   ↓
   等待用户手动登录     继续上传流程
   (最多60秒)              ↓
        ↓                   ↓
   检测登录成功 ────────────┘
```

### 优势

- **独立隔离**：使用独立 Profile，不影响用户正常的 Chrome 浏览器
- **自动持久化**：无需额外保存/加载 Cookie 文件
- **简单可靠**：Chrome 原生 Cookie 管理机制

## 注意事项

- 请确保 Chrome driver 与 Chrome 浏览器版本匹配
- 上传前请先在浏览器中登录 51CTO 博客
- 程序检测到未登录状态时会终止运行并提示
- 批量上传时文件逐个加载，避免内存溢出
- 登录状态通过 Chrome 用户数据目录持久化

## License

MIT
