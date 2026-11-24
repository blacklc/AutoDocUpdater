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
# 在项目根目录执行
pip install -r requirements.txt
```

## Chrome Driver

项目不再内置 ChromeDriver，统一由 Selenium Manager 自动检测本地 Chrome 版本，并从缓存或网络获取兼容的 driver。

- 默认缓存目录：`~/.cache/selenium/`
- 首次运行需要网络，网络超时限制为 120 秒
- 缓存命中后可直接离线使用
- 不再需要手动下载或维护 ChromeDriver

## 使用方法

```bash
# 上传单个文件
python3 .agents/skills/uploading-2-51cto/scripts/51cto_uploader.py /path/to/article.md

# 上传整个目录
python3 .agents/skills/uploading-2-51cto/scripts/51cto_uploader.py /path/to/articles/

# 用户确认后重传保留文件
python3 .agents/skills/uploading-2-51cto/scripts/51cto_uploader.py --retry-manifest

# 用户拒绝重传后删除保留文件
python3 .agents/skills/uploading-2-51cto/scripts/51cto_uploader.py --discard-manifest
```

## 命令行参数

| 参数 | 说明 |
|------|------|
| `path` | 要上传的 Markdown 文件路径或目录路径 |
| `--retry-manifest [PATH]` | 重传保留文件，默认读取 `tmp/51cto_retry.json` |
| `--discard-manifest [PATH]` | 删除保留文件，默认读取 `tmp/51cto_retry.json` |
| `--max-retries N` | 即时重试次数，默认 `1` |
| `-l, --log` | 日志文件路径，默认保存到项目根目录的 `logs/` 目录 |

## 操作流程

1. 程序会提示登录 51CTO 博客
2. 请在浏览器中完成登录操作（如已登录可跳过）
3. 程序自动检查登录状态，最多等待 60 秒
4. 自动逐个上传 Markdown 文件
5. 最终提交前发生瞬时失败时自动即时重试一次
6. 重试耗尽后暂时保留文件并写入重试清单
7. 上传完成后显示结果汇总

## 即时重试与用户确认

- 默认即时重试 `1` 次，单篇最多自动尝试 `2` 次。
- 只有最终发布前的可恢复失败才自动重试。
- 最终发布后状态未知时禁止自动重试，避免重复发布。
- 即时重试失败后，文件暂时保留，路径、原因、尝试次数和最终 URL 写入 `tmp/51cto_retry.json`。
- Skill/Agent 必须向用户说明失败原因，并询问是否重传。
- 用户同意时执行 `--retry-manifest`；重传仍失败时继续保留并再次询问。
- 用户拒绝时执行 `--discard-manifest` 删除保留文件。
- 用户未回复时不得删除。

## 违禁词弹窗与分类选择

- 点击“发布文章”后轮询检测违禁词弹窗或分类区域。
- 分类区域已经可用时立即继续，不再固定等待 5 秒。
- 检测到弹窗时点击“继续发布”，并等待弹窗关闭。
- 弹窗存在但无法继续发布时，本次上传判定失败并进入即时重试流程。
- 文章分类优先按文本“代码人生”定位。
- 文本定位失败时才使用旧的固定 XPath 兜底，并记录警告日志。

## 项目结构

```
uploading-2-51cto/
├── SKILL.md
├── scripts/
│   └── 51cto_uploader.py     # 主程序
├── references/
│   └── README.md             # 详细使用文档
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
| `stale_browser_lock_removed` | 无活动 Chrome 时清理了陈旧 Profile 锁文件 |
| `selenium_cache_not_writable` | Selenium 缓存不可写，但可尝试使用已有缓存 |
| `login_verified` | 登录验证成功 |
| `login_required` | 登录会话不存在或已过期，需要用户登录 |
| `login_state_ambiguous` | 页面状态不明确，准备刷新后重试 |
| `manual_login_completed` | 检测到用户已离开登录页 |
| `login_failed` | 登录失败，包含原因代码和详细信息 |
| `publish_clicked` | 点击发布按钮 |
| `upload_retry_scheduled` | 最终提交前失败，安排即时重试 |
| `publish_success` | 连续检测到可见的成功或审核中提示 |
| `publish_result_unknown` | 超时后仍未检测到明确结果 |
| `upload_retained_for_user` | 即时重试失败，文件暂时保留 |
| `retry_manifest_read_failed` | 重试清单读取失败 |
| `retry_files_missing` | 重试清单中的文件已不存在 |
| `retained_file_delete_failed` | 用户拒绝重传后删除文件失败 |
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
  - etcd设计思想: 等待 30 秒后仍未检测到明确的成功或失败提示。

暂时保留的文件:
  - etcd设计思想
    路径: /path/to/etcd设计思想.md
    尝试次数: 2
    失败阶段: verify_result
    原因: 等待 30 秒后仍未检测到明确的成功或失败提示。

重试清单: /path/to/tmp/51cto_retry.json
请向用户确认是否重传这些文件；用户拒绝后再删除保留文件。

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
检测到登录完成，正在验证发布页...
检测到登录成功！
```

登录失败时会输出具体原因，例如：

```
登录失败：登录超时
原因：等待 60 秒后仍停留在 51CTO 登录页；登录会话不存在或已过期，且未检测到登录完成。
当前页面：https://home.51cto.com/index
页面标题：51CTO技术家园
检测耗时：66.5 秒
处理结果：未加载、未上传、未删除任何文章。
建议：请保持浏览器窗口打开，并在 60 秒内完成登录、验证码或安全验证后重试。
```

## 页面用户登录状态实现原理

### 核心实现方式

通过 **Chrome 用户数据目录（User Data Dir）** 持久化 Cookie 来实现登录状态保持。

### 关键代码

```python
# 使用专门为 Selenium 创建的独立 Chrome 用户数据目录
selenium_profile_dir = str(_SELENIUM_PROFILE_DIR)
options.add_argument(f"--user-data-dir={selenium_profile_dir}")
```

平台默认路径：

| 平台 | SeleniumProfile 路径 |
|------|----------------------|
| macOS | `~/Library/Application Support/Google/Chrome/SeleniumProfile` |
| Windows | `%LOCALAPPDATA%\Google\Chrome\SeleniumProfile` |
| Linux | `$XDG_CONFIG_HOME/google-chrome/SeleniumProfile` 或 `~/.config/google-chrome/SeleniumProfile` |

启动 Chrome 前会执行以下检查：

- 确认 SeleniumProfile 目录可写。
- 检查是否存在活动 Chrome 进程占用该 Profile。
- 无活动进程时清理陈旧的 `DevToolsActivePort`、`SingletonLock`、`SingletonSocket` 和 `SingletonCookie`。
- Selenium 缓存不可写时记录警告；已有缓存 driver 仍可继续使用。
- 权限不足时返回 `browser_permission_required`，不会误报为用户未登录。

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

登录检测以发布页是否真实可用作为唯一成功标准：

1. 打开 `https://blog.51cto.com/blogger/publish`
2. 等待页面进入两种确定状态之一：
   - 发布页：URL 严格匹配发布页，且标题输入框 `#title` 可见
   - 登录页：跳转到 `home.51cto.com` 等登录地址
3. 发布页状态需要连续两次检查通过，避免只检测到短暂中间页面
4. 不再仅凭 URL 判断为已登录
5. 不再依赖 `a.want-write` 元素判断登录状态
6. 状态不明确时刷新页面并重新检测一次

如果检测到登录页，程序会提示用户手动登录并最多等待 60 秒。登录完成后会重新打开发布页，再次连续确认标题输入框可见，才会继续上传。

### 登录失败原因

程序会记录并反馈可确认的具体原因：

| 原因代码 | 用户反馈 |
|----------|----------|
| `session_missing_or_expired` | 检测到当前没有有效登录会话，提示用户登录 |
| `login_timeout` | 60 秒后仍停留在登录页，登录会话不存在、已过期或未完成登录 |
| `login_rejected` | 登录页明确提示密码错误、账号不存在、账号锁定、登录失败等 |
| `login_captcha_required` | 需要完成验证码、人机验证或安全验证 |
| `session_not_established` | 已离开登录页，但重新打开发布页后仍未建立有效会话 |
| `publish_page_unavailable` | 已进入发布页 URL，但标题输入框不可见 |
| `unexpected_redirect` | 跳转到 51CTO 登录页和发布页之外的未知地址 |
| `browser_closed` | 等待登录期间浏览器窗口或 Selenium 会话失效 |
| `browser_start_failed` | Chrome、ChromeDriver 或 Selenium Manager 启动失败 |
| `browser_permission_required` | 当前进程无权限写入 SeleniumProfile 或 Selenium 缓存 |
| `profile_in_use` | SeleniumProfile 被其他 Chrome 或上传进程占用 |
| `page_load_failed` | 页面加载、网络或代理异常 |
| `unknown_login_state` | 无法确认具体原因，反馈实际 URL、页面标题和耗时 |

无法从页面获得明确证据时，程序不会猜测账号或密码问题，而是反馈观测状态。

登录失败会被视为独立异常，程序返回退出码 `1`。此时不会加载文章、不会上传、不会删除本地文件，关闭浏览器后立即结束。

### 流程图

```text
启动 Chrome
    ↓
打开 51CTO 发布页
    ↓
等待标题框或登录页稳定出现
    ├─ 发布页就绪 ───────────────────────┐
    └─ 跳转登录页                         │
          ↓                               │
      等待用户登录（最多 60 秒）             │
          ↓                               │
      重新打开发布页                       │
          ↓                               │
      连续确认标题输入框可见 ───────────────┤
                                          ↓
                                    继续上传流程
```

### 优势

- **独立隔离**：使用独立 Profile，不影响用户正常的 Chrome 浏览器
- **自动持久化**：无需额外保存/加载 Cookie 文件
- **简单可靠**：Chrome 原生 Cookie 管理机制

## 注意事项

- 首次运行需要网络下载兼容的 ChromeDriver，网络超时限制为 120 秒
- 上传前请先在浏览器中登录 51CTO 博客
- 程序检测到未登录状态时会终止运行并提示
- 批量上传时文件逐个加载，避免内存溢出
- 登录状态通过 Chrome 用户数据目录持久化
- 上传成功后删除本地文件；即时重试失败后暂时保留，由用户决定重传或删除

## License

MIT
