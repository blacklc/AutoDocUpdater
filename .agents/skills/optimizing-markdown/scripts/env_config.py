#!/usr/bin/env python3
"""LLM 环境变量配置与预检模块"""

import copy
import os
import re
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


_SKILL_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = _SKILL_ROOT / "conf" / "config.yaml"
ENV_FILE_NAME = "env"

ENV_PROVIDER = "AUTODOC_LLM_PROVIDER"
ENV_MODEL = "AUTODOC_LLM_MODEL"
ENV_API_BASE = "AUTODOC_LLM_API_BASE"
ENV_API_KEY = "AUTODOC_LLM_API_KEY"
ENV_AZURE_ENDPOINT = "AUTODOC_LLM_AZURE_ENDPOINT"
ENV_AZURE_API_VERSION = "AUTODOC_LLM_AZURE_API_VERSION"
ENV_GOOGLE_PROJECT_ID = "AUTODOC_LLM_GOOGLE_PROJECT_ID"
ENV_GOOGLE_LOCATION = "AUTODOC_LLM_GOOGLE_LOCATION"

SUPPORTED_PROVIDERS = {
    "openai",
    "anthropic",
    "azure_openai",
    "google_vertexai",
    "litellm",
}

_SOURCE_START = "# >>> AutoDocUpdater environment >>>"
_SOURCE_END = "# <<< AutoDocUpdater environment <<<"


@dataclass
class EnvironmentStatus:
    """LLM 环境预检结果"""

    configured: bool
    provider: str
    missing: list[str] = field(default_factory=list)
    instructions: list[str] = field(default_factory=list)
    config: dict = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict:
        """转换为可序列化结果，不包含密钥"""
        return {
            "configured": self.configured,
            "provider": self.provider,
            "missing": self.missing.copy(),
            "instructions": self.instructions.copy(),
        }


class EnvironmentConfigurationError(RuntimeError):
    """LLM 环境变量配置不完整异常"""

    def __init__(self, status: EnvironmentStatus):
        """初始化环境配置异常

        @param status: 环境预检结果
        @type  status: EnvironmentStatus
        """
        self.status = status
        super().__init__("LLM 环境变量配置不完整: " + ", ".join(status.missing))


def load_base_config(config_path: Path = CONFIG_PATH) -> dict:
    """加载非敏感基础配置

    @param config_path: 配置文件路径
    @type  config_path: Path
    @return: 配置字典
    @rtype:  dict
    @raises FileNotFoundError: 配置文件不存在时抛出
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def get_user_env_file(home: Optional[Path] = None) -> Path:
    """获取用户级环境文件路径

    @param home: 用户主目录，用于测试时覆盖
    @type  home: Optional[Path]
    @return: 环境文件路径
    @rtype:  Path
    """
    home_dir = Path(home) if home else Path.home()
    return home_dir / ".config" / "autodoc" / ENV_FILE_NAME


def load_user_environment(env_file: Optional[Path] = None) -> dict[str, str]:
    """加载用户级 AUTODOC 环境文件

    已存在的真实环境变量优先级更高，不会被文件覆盖。

    @param env_file: 环境文件路径，不提供时使用默认用户级路径
    @type  env_file: Optional[Path]
    @return: 从文件加载的变量
    @rtype:  dict[str, str]
    """
    path = Path(env_file) if env_file else get_user_env_file()
    if not path.exists():
        return {}

    loaded = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.startswith("export "):
            continue
        assignment = line[len("export "):]
        name, separator, value = assignment.partition("=")
        name = name.strip()
        if not separator or not name.startswith("AUTODOC_"):
            continue
        try:
            parts = shlex.split(value)
        except ValueError:
            continue
        if len(parts) != 1:
            continue
        os.environ.setdefault(name, parts[0])
        loaded[name] = parts[0]
    return loaded


def apply_environment_overrides(config: Optional[dict] = None) -> dict:
    """将环境变量合并到基础配置

    @param config: 基础配置，不提供时从默认配置文件读取
    @type  config: Optional[dict]
    @return: 已合并环境变量的配置
    @rtype:  dict
    """
    load_user_environment()
    merged = copy.deepcopy(config) if config is not None else load_base_config()

    for value in merged.values():
        if isinstance(value, dict):
            value.pop("api_key", None)

    provider = os.getenv(ENV_PROVIDER) or merged.get("provider", "openai")
    merged["provider"] = provider

    model_name = os.getenv(ENV_MODEL)
    if model_name:
        merged.setdefault("model", {})[provider] = model_name

    provider_config = merged.setdefault(provider, {})
    if not isinstance(provider_config, dict):
        provider_config = {}
        merged[provider] = provider_config

    api_key = os.getenv(ENV_API_KEY)
    if api_key:
        provider_config["api_key"] = api_key

    api_base = os.getenv(ENV_API_BASE)
    if api_base:
        provider_config["api_base"] = api_base

    if provider == "azure_openai":
        endpoint = os.getenv(ENV_AZURE_ENDPOINT)
        api_version = os.getenv(ENV_AZURE_API_VERSION)
        if endpoint:
            provider_config["azure_endpoint"] = endpoint
        if api_version:
            provider_config["api_version"] = api_version

    if provider == "google_vertexai":
        project_id = os.getenv(ENV_GOOGLE_PROJECT_ID)
        location = os.getenv(ENV_GOOGLE_LOCATION)
        if project_id:
            provider_config["project_id"] = project_id
        if location:
            provider_config["location"] = location

    return merged


def _build_instructions(missing: list[str]) -> list[str]:
    """构建环境配置引导信息"""
    configure_script = _SKILL_ROOT / "scripts" / "configure_env.py"
    if not missing:
        return []
    return [
        f"缺少环境变量: {', '.join(missing)}",
        f"运行交互式配置: python3 {configure_script}",
        "配置后重新运行本工具，程序会自动读取 ~/.config/autodoc/env",
        "可选: 在当前普通终端执行 source ~/.config/autodoc/env",
        "请勿在聊天窗口、日志或命令历史中粘贴密钥。",
    ]


def check_environment(config: Optional[dict] = None) -> EnvironmentStatus:
    """检查当前 Provider 所需的环境变量是否齐全

    @param config: 基础配置，不提供时从默认配置文件读取
    @type  config: Optional[dict]
    @return: 环境预检结果
    @rtype:  EnvironmentStatus
    """
    merged = apply_environment_overrides(config)
    provider = str(merged.get("provider", ""))
    provider_config = merged.get(provider, {})
    if not isinstance(provider_config, dict):
        provider_config = {}

    missing = []
    if provider not in SUPPORTED_PROVIDERS:
        missing.append(ENV_PROVIDER)
    else:
        if provider != "google_vertexai" and not provider_config.get("api_key"):
            missing.append(ENV_API_KEY)
        if provider == "litellm" and not provider_config.get("api_base"):
            missing.append(ENV_API_BASE)
        if provider == "azure_openai" and not provider_config.get("azure_endpoint"):
            missing.append(ENV_AZURE_ENDPOINT)
        if provider == "google_vertexai" and not provider_config.get("project_id"):
            missing.append(ENV_GOOGLE_PROJECT_ID)

    status = EnvironmentStatus(
        configured=not missing,
        provider=provider,
        missing=missing,
        instructions=_build_instructions(missing),
        config=merged,
    )
    return status


def format_environment_status(status: EnvironmentStatus) -> str:
    """格式化环境预检结果

    @param status: 环境预检结果
    @type  status: EnvironmentStatus
    @return: 用户可读文本
    @rtype:  str
    """
    lines = [
        "LLM 环境配置检查",
        f"Provider: {status.provider or '<unknown>'}",
        f"状态: {'已配置' if status.configured else '未配置完整'}",
    ]
    if status.missing:
        lines.append(f"缺失变量: {', '.join(status.missing)}")
    if status.instructions:
        lines.append("配置引导:")
        lines.extend(f"  {instruction}" for instruction in status.instructions)
    return "\n".join(lines)


def _detect_shell_rc(home: Path) -> Path:
    """检测当前 Shell 的启动配置文件"""
    shell_name = Path(os.getenv("SHELL", "")).name.lower()
    if "zsh" in shell_name:
        return home / ".zshrc"
    if "bash" in shell_name:
        if sys.platform == "darwin":
            return home / ".bash_profile"
        return home / ".bashrc"
    return home / ".profile"


def _source_block(env_file: Path) -> str:
    """构建 Shell 配置中的受管理引用区块"""
    quoted_path = shlex.quote(str(env_file))
    return (
        f"{_SOURCE_START}\n"
        f"if [ -f {quoted_path} ]; then\n"
        f"    . {quoted_path}\n"
        f"fi\n"
        f"{_SOURCE_END}\n"
    )


def write_environment(
    values: dict[str, str],
    home: Optional[Path] = None,
    shell_rc: Optional[Path] = None,
) -> dict[str, str]:
    """写入用户级环境文件和 Shell 引用区块

    @param values: 环境变量名称和值
    @type  values: dict[str, str]
    @param home: 用户主目录，用于测试时覆盖
    @type  home: Optional[Path]
    @param shell_rc: Shell 配置文件路径，用于测试时覆盖
    @type  shell_rc: Optional[Path]
    @return: 环境文件与 Shell 配置文件路径
    @rtype:  dict[str, str]
    @raises ValueError: 包含非 AUTODOC 变量或值包含换行时抛出
    """
    invalid_names = [name for name in values if not name.startswith("AUTODOC_")]
    if invalid_names:
        raise ValueError(f"不支持的环境变量: {', '.join(invalid_names)}")
    if any("\n" in value or "\r" in value for value in values.values()):
        raise ValueError("环境变量值不能包含换行符")

    home_dir = Path(home) if home else Path.home()
    env_dir = home_dir / ".config" / "autodoc"
    env_file = get_user_env_file(home_dir)
    rc_path = Path(shell_rc) if shell_rc else _detect_shell_rc(home_dir)

    env_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(env_dir, 0o700)

    lines = ["# Generated by AutoDocUpdater. Do not commit this file."]
    for name in sorted(values):
        lines.append(f"export {name}={shlex.quote(values[name])}")
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(env_file, 0o600)

    rc_path.parent.mkdir(parents=True, exist_ok=True)
    existing = rc_path.read_text(encoding="utf-8") if rc_path.exists() else ""
    block = _source_block(env_file)
    pattern = re.compile(
        re.escape(_SOURCE_START) + r".*?" + re.escape(_SOURCE_END) + r"\n?",
        re.DOTALL,
    )
    if pattern.search(existing):
        updated = pattern.sub(block, existing)
    else:
        updated = existing.rstrip() + ("\n\n" if existing.strip() else "") + block
    rc_path.write_text(updated, encoding="utf-8")

    return {
        "env_file": str(env_file),
        "shell_rc": str(rc_path),
    }
