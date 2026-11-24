# Contributing

感谢你考虑为 AutoDocUpdater 做贡献。

## Before You Start

- 先搜索现有 Issue，避免重复工作。
- 较大的功能或行为变更请先开 Issue 讨论范围和兼容性。
- 不要在 Issue、PR、提交或测试代码中放入真实 API Key、Cookie 或文章隐私内容。

## Development Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

需要 macOS 备忘录、Chrome 或 LLM Provider 的验证，请在 Issue/PR 中说明实际验证环境。

## Code Style

- 路径优先从脚本位置或项目根目录派生，避免依赖启动目录。
- 不要硬编码用户主目录、API Key 或 Cookie。
- 新增文件读写操作时，明确失败处理和清理逻辑。
- 日志中不得记录密钥、Authorization、Cookie 或完整环境变量。
- 保持现有 JSON 日志事件和结构化结果格式一致。

## Verification

至少执行 Python 语法检查：

```bash
python3 -m compileall -q .agents
```

涉及备忘录导出、LLM 调用或 51CTO 上传的变更，应在 PR 中记录手工验证步骤、环境限制和结果。不要为了测试向真实博客发布未经确认的文章。

## Pull Requests

PR 描述请包含：

- 变更目的和用户影响
- 主要修改文件
- 验证命令和结果
- 是否涉及密钥、登录态、日志或文件删除
- 已知限制和后续工作

提交前请确认：

- [ ] 没有提交 `.env`、`.mcp.json`、Chrome Profile、日志或临时文章
- [ ] 没有新增明文密钥、Cookie 或个人敏感信息
- [ ] Python 语法检查通过
- [ ] 相关文档已更新
- [ ] 变更范围保持聚焦

## Security

安全问题不要通过公开 Issue 报告，请遵循 [`SECURITY.md`](SECURITY.md)。
