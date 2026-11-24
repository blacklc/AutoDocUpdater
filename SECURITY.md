# Security Policy

## Supported Versions

项目当前只维护 `main` 分支。安全修复会优先提交到 `main`，不承诺为旧版本提供长期补丁。

## Reporting a Vulnerability

请不要在公开 Issue 中发布以下内容：

- API Key、Bearer Token 或密码
- 51CTO Cookie、Chrome Profile 内容
- 包含个人信息的完整日志
- 可被直接利用的漏洞细节

请优先使用 GitHub 仓库的 Private vulnerability reporting 或 Security Advisory 私密报告。如果仓库尚未开启该功能，请通过维护者的 GitHub 联系方式私下联系，并先只提供最小必要信息。

## Sensitive Data

本项目可能在本机产生或使用以下敏感数据：

| 数据 | 默认位置 | 说明 |
|---|---|---|
| LLM API Key | `~/.config/autodoc/env` | 由 `configure_env.py` 写入，权限应为 `0600` |
| 51CTO 登录态 | Chrome `SeleniumProfile` | 位于仓库外，包含 Cookie |
| 导出与上传日志 | `logs/` | 可能包含文章标题、路径和结果 URL |
| 临时文章与重试清单 | `tmp/` | 可能包含待发布文章和失败信息 |

这些路径均不应被提交到 Git。若怀疑密钥或 Cookie 已经泄露，请立即轮换 API Key，并在 51CTO 中退出相关会话。

## Safe Usage

- 不要在 `conf/config.yaml` 中写入密钥。
- 不要在命令历史、Issue、PR 或聊天窗口中粘贴密钥。
- 不要在公开环境使用个人或生产账号做自动化测试。
- 运行上传脚本前确认 Chrome Profile 目录不可被其他用户读取。
- 发布文章前核对内容，避免将内部文档或个人数据发送到公开平台。

## Scope

安全报告重点包括但不限于：

- 命令执行或参数注入
- 密钥、Cookie 或日志泄露
- 文件删除、覆盖或路径穿越
- 登录态判断绕过
- 发布结果误判导致重复发布
