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

# 用户确认后重传保留文件
python3 {skill_path}/scripts/51cto_uploader.py --retry-manifest

# 用户拒绝重传后删除保留文件
python3 {skill_path}/scripts/51cto_uploader.py --discard-manifest
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

暂时保留的文件:
  - article_name
    路径: /path/to/article.md
    尝试次数: 2
    失败阶段: verify_result
    原因: 最终发布后未检测到明确结果

重试清单: /path/to/tmp/51cto_retry.json
请向用户确认是否重传这些文件；用户拒绝后再删除保留文件。

请访问 51CTO 博客用户中心查看:
https://blog.51cto.com/creative-center/manager
==================================================
```

详细输出示例和日志格式请参考 `references/README.md`。

## 操作流程

1. 程序会提示登录 51CTO 博客
2. 请在浏览器中完成登录操作（如已登录可跳过）
3. 程序通过发布页标题输入框严格确认登录状态，最多等待 60 秒
4. 自动逐个上传 Markdown 文件
5. 对最终提交前的瞬时失败自动重试一次
6. 即时重试后仍失败的文件暂时保留
7. 上传完成后显示结果汇总和重试清单

## 即时重试与用户确认机制

- 默认即时重试 `1` 次，单篇最多自动尝试 `2` 次。
- 只对最终提交前的可恢复失败执行即时重试。
- 已经点击最终发布但无法确认结果时，禁止自动重试，避免重复发布。
- 即时重试仍失败后，程序保留本地文件并写入 `tmp/51cto_retry.json`。
- Agent 必须向用户说明失败原因、尝试次数、失败阶段和保留文件路径。
- Agent 必须询问用户是否重传保留文件。
- 用户同意时执行 `--retry-manifest`。
- 用户拒绝时执行 `--discard-manifest` 删除保留文件。
- 用户未回复时不得删除文件。
- 用户确认重传后仍失败时，文件继续保留，并再次反馈和询问。
- Agent 不得自行使用 `input()` 或假设用户同意删除。

## 兼容性

- **操作系统**：仅支持 macOS 和 Windows（需要 Chrome 浏览器）
- **Python**：Python 3.x
- **依赖**：`pip install -r requirements.txt`
- **浏览器**：本地 Google Chrome；ChromeDriver 由 Selenium Manager 自动获取

## 注意事项

- 首次运行需要网络下载匹配的 ChromeDriver，网络超时限制为 120 秒
- 上传前请先在浏览器中登录 51CTO 博客
- 登录失败时会反馈具体原因，例如登录超时、密码错误、验证码、会话失效、浏览器关闭或发布页不可用
- 启动 Chrome 前会检查 SeleniumProfile 和 Selenium 缓存的写权限，并在无活动 Chrome 时清理陈旧 `DevToolsActivePort`/Singleton 锁文件
- 在 Codex 沙箱中运行上传任务时，必须主动申请 SeleniumProfile 和 Selenium 缓存所在外部目录的写权限
- 权限不足会返回 `browser_permission_required`，不会误报为未登录或 Profile 被占用
- 程序检测到未登录状态时会终止运行并提示
- 批量上传时文件逐个加载，避免内存溢出
- 登录状态通过 Chrome 用户数据目录持久化
- 上传成功后会删除本地文件
- 即时重试失败后会暂时保留文件，必须由用户决定重传还是删除

详细文档和参数说明请参考 `references/README.md`。
