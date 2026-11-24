#!/usr/bin/env python3
"""交互式配置 AutoDocUpdater LLM 环境变量"""

import getpass
import os
import sys
from pathlib import Path


_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from env_config import (
    ENV_API_BASE,
    ENV_API_KEY,
    ENV_AZURE_API_VERSION,
    ENV_AZURE_ENDPOINT,
    ENV_GOOGLE_LOCATION,
    ENV_GOOGLE_PROJECT_ID,
    ENV_MODEL,
    ENV_PROVIDER,
    SUPPORTED_PROVIDERS,
    get_user_env_file,
    load_base_config,
    write_environment,
)


def _prompt(label: str, default: str = "") -> str:
    """读取普通文本输入"""
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or default


def main() -> int:
    """运行交互式环境配置

    @return: 0 表示配置成功，2 表示输入或写入失败
    @rtype:  int
    """
    config = load_base_config()
    provider_default = os.getenv(ENV_PROVIDER) or str(config.get("provider", "litellm"))
    provider_config = config.get(provider_default, {})
    if not isinstance(provider_config, dict):
        provider_config = {}
    model_default = os.getenv(ENV_MODEL) or str(
        config.get("model", {}).get(provider_default, "")
    )
    api_base_default = os.getenv(ENV_API_BASE) or str(
        provider_config.get("api_base", "")
    )

    print("AutoDocUpdater LLM 环境配置")
    print("密钥输入不会回显，也不会写入命令历史或项目目录。")
    print()

    try:
        provider = _prompt("Provider", provider_default)
        if provider not in SUPPORTED_PROVIDERS:
            print(f"不支持的 Provider: {provider}", file=sys.stderr)
            print(f"可选值: {', '.join(sorted(SUPPORTED_PROVIDERS))}", file=sys.stderr)
            return 2

        model = _prompt("模型名称", model_default)
        if not model:
            print("模型名称不能为空", file=sys.stderr)
            return 2

        values = {
            ENV_PROVIDER: provider,
            ENV_MODEL: model,
        }

        if provider == "google_vertexai":
            project_id = _prompt(
                "Google Project ID",
                os.getenv(ENV_GOOGLE_PROJECT_ID)
                or str(provider_config.get("project_id", "")),
            )
            location = _prompt(
                "Google Location",
                os.getenv(ENV_GOOGLE_LOCATION)
                or str(provider_config.get("location", "us-central1")),
            )
            if not project_id:
                print("Google Project ID 不能为空", file=sys.stderr)
                return 2
            values[ENV_GOOGLE_PROJECT_ID] = project_id
            values[ENV_GOOGLE_LOCATION] = location
        else:
            api_base = _prompt("API Base", api_base_default)
            api_key = getpass.getpass("API Key（输入隐藏）: ")
            if not api_key:
                print("API Key 不能为空", file=sys.stderr)
                return 2
            values[ENV_API_KEY] = api_key
            if api_base:
                values[ENV_API_BASE] = api_base

            if provider == "azure_openai":
                endpoint = _prompt(
                    "Azure Endpoint",
                    os.getenv(ENV_AZURE_ENDPOINT)
                    or str(provider_config.get("azure_endpoint", "")),
                )
                api_version = _prompt(
                    "Azure API Version",
                    os.getenv(ENV_AZURE_API_VERSION)
                    or str(provider_config.get("api_version", "2024-02-01")),
                )
                if not endpoint:
                    print("Azure Endpoint 不能为空", file=sys.stderr)
                    return 2
                values[ENV_AZURE_ENDPOINT] = endpoint
                values[ENV_AZURE_API_VERSION] = api_version
    except (EOFError, KeyboardInterrupt):
        print("\n配置已取消", file=sys.stderr)
        return 2

    env_file = get_user_env_file()
    print()
    print(f"将写入环境文件: {env_file}")
    confirm = input("确认写入? [y/N]: ").strip().lower()
    if confirm not in {"y", "yes"}:
        print("配置已取消")
        return 2

    try:
        paths = write_environment(values)
    except Exception as exc:
        print(f"写入环境配置失败: {exc}", file=sys.stderr)
        return 2

    print("配置完成:")
    for name in sorted(values):
        print(f"  - {name}")
    print(f"环境文件: {paths['env_file']}")
    print(f"Shell 配置: {paths['shell_rc']}")
    print("后续运行会自动加载该环境文件。")
    print("如需在当前普通终端中立即使用，可执行:")
    print(f"  source {paths['env_file']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
