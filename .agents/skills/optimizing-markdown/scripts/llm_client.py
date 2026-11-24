#!/usr/bin/env python3
"""
LLM 客户端模块

提供通用的 LLM 调用接口，支持多种 LLM 提供者（OpenAI、Anthropic 等）。
通过 langchain 实现灵活的 LLM 管理和切换。
所有配置通过配置文件管理，不再使用环境变量。
"""

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

import yaml

from env_config import (
    CONFIG_PATH,
    EnvironmentConfigurationError,
    apply_environment_overrides,
    check_environment,
)


_SKILL_ROOT = Path(__file__).resolve().parent.parent
_PROMPTS_DIR = _SKILL_ROOT / "prompts"


class LLMProvider(ABC):
    """LLM 提供者抽象基类"""

    @classmethod
    @abstractmethod
    def build_params_from_config(cls, config: dict, model_config: dict, override_kwargs: dict) -> dict:
        """从配置构建提供者初始化参数

        每个子类实现自己的配置解析逻辑，将特定配置转换为初始化参数。

        @param config: 全局配置字典
        @type  config: dict
        @param model_config: model 部分的配置字典
        @type  model_config: dict
        @param override_kwargs: 用户传入的覆盖参数
        @type  override_kwargs: dict
        @return: 提供者初始化参数字典
        @rtype:  dict
        """
        pass

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """生成文本

        @param prompt: 输入提示词
        @type  prompt: str
        @param kwargs: 其他生成参数
        @return: 生成的文本
        @rtype:  str
        """
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """获取模型名称

        @return: 模型名称
        @rtype:  str
        """
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI LLM 提供者"""

    PROVIDER_NAME = "openai"

    @classmethod
    def build_params_from_config(cls, config: dict, model_config: dict, override_kwargs: dict) -> dict:
        """从配置构建 OpenAI 提供者参数"""
        provider_config = config.get(cls.PROVIDER_NAME, {})

        params = {
            "model_name": override_kwargs.pop("model_name", model_config.get(cls.PROVIDER_NAME, "gpt-4o")),
            "api_key": override_kwargs.pop("api_key", provider_config.get("api_key", "")),
            "api_base": override_kwargs.pop("api_base", provider_config.get("api_base", "")),
        }
        return params

    def __init__(
        self,
        model_name: str = "gpt-4o",
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        **kwargs
    ):
        """初始化 OpenAI 提供者

        @param model_name: 模型名称
        @type  model_name: str
        @param api_key: API 密钥（从环境变量合并后的配置读取）
        @type  api_key: Optional[str]
        @param api_base: OpenAI 兼容 API 地址
        @type  api_base: Optional[str]
        @param kwargs: 其他参数
        """
        self.model_name = model_name
        self.api_key = api_key
        self.api_base = api_base
        self.kwargs = kwargs

        if not self.api_key:
            raise ValueError("OpenAI API 密钥未配置，请检查配置文件")

        self._client = None
        self._langchain_model = None

    def _get_client(self):
        """获取 langchain 模型"""
        if self._langchain_model is None:
            try:
                from langchain_openai import ChatOpenAI
                self._langchain_model = ChatOpenAI(
                    model=self.model_name,
                    api_key=self.api_key,
                    **({"base_url": self.api_base} if self.api_base else {}),
                    **self.kwargs
                )
            except ImportError:
                raise ImportError("请安装 langchain-openai: pip install langchain-openai")
        return self._langchain_model

    def generate(self, prompt: str, **kwargs) -> str:
        """生成文本

        @param prompt: 输入提示词
        @type  prompt: str
        @param kwargs: 其他生成参数
        @return: 生成的文本
        @rtype:  str
        """
        model = self._get_client()
        response = model.invoke(prompt, **kwargs)
        return response.content

    def get_model_name(self) -> str:
        """获取模型名称"""
        return self.model_name


class AnthropicProvider(LLMProvider):
    """Anthropic LLM 提供者"""

    PROVIDER_NAME = "anthropic"

    @classmethod
    def build_params_from_config(cls, config: dict, model_config: dict, override_kwargs: dict) -> dict:
        """从配置构建 Anthropic 提供者参数"""
        provider_config = config.get(cls.PROVIDER_NAME, {})

        params = {
            "model_name": override_kwargs.pop("model_name", model_config.get(cls.PROVIDER_NAME, "claude-opus-4-6")),
            "api_key": override_kwargs.pop("api_key", provider_config.get("api_key", "")),
            "api_base": override_kwargs.pop("api_base", provider_config.get("api_base", "")),
        }
        return params

    def __init__(
        self,
        model_name: str = "claude-opus-4-6",
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        **kwargs
    ):
        """初始化 Anthropic 提供者

        @param model_name: 模型名称
        @type  model_name: str
        @param api_key: API 密钥（从环境变量合并后的配置读取）
        @type  api_key: Optional[str]
        @param api_base: Anthropic 兼容 API 地址
        @type  api_base: Optional[str]
        @param kwargs: 其他参数
        """
        self.model_name = model_name
        self.api_key = api_key
        self.api_base = api_base
        self.kwargs = kwargs

        if not self.api_key:
            raise ValueError("Anthropic API 密钥未配置，请检查配置文件")

        self._langchain_model = None

    def _get_model(self):
        """获取 langchain 模型"""
        if self._langchain_model is None:
            try:
                from langchain_anthropic import ChatAnthropic
                self._langchain_model = ChatAnthropic(
                    model=self.model_name,
                    api_key=self.api_key,
                    **({"base_url": self.api_base} if self.api_base else {}),
                    **self.kwargs
                )
            except ImportError:
                raise ImportError("请安装 langchain-anthropic: pip install langchain-anthropic")
        return self._langchain_model

    def generate(self, prompt: str, **kwargs) -> str:
        """生成文本

        @param prompt: 输入提示词
        @type  prompt: str
        @param kwargs: 其他生成参数
        @return: 生成的文本
        @rtype:  str
        """
        model = self._get_model()
        response = model.invoke(prompt, **kwargs)
        return response.content

    def get_model_name(self) -> str:
        """获取模型名称"""
        return self.model_name


class AzureOpenAIProvider(LLMProvider):
    """Azure OpenAI LLM 提供者"""

    PROVIDER_NAME = "azure_openai"

    @classmethod
    def build_params_from_config(cls, config: dict, model_config: dict, override_kwargs: dict) -> dict:
        """从配置构建 Azure OpenAI 提供者参数"""
        provider_config = config.get(cls.PROVIDER_NAME, {})

        params = {
            "model_name": override_kwargs.pop("model_name", model_config.get(cls.PROVIDER_NAME, "gpt-4o")),
            "api_key": override_kwargs.pop("api_key", provider_config.get("api_key", "")),
            "azure_endpoint": override_kwargs.pop("azure_endpoint", provider_config.get("azure_endpoint", "")),
            "api_version": override_kwargs.pop("api_version", provider_config.get("api_version", "2024-02-01")),
        }
        return params

    def __init__(
        self,
        model_name: str = "gpt-4o",
        api_key: Optional[str] = None,
        azure_endpoint: Optional[str] = None,
        api_version: str = "2024-02-01",
        **kwargs
    ):
        """初始化 Azure OpenAI 提供者

        @param model_name: 部署名称
        @type  model_name: str
        @param api_key: API 密钥（从环境变量合并后的配置读取）
        @type  api_key: Optional[str]
        @param azure_endpoint: Azure 端点（从配置文件读取）
        @type  azure_endpoint: Optional[str]
        @param api_version: API 版本
        @type  api_version: str
        @param kwargs: 其他参数
        """
        self.model_name = model_name
        self.api_key = api_key
        self.azure_endpoint = azure_endpoint
        self.api_version = api_version
        self.kwargs = kwargs

        if not self.api_key or not self.azure_endpoint:
            raise ValueError("Azure OpenAI 配置不完整，请检查配置文件")

        self._langchain_model = None

    def _get_model(self):
        """获取 langchain 模型"""
        if self._langchain_model is None:
            try:
                from langchain_openai import AzureChatOpenAI
                self._langchain_model = AzureChatOpenAI(
                    deployment_name=self.model_name,
                    api_key=self.api_key,
                    azure_endpoint=self.azure_endpoint,
                    api_version=self.api_version,
                    **self.kwargs
                )
            except ImportError:
                raise ImportError("请安装 langchain-openai: pip install langchain-openai")
        return self._langchain_model

    def generate(self, prompt: str, **kwargs) -> str:
        """生成文本

        @param prompt: 输入提示词
        @type  prompt: str
        @param kwargs: 其他生成参数
        @return: 生成的文本
        @rtype:  str
        """
        model = self._get_model()
        response = model.invoke(prompt, **kwargs)
        return response.content

    def get_model_name(self) -> str:
        """获取模型名称"""
        return self.model_name


class GoogleVertexAIProvider(LLMProvider):
    """Google Vertex AI LLM 提供者"""

    PROVIDER_NAME = "google_vertexai"

    @classmethod
    def build_params_from_config(cls, config: dict, model_config: dict, override_kwargs: dict) -> dict:
        """从配置构建 Google Vertex AI 提供者参数"""
        provider_config = config.get(cls.PROVIDER_NAME, {})

        params = {
            "model_name": override_kwargs.pop("model_name", model_config.get(cls.PROVIDER_NAME, "gemini-pro")),
            "project_id": override_kwargs.pop("project_id", provider_config.get("project_id", "")),
            "location": override_kwargs.pop("location", provider_config.get("location", "us-central1")),
        }
        return params

    def __init__(
        self,
        model_name: str = "gemini-pro",
        project_id: Optional[str] = None,
        location: str = "us-central1",
        **kwargs
    ):
        """初始化 Google Vertex AI 提供者

        @param model_name: 模型名称
        @type  model_name: str
        @param project_id: GCP 项目 ID（从配置文件读取）
        @type  project_id: Optional[str]
        @param location: GCP 区域
        @type  location: str
        @param kwargs: 其他参数
        """
        self.model_name = model_name
        self.project_id = project_id
        self.location = location
        self.kwargs = kwargs

        self._langchain_model = None

    def _get_model(self):
        """获取 langchain 模型"""
        if self._langchain_model is None:
            try:
                from langchain_google_vertexai import ChatVertexAI
                self._langchain_model = ChatVertexAI(
                    model_name=self.model_name,
                    project=self.project_id,
                    location=self.location,
                    **self.kwargs
                )
            except ImportError:
                raise ImportError("请安装 langchain-google-vertexai: pip install langchain-google-vertexai")
        return self._langchain_model

    def generate(self, prompt: str, **kwargs) -> str:
        """生成文本

        @param prompt: 输入提示词
        @type  prompt: str
        @param kwargs: 其他生成参数
        @return: 生成的文本
        @rtype:  str
        """
        model = self._get_model()
        response = model.invoke(prompt, **kwargs)
        return response.content

    def get_model_name(self) -> str:
        """获取模型名称"""
        return self.model_name


class LiteLLMProvider(LLMProvider):
    """LiteLLM 代理提供者

    支持通过 LiteLLM 代理调用多种 LLM，包括 MiniMax、GLM、Kimi 等。
    使用 Anthropic 兼容格式进行调用。
    """

    PROVIDER_NAME = "litellm"

    @classmethod
    def build_params_from_config(cls, config: dict, model_config: dict, override_kwargs: dict) -> dict:
        """从配置构建 LiteLLM 提供者参数"""
        provider_config = config.get(cls.PROVIDER_NAME, {})

        params = {
            "model_name": override_kwargs.pop("model_name", model_config.get(cls.PROVIDER_NAME, "deepseek-flash")),
            "api_base": override_kwargs.pop("api_base", provider_config.get("api_base", "")),
            "api_key": override_kwargs.pop("api_key", provider_config.get("api_key", "")),
        }
        return params

    def __init__(
        self,
        model_name: str = "deepseek-flash",
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        **kwargs
    ):
        """初始化 LiteLLM 提供者

        @param model_name: 模型名称，默认 deepseek-flash
        @type  model_name: str
        @param api_base: LiteLLM 代理服务器地址（从配置文件读取）
        @type  api_base: Optional[str]
        @param api_key: API 密钥（从环境变量合并后的配置读取）
        @type  api_key: Optional[str]
        @param kwargs: 其他参数
        """
        self.model_name = model_name
        self.api_base = api_base
        self.api_key = api_key
        self.kwargs = kwargs

        if not self.api_key:
            raise ValueError("LiteLLM API 密钥未配置，请检查配置文件")
        if not self.api_base:
            raise ValueError("LiteLLM API 地址未配置，请检查配置文件")

        self._langchain_model = None

    def _get_model(self):
        """获取 langchain 模型"""
        if self._langchain_model is None:
            try:
                from langchain_anthropic import ChatAnthropic
                self._langchain_model = ChatAnthropic(
                    model=self.model_name,
                    anthropic_api_key=self.api_key,
                    base_url=self.api_base,
                    **self.kwargs
                )
            except ImportError:
                raise ImportError("请安装 langchain-anthropic: pip install langchain-anthropic")
        return self._langchain_model

    def generate(self, prompt: str, **kwargs) -> str:
        """生成文本

        @param prompt: 输入提示词
        @type  prompt: str
        @param kwargs: 其他生成参数
        @return: 生成的文本
        @rtype:  str
        """
        model = self._get_model()
        response = model.invoke(prompt, **kwargs)

        # 处理 MiniMax 等返回的复杂响应格式
        content = response.content

        # 如果 content 是列表（包含 thinking 和 text），提取 text 部分
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        return item.get("text", "")
                elif isinstance(item, str):
                    # 如果是字符串，尝试解析为 JSON
                    try:
                        import json
                        parsed = json.loads(item)
                        if isinstance(parsed, dict) and parsed.get("type") == "text":
                            return parsed.get("text", "")
                    except (json.JSONDecodeError, TypeError):
                        pass
            # 如果没找到 text 类型，返回第一个非 thinking 项
            for item in content:
                if isinstance(item, dict) and item.get("type") != "thinking":
                    return item.get("text", "") or str(item)

        if content is None:
            raise RuntimeError("LLM 返回内容为空")

        return content

    def get_model_name(self) -> str:
        """获取模型名称"""
        return self.model_name


class LLMClient:
    """LLM 客户端

    统一的 LLM 调用接口，支持多种提供者和灵活配置。
    所有配置通过配置文件管理。
    """

    PROVIDER_CLASSES = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "azure_openai": AzureOpenAIProvider,
        "google_vertexai": GoogleVertexAIProvider,
        "litellm": LiteLLMProvider,
    }

    def __init__(
        self,
        provider: Optional[str] = None,
        config_path: Optional[str] = None,
        **override_kwargs
    ):
        """初始化 LLM 客户端

        @param provider: LLM 提供者类型（从配置文件读取，可被覆盖）
        @type  provider: Optional[str]
        @param config_path: 配置文件路径
        @type  config_path: Optional[str]
        @param override_kwargs: 覆盖配置文件的参数
        """
        # 加载配置文件
        if config_path:
            config = self._load_config(config_path)
        else:
            config = self._load_config(str(CONFIG_PATH))

        self.config = apply_environment_overrides(config)
        if provider:
            self.config["provider"] = provider
        status = check_environment(self.config)
        if not status.configured:
            raise EnvironmentConfigurationError(status)
        self.config = status.config

        # 确定使用的提供者
        self.provider_name = self.config.get("provider", "openai")

        if self.provider_name not in self.PROVIDER_CLASSES:
            raise ValueError(
                f"不支持的 LLM 提供者: {self.provider_name}。"
                f"支持的提供者: {list(self.PROVIDER_CLASSES.keys())}"
            )

        # 构建提供者初始化参数
        provider_params = self._build_provider_params(override_kwargs)

        provider_class = self.PROVIDER_CLASSES[self.provider_name]
        self._provider = provider_class(**provider_params)

    def _load_config(self, config_path: str) -> dict:
        """加载配置文件

        @param config_path: 配置文件路径
        @type  config_path: str
        @return: 配置字典
        @rtype:  dict
        @raises FileNotFoundError: 配置文件不存在时抛出
        """
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")

        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _build_provider_params(self, override_kwargs: dict) -> dict:
        """构建提供者初始化参数

        通过委托给具体的 Provider 类来消除 if-else 逻辑，符合开闭原则。
        每个 Provider 子类通过 build_params_from_config 类方法负责解析自己的配置。

        @param override_kwargs: 覆盖配置的参数
        @type  override_kwargs: dict
        @return: 提供者初始化参数字典
        @rtype:  dict
        """
        # 获取对应的 Provider 类
        provider_class = self.PROVIDER_CLASSES[self.provider_name]

        # 提取模型配置
        model_config = self.config.get("model", {})

        # 委托给 Provider 类构建其特定参数
        params = provider_class.build_params_from_config(
            self.config, model_config, override_kwargs.copy()
        )

        # 添加通用的生成参数（max_tokens, temperature, top_p）
        generation_config = self.config.get("generation", {})
        for key in ["max_tokens", "temperature", "top_p"]:
            if key in generation_config:
                params[key] = override_kwargs.pop(key, generation_config[key])

        # 添加任何剩余的覆盖参数
        params.update(override_kwargs)

        return params

    def generate(self, prompt: str, **kwargs) -> str:
        """生成文本

        @param prompt: 输入提示词
        @type  prompt: str
        @param kwargs: 其他生成参数
        @return: 生成的文本
        @rtype:  str
        """
        return self._provider.generate(prompt, **kwargs)

    def get_model_name(self) -> str:
        """获取当前模型名称

        @return: 模型名称
        @rtype:  str
        """
        return self._provider.get_model_name()


class PromptTemplate:
    """Prompt 模板管理器"""

    def __init__(self, template_dir: Optional[str] = None):
        """初始化 Prompt 模板管理器

        @param template_dir: 模板目录路径
        @type  template_dir: Optional[str]
        """
        if template_dir:
            self.template_dir = Path(template_dir)
        else:
            self.template_dir = _PROMPTS_DIR

        self._templates: dict[str, str] = {}

    def load(self, name: str) -> str:
        """加载指定名称的模板

        @param name: 模板名称（不含扩展名）
        @type  name: str
        @return: 模板内容
        @rtype:  str
        """
        if name in self._templates:
            return self._templates[name]

        template_path = self.template_dir / f"{name}.yaml"
        if not template_path.exists():
            raise FileNotFoundError(f"模板文件不存在: {template_path}")

        with open(template_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        template = data.get("template", "")
        self._templates[name] = template
        return template

    def render(self, name: str, **kwargs) -> str:
        """渲染模板

        @param name: 模板名称
        @type  name: str
        @param kwargs: 模板变量
        @return: 渲染后的文本
        @rtype:  str
        """
        template = self.load(name)
        # 直接替换占位符，避免文章内容中的 { } 导致 format() 失败
        for key, value in kwargs.items():
            placeholder = "{" + key + "}"
            template = template.replace(placeholder, str(value))
        return template

    def list_templates(self) -> list[str]:
        """列出所有可用模板

        @return: 模板名称列表
        @rtype:  list[str]
        """
        if not self.template_dir.exists():
            return []

        return [
            p.stem for p in self.template_dir.glob("*.yaml")
        ]
