#!/usr/bin/env python3
"""
51CTO 博客批量上传工具

该脚本用于将本地 Markdown 格式文件批量发布到 51CTO 博客网站。
支持单个文件或目录批量上传，使用 Selenium 操作浏览器完成自动化发布。
"""

import argparse
import json
import logging
import logging.handlers
import os
import re
import subprocess
import sys
import tempfile
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, urlunparse


def _default_selenium_profile_dir() -> Path:
    """返回当前平台的 Selenium Chrome 用户数据目录

    @return: 平台专属的 SeleniumProfile 路径
    @rtype:  Path
    """
    if sys.platform == "darwin":
        return Path("~/Library/Application Support/Google/Chrome/SeleniumProfile").expanduser()
    if sys.platform == "win32":
        local_app_data = os.getenv("LOCALAPPDATA")
        base_dir = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
        return base_dir / "Google" / "Chrome" / "SeleniumProfile"
    xdg_config_home = os.getenv("XDG_CONFIG_HOME")
    base_dir = Path(xdg_config_home) if xdg_config_home else Path.home() / ".config"
    return base_dir / "google-chrome" / "SeleniumProfile"


_SKILL_ROOT = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _SKILL_ROOT.parents[2]
_DEFAULT_LOG_DIR = _PROJECT_ROOT / "logs"
_SELENIUM_PROFILE_DIR = _default_selenium_profile_dir()
_SELENIUM_MANAGER_TIMEOUT_SECONDS = 120
_LOGIN_POLL_INTERVAL_SECONDS = 0.5
_INITIAL_LOGIN_STATE_TIMEOUT_SECONDS = 15
_MANUAL_LOGIN_TIMEOUT_SECONDS = 60
_POST_LOGIN_STABLE_DELAY_SECONDS = 2
_PUBLISH_STABLE_CONFIRM_SECONDS = 1
_LOGIN_HOSTS = {"home.51cto.com", "passport.51cto.com"}
_BLOG_HOST = "blog.51cto.com"
_PUBLISH_PATH = "/blogger/publish"
_CLASSIFY_URL = "https://blog.51cto.com/creative-center/classify"
_MAX_RETRIES_DEFAULT = 1
_RETRY_DELAY_SECONDS = 2
_PUBLISH_RESULT_TIMEOUT_SECONDS = 30
_DEFAULT_RETRY_MANIFEST = _PROJECT_ROOT / "tmp" / "51cto_retry.json"


class LoginFailureReason(Enum):
    """登录失败原因枚举"""

    SESSION_MISSING_OR_EXPIRED = "session_missing_or_expired"
    LOGIN_TIMEOUT = "login_timeout"
    LOGIN_REJECTED = "login_rejected"
    LOGIN_CAPTCHA_REQUIRED = "login_captcha_required"
    SESSION_NOT_ESTABLISHED = "session_not_established"
    PUBLISH_PAGE_UNAVAILABLE = "publish_page_unavailable"
    UNEXPECTED_REDIRECT = "unexpected_redirect"
    BROWSER_CLOSED = "browser_closed"
    BROWSER_START_FAILED = "browser_start_failed"
    BROWSER_PERMISSION_REQUIRED = "browser_permission_required"
    PROFILE_IN_USE = "profile_in_use"
    PAGE_LOAD_FAILED = "page_load_failed"
    UNKNOWN_LOGIN_STATE = "unknown_login_state"


_LOGIN_FAILURE_SUMMARIES = {
    LoginFailureReason.SESSION_MISSING_OR_EXPIRED: "登录会话不存在或已过期",
    LoginFailureReason.LOGIN_TIMEOUT: "登录超时",
    LoginFailureReason.LOGIN_REJECTED: "登录被拒绝",
    LoginFailureReason.LOGIN_CAPTCHA_REQUIRED: "需要完成安全验证",
    LoginFailureReason.SESSION_NOT_ESTABLISHED: "登录会话未建立",
    LoginFailureReason.PUBLISH_PAGE_UNAVAILABLE: "发布页不可用",
    LoginFailureReason.UNEXPECTED_REDIRECT: "页面跳转异常",
    LoginFailureReason.BROWSER_CLOSED: "浏览器已关闭",
    LoginFailureReason.BROWSER_START_FAILED: "浏览器启动失败",
    LoginFailureReason.BROWSER_PERMISSION_REQUIRED: "浏览器目录权限不足",
    LoginFailureReason.PROFILE_IN_USE: "浏览器配置目录被占用",
    LoginFailureReason.PAGE_LOAD_FAILED: "页面加载失败",
    LoginFailureReason.UNKNOWN_LOGIN_STATE: "无法确认登录状态",
}

_LOGIN_FAILURE_SUGGESTIONS = {
    LoginFailureReason.SESSION_MISSING_OR_EXPIRED: "请在脚本打开的 Selenium Chrome 中完成登录后重试。",
    LoginFailureReason.LOGIN_TIMEOUT: "请保持浏览器窗口打开，并在 60 秒内完成登录、验证码或安全验证后重试。",
    LoginFailureReason.LOGIN_REJECTED: "请检查账号、密码或账号状态后重试。",
    LoginFailureReason.LOGIN_CAPTCHA_REQUIRED: "请完成验证码或安全验证后重试。",
    LoginFailureReason.SESSION_NOT_ESTABLISHED: "请重新运行脚本并在 Selenium Chrome 中完成登录。",
    LoginFailureReason.PUBLISH_PAGE_UNAVAILABLE: "请检查账号是否具有发布权限，并确认 51CTO 发布页是否正常。",
    LoginFailureReason.UNEXPECTED_REDIRECT: "请检查网络、代理设置或 51CTO 当前页面状态。",
    LoginFailureReason.BROWSER_CLOSED: "请保持浏览器窗口打开，不要中途关闭。",
    LoginFailureReason.BROWSER_START_FAILED: "请检查 Chrome、Selenium 及 ChromeDriver 自动管理是否正常。",
    LoginFailureReason.BROWSER_PERMISSION_REQUIRED: "请允许当前进程写入 SeleniumProfile 和 Selenium 缓存，或从普通终端运行上传脚本。",
    LoginFailureReason.PROFILE_IN_USE: "请关闭其他上传脚本或占用 SeleniumProfile 的 Chrome 进程后重试。",
    LoginFailureReason.PAGE_LOAD_FAILED: "请检查网络、代理和 51CTO 服务状态后重试。",
    LoginFailureReason.UNKNOWN_LOGIN_STATE: "请重试；若问题持续，请根据日志中的 URL、页面标题和耗时排查。",
}


@dataclass
class LoginFailure:
    """登录失败详情"""

    reason: LoginFailureReason
    message: str
    url: str = ""
    page_title: str = ""
    elapsed_seconds: float = 0.0
    detail: str = ""

    @property
    def summary(self) -> str:
        """返回用户可读的失败摘要"""
        return _LOGIN_FAILURE_SUMMARIES[self.reason]

    @property
    def suggestion(self) -> str:
        """返回用户可读的处理建议"""
        return _LOGIN_FAILURE_SUGGESTIONS[self.reason]

    def format_for_user(self) -> str:
        """格式化用户反馈文本"""
        lines = [f"登录失败：{self.summary}", f"原因：{self.message}"]
        if self.url:
            lines.append(f"当前页面：{self.url}")
        if self.page_title:
            lines.append(f"页面标题：{self.page_title}")
        if self.elapsed_seconds:
            lines.append(f"检测耗时：{self.elapsed_seconds:.1f} 秒")
        if self.detail:
            lines.append(f"详细信息：{self.detail}")
        lines.append("处理结果：未加载、未上传、未删除任何文章。")
        lines.append(f"建议：{self.suggestion}")
        return "\n".join(lines)

    def to_log_dict(self) -> dict:
        """转换为结构化日志字段"""
        return {
            "reason": self.reason.value,
            "message": self.message,
            "url": self.url,
            "page_title": self.page_title,
            "elapsed_seconds": round(self.elapsed_seconds, 1),
            "detail": self.detail,
        }


class LoginRequiredError(RuntimeError):
    """用户未登录或登录失败异常"""

    def __init__(self, failure: LoginFailure):
        """初始化登录异常

        @param failure: 登录失败详情
        @type  failure: LoginFailure
        """
        self.failure = failure
        super().__init__(failure.message)


@dataclass
class UploadResult:
    """上传结果数据类"""

    success_count: int = 0
    fail_count: int = 0
    personal_category: str = ""
    success_files: list[str] = field(default_factory=list)
    fail_files: list[tuple[str, str]] = field(default_factory=list)
    success_paths: list[str] = field(default_factory=list)
    retained_files: list[dict] = field(default_factory=list)


@dataclass
class PublishOutcome:
    """单篇发布结果"""

    success: bool
    message: str
    stage: str
    retry_safe: bool
    final_submit_clicked: bool = False
    final_url: str = ""
    attempts: int = 1


class BrowserEnvironmentError(RuntimeError):
    """浏览器运行环境预检失败"""

    def __init__(self, reason: str, message: str):
        self.reason = reason
        super().__init__(message)


class PersonalCategoryError(RuntimeError):
    """个人分类读取、创建或验证失败"""


class BrowserAutomation:
    """浏览器自动化操作类"""

    def __init__(self, logger: Optional[logging.Logger] = None):
        """初始化浏览器自动化

        @param logger: 日志记录器
        @type  logger: Optional[logging.Logger]
        @raises ImportError: Selenium 未安装时抛出
        """
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
        except ImportError:
            raise ImportError("请安装 selenium: pip install selenium")

        self._webdriver = webdriver
        self._Options = Options
        self.logger = logger
        self._driver = None

    def _profile_in_use(self) -> bool:
        """判断 SeleniumProfile 是否被活动 Chrome 进程占用"""
        singleton_lock = _SELENIUM_PROFILE_DIR / "SingletonLock"
        if singleton_lock.is_symlink():
            try:
                target = os.readlink(singleton_lock)
                pid_text = target.rsplit("-", 1)[-1]
                if pid_text.isdigit():
                    os.kill(int(pid_text), 0)
                    return True
            except (OSError, ValueError):
                pass

        try:
            result = subprocess.run(
                ["pgrep", "-f", str(_SELENIUM_PROFILE_DIR)],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    @staticmethod
    def _directory_writable(path: Path) -> bool:
        """通过实际写入临时文件判断目录是否可写"""
        try:
            with tempfile.NamedTemporaryFile(
                dir=path,
                prefix=".autodoc-write-test-",
                delete=True,
            ) as test_file:
                test_file.write(b"ok")
                test_file.flush()
            return True
        except OSError:
            return False

    def _prepare_profile(self) -> None:
        """预检 Chrome Profile 并清理陈旧锁文件

        @raises BrowserEnvironmentError: 目录不可写或 Profile 正在使用时抛出
        """
        profile_dir = _SELENIUM_PROFILE_DIR
        try:
            profile_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise BrowserEnvironmentError(
                "permission_required",
                f"无法创建 SeleniumProfile 目录: {profile_dir}: {exc}",
            ) from exc

        if not self._directory_writable(profile_dir):
            raise BrowserEnvironmentError(
                "permission_required",
                f"当前进程没有写入 SeleniumProfile 的权限: {profile_dir}",
            )

        if self._profile_in_use():
            raise BrowserEnvironmentError(
                "profile_in_use",
                f"SeleniumProfile 正被活动 Chrome 进程使用: {profile_dir}",
            )

        stale_names = (
            "DevToolsActivePort",
            "SingletonLock",
            "SingletonSocket",
            "SingletonCookie",
        )
        for name in stale_names:
            stale_path = profile_dir / name
            if not (stale_path.exists() or stale_path.is_symlink()):
                continue
            try:
                stale_path.unlink()
                if self.logger:
                    self.logger.info({
                        "timestamp": datetime.now().isoformat(),
                        "level": "info",
                        "event": "stale_browser_lock_removed",
                        "path": str(stale_path),
                    })
            except OSError as exc:
                raise BrowserEnvironmentError(
                    "permission_required",
                    f"无法清理陈旧 Chrome 锁文件 {stale_path}: {exc}",
                ) from exc

        cache_dir = Path("~/.cache/selenium").expanduser()
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_writable = self._directory_writable(cache_dir)
        except OSError:
            cache_writable = False
        if not cache_writable and self.logger:
            self.logger.warning({
                "timestamp": datetime.now().isoformat(),
                "level": "warning",
                "event": "selenium_cache_not_writable",
                "path": str(cache_dir),
                "note": "已有缓存 driver 仍可使用；首次下载或元数据更新可能失败",
            })

    def setup_driver(self) -> "webdriver.Chrome":
        """设置并返回 Chrome 驱动

        @return: Chrome WebDriver 实例
        @rtype:  webdriver.Chrome
        """
        self._prepare_profile()
        options = self._Options()
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-infobars")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        # 使用专门为 Selenium 创建的 Chrome 用户数据目录
        # 这个目录会在首次登录后保存 Cookie，下次运行时无需重新登录
        selenium_profile_dir = str(_SELENIUM_PROFILE_DIR)
        options.add_argument(f"--user-data-dir={selenium_profile_dir}")

        previous_timeout = os.environ.get("SE_TIMEOUT")
        os.environ["SE_TIMEOUT"] = str(_SELENIUM_MANAGER_TIMEOUT_SECONDS)
        try:
            self._driver = self._webdriver.Chrome(options=options)
        except Exception as e:
            raise RuntimeError(
                "Selenium Manager 无法获取兼容的 ChromeDriver，"
                f"网络超时设置为 {_SELENIUM_MANAGER_TIMEOUT_SECONDS} 秒: {e}"
            ) from e
        finally:
            if previous_timeout is None:
                os.environ.pop("SE_TIMEOUT", None)
            else:
                os.environ["SE_TIMEOUT"] = previous_timeout

        if self.logger:
            capabilities = self._driver.capabilities
            self.logger.info({
                "timestamp": datetime.now().isoformat(),
                "level": "info",
                "event": "driver_ready",
                "driver_path": self._driver.service.path,
                "browser_version": capabilities.get("browserVersion"),
                "manager_timeout_seconds": _SELENIUM_MANAGER_TIMEOUT_SECONDS
            })

        return self._driver

    def quit(self) -> None:
        """关闭浏览器驱动"""
        if self._driver:
            self._driver.quit()
            self._driver = None


class C51ctoUploader:
    """51CTO 博客上传器

    使用 Selenium 自动化操作浏览器，将本地 Markdown 文件发布到 51CTO 博客。
    """

    # 发布页 URL
    PUBLISH_URL = "https://blog.51cto.com/blogger/publish"
    CLASSIFY_URL = _CLASSIFY_URL
    PROHIBITED_POPUP_XPATH = "/html/body/div[2]/div[4]"
    CONTINUE_PUBLISH_XPATH = "/html/body/div[2]/div[4]/div/div[4]/button[1]"
    CATEGORY_TEXT_XPATH = "//*[@id='oneLever']//*[normalize-space()='代码人生']"
    CATEGORY_FALLBACK_XPATH = "//*[@id='oneLever']/div[22]"
    PERSONAL_CATEGORY_FIELD_ID = "selfType"
    PERSONAL_CATEGORY_CONTAINER_CSS = ".el-select.classification.person-type"
    PERSONAL_CATEGORY_OPTION_CSS = ".el-select-dropdown__item"
    CLASSIFY_ADD_BUTTON_CSS = "span.addClassify"
    CLASSIFY_SAVE_BUTTON_CSS = "span.saveClassify"
    CLASSIFY_CATEGORY_INPUT_CSS = "input.name[name^='Cate[']"
    CLASSIFY_NEW_CATEGORY_INPUT_CSS = "input.name[name^='name[']"

    def __init__(self, logger: Optional[logging.Logger] = None):
        """初始化 51CTO 上传器

        @param logger: 日志记录器
        @type  logger: Optional[logging.Logger]
        """
        self.logger = logger
        self._browser: Optional[BrowserAutomation] = None
        self._driver = None

    def _log(self, level: str, data: dict) -> None:
        """记录 JSON 格式日志

        @param level: 日志级别 (info, warning, error)
        @type  level: str
        @param data: 日志数据
        @type  data: dict
        """
        if self.logger:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "level": level,
                **data
            }
            getattr(self.logger, level.lower())(str(log_entry))

    def _delete_local_file(self, file_path: str) -> bool:
        """删除本地文件

        @param file_path: 要删除的文件路径
        @type  file_path: str
        @return: 删除成功返回 True，失败返回 False
        @rtype:  bool
        """
        try:
            path = Path(file_path)
            if path.exists() and path.is_file():
                path.unlink()
                self._log("info", {"event": "file_deleted", "file": str(path)})
                return True
            return False
        except Exception as e:
            self._log("warning", {"event": "file_delete_failed", "file": file_path, "error": str(e)})
            return False

    def _get_browser(self) -> BrowserAutomation:
        """获取浏览器自动化实例

        @return: 浏览器自动化实例
        @rtype:  BrowserAutomation
        """
        if self._browser is None:
            self._browser = BrowserAutomation(self.logger)
        return self._browser

    @staticmethod
    def _sanitize_url(url: str) -> str:
        """移除 URL 中的查询参数和片段，避免记录敏感信息

        @param url: 原始 URL
        @type  url: str
        @return: 仅包含协议、主机和路径的 URL
        @rtype:  str
        """
        if not url:
            return ""
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return url.split("?", 1)[0].split("#", 1)[0][:200]
            return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
        except Exception:
            return url.split("?", 1)[0].split("#", 1)[0][:200]

    @staticmethod
    def _is_login_url(url: str) -> bool:
        """判断 URL 是否为 51CTO 登录页

        @param url: 页面 URL
        @type  url: str
        @return: 是否属于登录页
        @rtype:  bool
        """
        try:
            parsed = urlparse(url)
            host = (parsed.hostname or "").lower()
            path = (parsed.path or "").lower().rstrip("/")
            return host in _LOGIN_HOSTS or path in {"/login", "/signin"} or \
                path.endswith("/login") or path.endswith("/signin")
        except Exception:
            return False

    @staticmethod
    def _is_publish_url(url: str) -> bool:
        """判断 URL 是否严格匹配 51CTO 发布页

        @param url: 页面 URL
        @type  url: str
        @return: 是否为发布页 URL
        @rtype:  bool
        """
        try:
            parsed = urlparse(url)
            return (parsed.hostname or "").lower() == _BLOG_HOST and \
                (parsed.path or "").lower().rstrip("/") == _PUBLISH_PATH
        except Exception:
            return False

    def _page_title(self) -> str:
        """安全读取当前页面标题

        @return: 截断后的页面标题
        @rtype:  str
        """
        try:
            return (self._driver.title or "")[:160]
        except Exception:
            return ""

    def _page_text(self) -> str:
        """安全读取当前页面可见文本

        @return: 截断后的页面文本
        @rtype:  str
        """
        try:
            body = self._driver.find_element("tag name", "body")
            return (body.text or "")[:10000]
        except Exception:
            return ""

    def _is_title_visible(self) -> bool:
        """判断发布页标题输入框是否可见

        @return: 标题输入框是否可见
        @rtype:  bool
        """
        elements = self._driver.find_elements("id", "title")
        return any(element.is_displayed() for element in elements)

    def _is_publish_page_ready(self) -> bool:
        """判断当前页面是否为可用的发布页

        @return: URL 和标题输入框是否同时满足
        @rtype:  bool
        """
        return self._is_publish_url(self._driver.current_url) and self._is_title_visible()

    @staticmethod
    def _is_browser_closed_error(exc: Exception) -> bool:
        """判断异常是否表示浏览器窗口或会话已失效

        @param exc: 异常对象
        @type  exc: Exception
        @return: 是否属于浏览器关闭类异常
        @rtype:  bool
        """
        message = str(exc).lower()
        indicators = (
            "invalid session id",
            "no such window",
            "target window already closed",
            "chrome not reachable",
            "disconnected",
        )
        return any(indicator in message for indicator in indicators)

    @staticmethod
    def _is_profile_lock_error(exc: Exception) -> bool:
        """判断异常是否表示 Chrome 用户数据目录被占用

        @param exc: 异常对象
        @type  exc: Exception
        @return: 是否为 Profile 占用错误
        @rtype:  bool
        """
        message = str(exc).lower()
        return "user data directory is already in use" in message or \
            "profile appears to be in use" in message

    @staticmethod
    def _is_browser_permission_error(exc: Exception) -> bool:
        """判断异常是否表示浏览器目录权限不足

        @param exc: 异常对象
        @type  exc: Exception
        @return: 是否为权限不足
        @rtype:  bool
        """
        message = str(exc).lower()
        indicators = (
            "operation not permitted",
            "permission denied",
            "not writable",
            "read-only file system",
        )
        return any(indicator in message for indicator in indicators)

    def _match_login_page_issue(self, text: str) -> tuple[Optional[str], str]:
        """从登录页文本中匹配可确认的失败原因

        @param text: 页面可见文本
        @type  text: str
        @return: (问题类型, 页面证据)
        @rtype:  tuple[Optional[str], str]
        """
        lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]
        rejected_keywords = (
            "用户名或密码错误",
            "账号或密码错误",
            "密码错误",
            "账号不存在",
            "用户不存在",
            "账号被锁定",
            "账户被锁定",
            "登录失败",
            "认证失败",
            "登录异常",
            "操作过于频繁",
        )
        captcha_keywords = (
            "验证码错误",
            "验证码已过期",
            "请完成安全验证",
            "请完成验证",
            "人机验证",
            "滑动验证",
            "拖动滑块",
            "安全验证",
        )
        for keyword in rejected_keywords:
            for line in lines:
                if keyword in line:
                    return "rejected", line[:160]
        for keyword in captcha_keywords:
            for line in lines:
                if keyword in line:
                    return "captcha", line[:160]
        return None, ""

    def _raise_login_failure(
        self,
        reason: LoginFailureReason,
        message: str,
        started_at: float,
        detail: str = ""
    ) -> None:
        """记录并抛出登录失败异常

        @param reason: 失败原因
        @type  reason: LoginFailureReason
        @param message: 用户可读原因
        @type  message: str
        @param started_at: 检测开始时间
        @type  started_at: float
        @param detail: 补充技术信息
        @type  detail: str
        @raises LoginRequiredError: 登录失败时抛出
        """
        url = ""
        try:
            url = self._sanitize_url(self._driver.current_url)
        except Exception:
            pass
        failure = LoginFailure(
            reason=reason,
            message=message,
            url=url,
            page_title=self._page_title(),
            elapsed_seconds=time.monotonic() - started_at,
            detail=re.sub(r"\s+", " ", detail).strip()[:300],
        )
        self._log("error", {"event": "login_failed", **failure.to_log_dict()})
        raise LoginRequiredError(failure)

    def _raise_login_page_failure(
        self,
        started_at: float,
        default_reason: LoginFailureReason = LoginFailureReason.LOGIN_TIMEOUT
    ) -> None:
        """根据登录页文本记录并抛出具体失败

        @param started_at: 检测开始时间
        @type  started_at: float
        @param default_reason: 未匹配到明确提示时的默认失败原因
        @type  default_reason: LoginFailureReason
        @raises LoginRequiredError: 登录失败时抛出
        """
        issue, evidence = self._match_login_page_issue(self._page_text())
        if issue == "rejected":
            self._raise_login_failure(
                LoginFailureReason.LOGIN_REJECTED,
                f"51CTO 登录页提示：{evidence}",
                started_at,
            )
        if issue == "captcha":
            self._raise_login_failure(
                LoginFailureReason.LOGIN_CAPTCHA_REQUIRED,
                f"51CTO 要求完成验证码或安全验证：{evidence}",
                started_at,
            )
        if default_reason == LoginFailureReason.SESSION_NOT_ESTABLISHED:
            message = "已离开登录页并重新打开发布页，但再次被跳转到登录页，未建立有效登录会话。"
        else:
            message = "等待 60 秒后仍停留在 51CTO 登录页；登录会话不存在或已过期，且未检测到登录完成。"
        self._raise_login_failure(default_reason, message, started_at)

    def _raise_current_state_failure(self, started_at: float) -> None:
        """根据当前页面状态抛出登录失败

        @param started_at: 检测开始时间
        @type  started_at: float
        @raises LoginRequiredError: 登录失败时抛出
        """
        try:
            current_url = self._driver.current_url
        except Exception as exc:
            if self._is_browser_closed_error(exc):
                self._raise_login_failure(
                    LoginFailureReason.BROWSER_CLOSED,
                    "等待登录期间浏览器窗口或 Selenium 会话已失效。",
                    started_at,
                    str(exc),
                )
            self._raise_login_failure(
                LoginFailureReason.UNKNOWN_LOGIN_STATE,
                "读取当前页面状态失败。",
                started_at,
                str(exc),
            )

        if self._is_login_url(current_url):
            self._raise_login_page_failure(started_at)
        if self._is_publish_url(current_url):
            self._raise_login_failure(
                LoginFailureReason.PUBLISH_PAGE_UNAVAILABLE,
                "已进入发布页 URL，但标题输入框在等待时间内不可见。",
                started_at,
            )
        if (urlparse(current_url).hostname or "").lower() == _BLOG_HOST:
            self._raise_login_failure(
                LoginFailureReason.SESSION_NOT_ESTABLISHED,
                "页面停留在 51CTO 站点，但未进入发布页。",
                started_at,
            )
        self._raise_login_failure(
            LoginFailureReason.UNEXPECTED_REDIRECT,
            f"页面跳转到未预期地址：{self._sanitize_url(current_url)}",
            started_at,
        )

    def _wait_for_initial_state(self, timeout: float) -> str:
        """等待发布页或登录页稳定出现

        @param timeout: 最长等待秒数
        @type  timeout: float
        @return: ready、login 或 unknown
        @rtype:  str
        """
        deadline = time.monotonic() + timeout
        ready_since = None
        login_count = 0
        while time.monotonic() < deadline:
            current_url = self._driver.current_url
            if self._is_login_url(current_url):
                ready_since = None
                login_count += 1
                if login_count >= 2:
                    return "login"
            elif self._is_publish_page_ready():
                login_count = 0
                if ready_since is None:
                    ready_since = time.monotonic()
                elif time.monotonic() - ready_since >= _PUBLISH_STABLE_CONFIRM_SECONDS:
                    return "ready"
            else:
                ready_since = None
                login_count = 0
            time.sleep(_LOGIN_POLL_INTERVAL_SECONDS)
        return "unknown"

    def _wait_for_manual_login(self, timeout: float) -> bool:
        """等待用户完成手动登录

        @param timeout: 最长等待秒数
        @type  timeout: float
        @return: 是否已离开登录页
        @rtype:  bool
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not self._is_login_url(self._driver.current_url):
                return True
            time.sleep(1)
        return False

    def _check_login_status(self) -> None:
        """确认用户已登录并能够访问 51CTO 发布页

        @raises LoginRequiredError: 未登录、登录失败或无法确认登录状态时抛出
        @raises Exception: 其他浏览器操作异常时抛出
        """
        self._log("info", {"event": "check_login_start"})
        started_at = time.monotonic()

        browser = self._get_browser()
        try:
            self._driver = browser.setup_driver()
        except BrowserEnvironmentError as exc:
            reason = LoginFailureReason.BROWSER_PERMISSION_REQUIRED \
                if exc.reason == "permission_required" else LoginFailureReason.PROFILE_IN_USE
            self._raise_login_failure(reason, str(exc), started_at, str(exc))
        except Exception as exc:
            if self._is_browser_permission_error(exc):
                self._raise_login_failure(
                    LoginFailureReason.BROWSER_PERMISSION_REQUIRED,
                    "当前进程没有权限启动或写入独立 Chrome Profile。",
                    started_at,
                    str(exc),
                )
            if self._is_profile_lock_error(exc):
                self._raise_login_failure(
                    LoginFailureReason.PROFILE_IN_USE,
                    "SeleniumProfile 已被其他 Chrome 或上传脚本占用，无法启动独立浏览器。",
                    started_at,
                    str(exc),
                )
            self._raise_login_failure(
                LoginFailureReason.BROWSER_START_FAILED,
                "Chrome、ChromeDriver 或 Selenium Manager 启动失败。",
                started_at,
                str(exc),
            )

        try:
            self._driver.get(self.PUBLISH_URL)
            state = self._wait_for_initial_state(_INITIAL_LOGIN_STATE_TIMEOUT_SECONDS)
            if state == "unknown":
                self._log("warning", {
                    "event": "login_state_ambiguous",
                    "url": self._sanitize_url(self._driver.current_url)
                })
                self._driver.refresh()
                state = self._wait_for_initial_state(_INITIAL_LOGIN_STATE_TIMEOUT_SECONDS)

            if state == "ready":
                self._log("info", {
                    "event": "login_verified",
                    "reason": "publish_page_ready",
                    "url": self._sanitize_url(self._driver.current_url)
                })
                return

            if state == "login":
                self._log("info", {
                    "event": "login_required",
                    "reason": LoginFailureReason.SESSION_MISSING_OR_EXPIRED.value,
                    "url": self._sanitize_url(self._driver.current_url)
                })
                print("\n请在浏览器中完成 51CTO 博客的登录操作...")
                print("等待登录完成（最多60秒）...")

                if not self._wait_for_manual_login(_MANUAL_LOGIN_TIMEOUT_SECONDS):
                    self._raise_login_page_failure(started_at)

                self._log("info", {
                    "event": "manual_login_completed",
                    "url": self._sanitize_url(self._driver.current_url)
                })
                print("检测到登录完成，正在验证发布页...")
                time.sleep(_POST_LOGIN_STABLE_DELAY_SECONDS)

                self._driver.get(self.PUBLISH_URL)
                state = self._wait_for_initial_state(_INITIAL_LOGIN_STATE_TIMEOUT_SECONDS)
                if state == "ready":
                    self._log("info", {
                        "event": "login_verified",
                        "reason": "publish_page_ready_after_manual_login",
                        "url": self._sanitize_url(self._driver.current_url)
                    })
                    print("检测到登录成功！")
                    return
                if state == "login":
                    self._raise_login_page_failure(
                        started_at,
                        LoginFailureReason.SESSION_NOT_ESTABLISHED,
                    )
                self._raise_current_state_failure(started_at)

            self._raise_current_state_failure(started_at)

        except LoginRequiredError:
            raise
        except Exception as exc:
            if self._is_browser_closed_error(exc):
                self._raise_login_failure(
                    LoginFailureReason.BROWSER_CLOSED,
                    "登录检测期间浏览器窗口或 Selenium 会话已失效。",
                    started_at,
                    str(exc),
                )
            self._raise_login_failure(
                LoginFailureReason.PAGE_LOAD_FAILED,
                "51CTO 页面加载或登录检测失败。",
                started_at,
                str(exc),
            )

    def _load_markdown_file(self, file_path: str) -> tuple[str, str]:
        """加载 Markdown 文件内容

        @param file_path: Markdown 文件路径
        @type  file_path: str
        @return: (文件名称, 文件内容)
        @rtype:  tuple[str, str]
        @raises FileNotFoundError: 文件不存在时抛出
        @raises IOError: 读取文件失败时抛出
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        file_name = path.stem
        self._log("info", {"event": "file_loaded", "file": file_name, "size": len(content)})
        return file_name, content

    def _safe_current_url(self) -> str:
        """安全读取当前页面 URL

        @return: 脱敏后的当前 URL
        @rtype:  str
        """
        try:
            return self._sanitize_url(self._driver.current_url)
        except Exception:
            return ""

    def _visible_body_text(self) -> str:
        """读取当前页面可见文本

        @return: 截断后的页面文本
        @rtype:  str
        """
        try:
            return (self._driver.find_element("tag name", "body").text or "")[:20000]
        except Exception:
            return ""

    def _wait_for_publish_outcome(self, file_name: str) -> PublishOutcome:
        """等待发布成功、失败或超时状态

        @param file_name: 当前文章名称
        @type  file_name: str
        @return: 发布结果
        @rtype:  PublishOutcome
        """
        deadline = time.monotonic() + _PUBLISH_RESULT_TIMEOUT_SECONDS
        success_streak = 0
        failure_keywords = (
            "发布失败",
            "保存失败",
            "标题不能为空",
            "内容不能为空",
            "请输入标题",
            "请输入正文",
            "网络异常",
            "请求失败",
            "请稍后重试",
        )

        while time.monotonic() < deadline:
            current_url = self._driver.current_url
            if self._is_login_url(current_url):
                return PublishOutcome(
                    success=False,
                    message="最终发布后页面跳转到登录页，登录会话可能已失效。",
                    stage="verify_result",
                    retry_safe=False,
                    final_submit_clicked=True,
                    final_url=self._sanitize_url(current_url),
                )

            page_text = self._visible_body_text()
            for keyword in failure_keywords:
                if keyword in page_text:
                    return PublishOutcome(
                        success=False,
                        message=f"发布后页面提示：{keyword}",
                        stage="verify_result",
                        retry_safe=False,
                        final_submit_clicked=True,
                        final_url=self._safe_current_url(),
                    )

            if "发布成功" in page_text or "审核中" in page_text:
                success_streak += 1
                if success_streak >= 2:
                    self._log("info", {
                        "event": "publish_success",
                        "file": file_name,
                        "message": "发布成功或审核中",
                        "url": self._safe_current_url(),
                    })
                    return PublishOutcome(
                        success=True,
                        message="发布成功或审核中",
                        stage="verify_result",
                        retry_safe=False,
                        final_submit_clicked=True,
                        final_url=self._safe_current_url(),
                    )
            else:
                success_streak = 0
            time.sleep(0.5)

        message = f"等待 {_PUBLISH_RESULT_TIMEOUT_SECONDS} 秒后仍未检测到明确的成功或失败提示。"
        self._log("warning", {
            "event": "publish_result_unknown",
            "file": file_name,
            "url": self._safe_current_url(),
            "reason": message,
        })
        return PublishOutcome(
            success=False,
            message=message,
            stage="verify_result",
            retry_safe=False,
            final_submit_clicked=True,
            final_url=self._safe_current_url(),
        )

    def _upload_single_file(
        self,
        file_path: str,
        personal_category: Optional[str] = None,
    ) -> PublishOutcome:
        """上传单个 Markdown 文件

        @param file_path: Markdown 文件路径
        @type  file_path: str
        @param personal_category: 本批次统一的个人分类
        @type  personal_category: Optional[str]
        @return: 发布结果
        @rtype:  PublishOutcome
        """
        file_name, content = self._load_markdown_file(file_path)

        self._log("info", {"event": "upload_start", "file": file_name})

        stage = "load_publish_page"
        final_submit_clicked = False

        try:
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC

            # 访问发布页面
            self._driver.get(self.PUBLISH_URL)

            # 显式等待标题输入框出现
            stage = "fill_title"
            wait = WebDriverWait(self._driver, 10)
            title_input = wait.until(EC.presence_of_element_located(("xpath", "//*[@id='title']")))
            title_input.clear()
            title_input.send_keys(file_name)

            # 填写正文内容
            stage = "fill_body"
            content_textarea = wait.until(EC.presence_of_element_located(("xpath", "//*[@id='markdownBody']/div[2]/div[1]/div/div/textarea")))
            self._driver.execute_script("arguments[0].value = arguments[1];", content_textarea, content)
            self._driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", content_textarea)

            self._log("info", {"event": "form_filled", "file": file_name})

            # 点击发布文章按钮
            stage = "click_publish"
            publish_button = wait.until(EC.element_to_be_clickable(("xpath", "/html/body/div[1]/div[1]/ul/li[2]/button")))
            publish_button.click()
            self._log("info", {"event": "publish_clicked", "file": file_name})

            # 检查是否出现违禁词弹窗提示框体，若出现则点击"继续发布"按钮
            stage = "handle_prohibited_popup"
            self._handle_prohibited_popup(file_name)

            # 选择文章分类
            stage = "select_category"
            self._select_category(file_name)

            if personal_category:
                stage = "select_personal_category"
                self._select_personal_category(file_name, personal_category)

            # 点击最终发布按钮
            stage = "final_submit"
            release_button = wait.until(EC.element_to_be_clickable(("xpath", "//*[@id='submitForm']")))
            final_submit_clicked = True
            release_button.click()
            self._log("info", {"event": "release_clicked", "file": file_name})

            stage = "verify_result"
            return self._wait_for_publish_outcome(file_name)

        except Exception as e:
            error_msg = str(e)
            self._log("error", {"event": "upload_failed", "file": file_name, "error": error_msg})
            retry_safe = not final_submit_clicked
            if self._is_browser_closed_error(e):
                retry_safe = False
                error_msg = "上传过程中浏览器窗口或 Selenium 会话已失效。"
            try:
                if self._is_login_url(self._driver.current_url):
                    retry_safe = False
                    error_msg = "上传过程中登录会话失效。"
            except Exception:
                pass
            return PublishOutcome(
                success=False,
                message=error_msg,
                stage=stage,
                retry_safe=retry_safe,
                final_submit_clicked=final_submit_clicked,
                final_url=self._safe_current_url(),
            )

    def _handle_prohibited_popup(self, file_name: str) -> None:
        """检查并处理违禁词弹窗提示框体

        当文章内容包含 base64 图片编码时，点击"发布文章"按钮后会弹出违禁词提示框。
        本方法检查该弹窗是否出现，若出现则点击"继续发布"按钮。

        @param file_name: 当前处理的文件名称（用于日志）
        @type  file_name: str
        @raises RuntimeError: 检测到弹窗但无法继续发布时抛出
        """
        from selenium.common.exceptions import TimeoutException
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            popups = self._driver.find_elements("xpath", self.PROHIBITED_POPUP_XPATH)
            popup = next((item for item in popups if item.is_displayed()), None)
            if popup is not None:
                self._log("info", {"event": "prohibited_popup_detected", "file": file_name})
                try:
                    wait = WebDriverWait(self._driver, 3)
                    continue_button = wait.until(
                        EC.element_to_be_clickable(("xpath", self.CONTINUE_PUBLISH_XPATH))
                    )
                    continue_button.click()
                    wait.until(EC.invisibility_of_element(popup))
                except Exception as exc:
                    raise RuntimeError(f"违禁词弹窗处理失败: {exc}") from exc
                self._log("info", {"event": "continue_publish_clicked", "file": file_name})
                return

            if self._category_ready_immediately():
                self._log("info", {
                    "event": "no_prohibited_popup",
                    "file": file_name,
                    "reason": "分类区域已就绪",
                })
                return
            time.sleep(0.25)

        self._log("info", {
            "event": "no_prohibited_popup",
            "file": file_name,
            "reason": "等待超时",
        })

    def _category_ready_immediately(self) -> bool:
        """检查分类选择区域是否已经可用

        @return: 分类元素是否可见
        @rtype:  bool
        """
        for xpath in (self.CATEGORY_TEXT_XPATH, self.CATEGORY_FALLBACK_XPATH):
            try:
                elements = self._driver.find_elements("xpath", xpath)
                if any(element.is_displayed() for element in elements):
                    return True
            except Exception:
                continue
        return False

    def _click_element(self, element) -> None:
        """优先执行普通点击，失败时回退到 JavaScript 点击"""
        try:
            element.click()
        except Exception:
            self._driver.execute_script("arguments[0].click();", element)

    def _select_category(self, file_name: str) -> None:
        """选择“代码人生”文章分类

        @param file_name: 当前文章名称
        @type  file_name: str
        @raises RuntimeError: 无法定位或点击分类时抛出
        """
        from selenium.common.exceptions import TimeoutException
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        wait = WebDriverWait(self._driver, 10)
        try:
            category = wait.until(
                EC.presence_of_element_located(("xpath", self.CATEGORY_TEXT_XPATH))
            )
            self._click_element(category)
            self._log("info", {
                "event": "category_selected",
                "file": file_name,
                "selector": "text:代码人生",
            })
            return
        except TimeoutException:
            pass

        try:
            category = wait.until(
                EC.element_to_be_clickable(("xpath", self.CATEGORY_FALLBACK_XPATH))
            )
            self._click_element(category)
            self._log("warning", {
                "event": "category_selected",
                "file": file_name,
                "selector": "fallback:xpath",
            })
        except Exception as exc:
            raise RuntimeError(f"无法选择文章分类“代码人生”: {exc}") from exc

    @staticmethod
    def _normalize_personal_category(personal_category: Optional[str]) -> Optional[str]:
        """规范化个人分类名称

        @param personal_category: 用户指定的个人分类
        @type  personal_category: Optional[str]
        @return: 去除首尾空白后的分类名；未指定时返回 None
        @rtype:  Optional[str]
        """
        if personal_category is None:
            return None
        normalized = personal_category.strip()
        return normalized or None

    def _find_personal_category_options(self, visible_only: bool = True) -> list:
        """查找个人分类下拉框中的选项

        @param visible_only: 是否只返回可见选项
        @type  visible_only: bool
        @return: 下拉选项元素列表
        @rtype:  list
        """
        options = []
        seen_ids = set()
        containers = self._driver.find_elements(
            "css selector",
            self.PERSONAL_CATEGORY_CONTAINER_CSS,
        )
        for container in containers:
            for option in container.find_elements(
                "css selector",
                self.PERSONAL_CATEGORY_OPTION_CSS,
            ):
                if option.id in seen_ids:
                    continue
                seen_ids.add(option.id)
                options.append(option)

        if visible_only:
            options = [option for option in options if option.is_displayed()]
        return options

    def _select_personal_category(self, file_name: str, personal_category: str) -> None:
        """从页面下拉框选择个人分类

        @param file_name: 当前文章名称
        @type  file_name: str
        @param personal_category: 本批次统一的个人分类
        @type  personal_category: str
        @raises RuntimeError: 无法打开下拉框、找不到选项或选择未生效时抛出
        """
        from selenium.common.exceptions import TimeoutException
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        target = self._normalize_personal_category(personal_category)
        if not target:
            return

        wait = WebDriverWait(self._driver, 10)
        try:
            field = wait.until(
                EC.element_to_be_clickable(("id", self.PERSONAL_CATEGORY_FIELD_ID))
            )
            self._driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});",
                field,
            )
            self._click_element(field)
        except Exception as exc:
            raise RuntimeError(f"无法打开个人分类下拉框“{target}”: {exc}") from exc

        option = None
        available_categories = []
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            options = self._find_personal_category_options(visible_only=True)
            available_categories = [
                (item.text or "").strip()
                for item in options
                if (item.text or "").strip()
            ]
            option = next(
                (item for item in options if (item.text or "").strip() == target),
                None,
            )
            if option is not None:
                break
            time.sleep(0.2)

        if option is None:
            if not available_categories:
                available_categories = [
                    (item.text or "").strip()
                    for item in self._find_personal_category_options(visible_only=False)
                    if (item.text or "").strip()
                ]
            available_text = "、".join(sorted(set(available_categories))) or "无"
            raise RuntimeError(
                f"无法选择个人分类“{target}”：下拉框中未找到该选项。"
                f"当前可用分类：{available_text}"
            )

        try:
            self._click_element(option)
            WebDriverWait(self._driver, 5).until(
                lambda _: (field.get_attribute("value") or "").strip() == target
            )
        except TimeoutException as exc:
            actual = (field.get_attribute("value") or "").strip() or "空"
            raise RuntimeError(
                f"个人分类选择未生效：期望“{target}”，当前值为“{actual}”"
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"点击个人分类“{target}”失败: {exc}") from exc

        self._log("info", {
            "event": "personal_category_selected",
            "file": file_name,
            "category": target,
            "selector": f"#{self.PERSONAL_CATEGORY_FIELD_ID}",
        })

    def _click_first_visible(
        self,
        css_selector: str,
        description: str,
        timeout: float = 10,
    ) -> None:
        """点击第一个可见匹配元素

        @param css_selector: CSS 选择器
        @type  css_selector: str
        @param description: 用于错误信息的元素描述
        @type  description: str
        @param timeout: 最长等待秒数
        @type  timeout: float
        @raises PersonalCategoryError: 找不到可见元素时抛出
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for element in self._driver.find_elements("css selector", css_selector):
                try:
                    if not element.is_displayed():
                        continue
                    self._driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});",
                        element,
                    )
                    self._click_element(element)
                    return
                except Exception:
                    continue
            time.sleep(0.2)
        message = f"分类管理页未找到可见的{description}"
        self._log("error", {
            "event": "classify_control_not_found",
            "description": description,
            "selector": css_selector,
        })
        raise PersonalCategoryError(message)

    def _open_classify_page(self) -> None:
        """打开并确认 51CTO 分类管理页可用

        @raises PersonalCategoryError: 页面加载失败或登录会话失效时抛出
        """
        self._driver.get(self.CLASSIFY_URL)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                current_url = self._driver.current_url
            except Exception as exc:
                raise PersonalCategoryError(f"读取分类管理页状态失败：{exc}") from exc

            if self._is_login_url(current_url):
                raise PersonalCategoryError("登录会话已失效，无法读取 51CTO 个人分类。")

            add_buttons = self._driver.find_elements(
                "css selector",
                self.CLASSIFY_ADD_BUTTON_CSS,
            )
            for button in add_buttons:
                try:
                    if button.is_displayed():
                        return
                except Exception:
                    continue
            time.sleep(0.5)

        raise PersonalCategoryError(
            f"分类管理页加载超时：{self._sanitize_url(self._driver.current_url)}"
        )

    def _read_personal_categories(self) -> list[str]:
        """读取分类管理页中已保存的个人分类

        @return: 按页面顺序去重后的分类名称
        @rtype:  list[str]
        """
        values = self._driver.execute_script(r"""
            return Array.from(document.querySelectorAll(arguments[0]))
              .map((element) => (element.value || '').trim())
              .filter(Boolean);
        """, self.CLASSIFY_CATEGORY_INPUT_CSS)
        return list(dict.fromkeys(values))

    def _find_empty_new_category_input(self, timeout: float = 5):
        """查找点击“添加分类”后新增的空分类名输入框

        @param timeout: 最长等待秒数
        @type  timeout: float
        @return: 空分类名输入框元素
        @raises PersonalCategoryError: 未找到新增行时抛出
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            elements = self._driver.find_elements(
                "css selector",
                self.CLASSIFY_NEW_CATEGORY_INPUT_CSS,
            )
            for element in reversed(elements):
                try:
                    if element.is_displayed() and not (element.get_attribute("value") or "").strip():
                        return element
                except Exception:
                    continue
            time.sleep(0.2)
        message = "点击“添加分类”后未出现新的分类名输入框"
        self._log("error", {
            "event": "personal_category_creation_failed",
            "reason": message,
        })
        raise PersonalCategoryError(message)

    def list_personal_categories(self) -> list[str]:
        """登录后实时读取 51CTO 个人分类列表

        @return: 当前个人分类名称列表
        @rtype:  list[str]
        @raises LoginRequiredError: 登录失败时抛出
        @raises PersonalCategoryError: 分类管理页不可用时抛出
        """
        self._check_login_status()
        self._open_classify_page()
        categories = self._read_personal_categories()
        self._log("info", {
            "event": "personal_categories_loaded",
            "count": len(categories),
        })
        return categories

    def _ensure_personal_category_exists(self, personal_category: Optional[str]) -> None:
        """上传前确认个人分类存在，缺失时在分类管理页创建

        @param personal_category: 用户在上传开始前确认的个人分类
        @type  personal_category: Optional[str]
        @raises PersonalCategoryError: 分类读取、创建或保存验证失败时抛出
        """
        target = self._normalize_personal_category(personal_category)
        if not target:
            return

        self._open_classify_page()
        categories = self._read_personal_categories()
        if target in categories:
            self._log("info", {
                "event": "personal_category_already_exists",
                "category": target,
            })
            return

        self._log("info", {
            "event": "personal_category_creation_started",
            "category": target,
        })
        print(f"个人分类“{target}”不存在，正在 51CTO 分类管理页创建...")
        self._click_first_visible(
            self.CLASSIFY_ADD_BUTTON_CSS,
            "“添加分类”按钮",
        )
        field = self._find_empty_new_category_input()
        self._driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});",
            field,
        )
        field.clear()
        field.send_keys(target)
        actual = (field.get_attribute("value") or "").strip()
        if actual != target:
            message = f"个人分类“{target}”填写失败，输入框当前值为“{actual or '空'}”。"
            self._log("error", {
                "event": "personal_category_creation_failed",
                "category": target,
                "reason": message,
            })
            raise PersonalCategoryError(message)

        self._click_first_visible(
            self.CLASSIFY_SAVE_BUTTON_CSS,
            "“保存”按钮",
        )

        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if self._is_login_url(self._driver.current_url):
                message = f"保存个人分类“{target}”时登录会话失效。"
                self._log("error", {
                    "event": "personal_category_creation_failed",
                    "category": target,
                    "reason": message,
                })
                raise PersonalCategoryError(message)
            categories = self._read_personal_categories()
            if target in categories:
                self._log("info", {
                    "event": "personal_category_created",
                    "category": target,
                })
                print(f"个人分类“{target}”创建成功。")
                return
            time.sleep(0.5)

        message = f"个人分类“{target}”保存后未出现在分类列表中，已停止上传。"
        self._log("error", {
            "event": "personal_category_creation_failed",
            "category": target,
            "reason": message,
        })
        raise PersonalCategoryError(message)

    def _manifest_path(self, manifest_path: Optional[str] = None) -> Path:
        """返回重试清单路径"""
        return Path(manifest_path) if manifest_path else _DEFAULT_RETRY_MANIFEST

    def _load_retry_manifest(self, manifest_path: Optional[str] = None) -> list[dict]:
        """读取重试清单

        @param manifest_path: 清单路径
        @type  manifest_path: Optional[str]
        @return: 重试条目列表
        @rtype:  list[dict]
        """
        path = self._manifest_path(manifest_path)
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            entries = data.get("files", [])
            return entries if isinstance(entries, list) else []
        except Exception as exc:
            self._log("warning", {
                "event": "retry_manifest_read_failed",
                "path": str(path),
                "error": str(exc),
            })
            return []

    def _save_retry_manifest(self, entries: list[dict], manifest_path: Optional[str] = None) -> None:
        """保存重试清单；条目为空时删除清单

        @param entries: 重试条目
        @type  entries: list[dict]
        @param manifest_path: 清单路径
        @type  manifest_path: Optional[str]
        """
        path = self._manifest_path(manifest_path)
        if not entries:
            if path.exists():
                path.unlink()
            return

        path.parent.mkdir(parents=True, exist_ok=True)
        now = datetime.now().isoformat()
        existing_created_at = now
        if path.exists():
            try:
                existing_created_at = json.loads(path.read_text(encoding="utf-8")).get("created_at", now)
            except Exception:
                pass
        data = {
            "created_at": existing_created_at,
            "updated_at": now,
            "files": entries,
        }
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(path)

    def _build_retained_entry(
        self,
        file_path: str,
        title: str,
        outcome: PublishOutcome,
        attempts: int,
        personal_category: Optional[str] = None,
    ) -> dict:
        """构建待用户确认的重试条目"""
        return {
            "path": str(Path(file_path).resolve()),
            "title": title,
            "attempts": attempts,
            "stage": outcome.stage,
            "reason": outcome.message,
            "retry_safe": outcome.retry_safe,
            "final_submit_clicked": outcome.final_submit_clicked,
            "final_url": outcome.final_url,
            "personal_category": self._normalize_personal_category(personal_category),
            "updated_at": datetime.now().isoformat(),
        }

    def _merge_retry_manifest(
        self,
        result: UploadResult,
        manifest_path: Optional[str] = None,
    ) -> None:
        """将本次成功和保留文件合并进重试清单"""
        existing = {entry.get("path"): entry for entry in self._load_retry_manifest(manifest_path)}
        for path in result.success_paths:
            existing.pop(path, None)
        for entry in result.retained_files:
            existing[entry["path"]] = entry
        self._save_retry_manifest(list(existing.values()), manifest_path)

    def _upload_batch(
        self,
        files: list[Path],
        max_retries: int,
        personal_category: Optional[str] = None,
    ) -> UploadResult:
        """执行一批文件上传和即时重试"""
        personal_category = self._normalize_personal_category(personal_category)
        result = UploadResult(personal_category=personal_category or "")
        self._check_login_status()
        self._ensure_personal_category_exists(personal_category)
        total_attempts = 1 + max(0, max_retries)

        for file in files:
            file_path = str(file.resolve())
            title = file.stem
            last_outcome = None
            attempts = 0

            for attempt in range(1, total_attempts + 1):
                attempts = attempt
                try:
                    outcome = self._upload_single_file(
                        file_path,
                        personal_category=personal_category,
                    )
                except Exception as exc:
                    outcome = PublishOutcome(
                        success=False,
                        message=str(exc),
                        stage="load_file",
                        retry_safe=False,
                        final_url=self._safe_current_url(),
                    )

                last_outcome = outcome
                if outcome.success:
                    result.success_count += 1
                    result.success_files.append(title)
                    result.success_paths.append(file_path)
                    self._delete_local_file(file_path)
                    break

                if not outcome.retry_safe or attempt >= total_attempts:
                    break

                self._log("warning", {
                    "event": "upload_retry_scheduled",
                    "file": title,
                    "attempt": attempt,
                    "next_attempt": attempt + 1,
                    "stage": outcome.stage,
                    "reason": outcome.message,
                })
                time.sleep(_RETRY_DELAY_SECONDS)

            if last_outcome and last_outcome.success:
                continue

            message = last_outcome.message if last_outcome else "未知上传失败"
            outcome = last_outcome or PublishOutcome(False, message, "unknown", False)
            outcome.attempts = attempts
            result.fail_count += 1
            result.fail_files.append((title, message))
            entry = self._build_retained_entry(
                file_path,
                title,
                outcome,
                attempts,
                personal_category=personal_category,
            )
            result.retained_files.append(entry)
            self._log("warning", {
                "event": "upload_retained_for_user",
                "file": title,
                "attempts": attempts,
                "stage": outcome.stage,
                "retry_safe": outcome.retry_safe,
                "reason": message,
            })

        self._log("info", {
            "event": "batch_upload_complete",
            "success": result.success_count,
            "failed": result.fail_count,
            "retained": len(result.retained_files),
        })
        return result

    def upload_files(
        self,
        file_path: str,
        max_retries: int = _MAX_RETRIES_DEFAULT,
        manifest_path: Optional[str] = None,
        personal_category: Optional[str] = None,
    ) -> UploadResult:
        """上传文件或目录中的所有 Markdown 文件

        @param file_path: 文件或目录路径
        @type  file_path: str
        @param max_retries: 即时重试次数
        @type  max_retries: int
        @param manifest_path: 重试清单路径
        @type  manifest_path: Optional[str]
        @param personal_category: 本批次统一的个人分类
        @type  personal_category: Optional[str]
        @return: 上传结果
        @rtype:  UploadResult
        @raises ValueError: 路径无效时抛出
        @raises Exception: 未登录或浏览器操作失败时抛出
        """
        personal_category = self._normalize_personal_category(personal_category)
        path = Path(file_path)
        if not path.exists():
            raise ValueError(f"路径不存在: {file_path}")

        if path.is_file():
            files = [path]
        elif path.is_dir():
            files = list(path.glob("*.md"))
        else:
            raise ValueError(f"无效的路径: {file_path}")

        if not files:
            self._log("warning", {"event": "no_md_files", "path": str(path)})
            return UploadResult(personal_category=personal_category or "")

        self._log("info", {
            "event": "batch_upload_start",
            "total_files": len(files),
            "max_retries": max(0, max_retries),
            "personal_category": personal_category,
        })
        result = self._upload_batch(
            files,
            max_retries,
            personal_category=personal_category,
        )
        self._merge_retry_manifest(result, manifest_path)
        return result

    def retry_from_manifest(
        self,
        manifest_path: Optional[str] = None,
        personal_category: Optional[str] = None,
    ) -> UploadResult:
        """重传用户确认保留的文件

        @param manifest_path: 重试清单路径
        @type  manifest_path: Optional[str]
        @param personal_category: 可选的新个人分类；未提供时沿用清单中记录的分类
        @type  personal_category: Optional[str]
        @return: 用户确认重传结果
        @rtype:  UploadResult
        """
        entries = self._load_retry_manifest(manifest_path)
        personal_category = self._normalize_personal_category(personal_category)
        if personal_category is None:
            manifest_categories = {
                self._normalize_personal_category(entry.get("personal_category"))
                for entry in entries
            }
            manifest_categories.discard(None)
            if len(manifest_categories) > 1:
                categories = "、".join(sorted(manifest_categories))
                raise ValueError(
                    "重试清单包含多个个人分类"
                    f"（{categories}），请使用 --personal-category 指定一个分类"
                )
            if manifest_categories:
                personal_category = next(iter(manifest_categories))

        files = []
        missing_paths = []
        for entry in entries:
            path = Path(str(entry.get("path", "")))
            if path.is_file():
                files.append(path)
            else:
                missing_paths.append(str(path))

        if missing_paths:
            self._log("warning", {
                "event": "retry_files_missing",
                "paths": missing_paths,
            })
        if not files:
            self._save_retry_manifest([], manifest_path)
            return UploadResult(personal_category=personal_category or "")

        result = self._upload_batch(
            files,
            max_retries=0,
            personal_category=personal_category,
        )
        self._save_retry_manifest(result.retained_files, manifest_path)
        return result

    def discard_retry_manifest(self, manifest_path: Optional[str] = None) -> dict:
        """删除用户拒绝重传的保留文件

        @param manifest_path: 重试清单路径
        @type  manifest_path: Optional[str]
        @return: 删除统计
        @rtype:  dict
        """
        entries = self._load_retry_manifest(manifest_path)
        deleted = []
        missing = []
        remaining = []
        for entry in entries:
            path = Path(str(entry.get("path", "")))
            try:
                if path.is_file():
                    path.unlink()
                    deleted.append(str(path))
                else:
                    missing.append(str(path))
            except Exception as exc:
                remaining.append(entry)
                self._log("warning", {
                    "event": "retained_file_delete_failed",
                    "path": str(path),
                    "error": str(exc),
                })
        self._save_retry_manifest(remaining, manifest_path)
        return {"deleted": deleted, "missing": missing, "remaining": remaining}

    def cleanup(self) -> None:
        """清理资源，关闭浏览器"""
        if self._browser is None and self._driver is None:
            return

        try:
            if self._driver:
                service = getattr(self._driver, "service", None)
                driver_process = getattr(service, "process", None)

                # 尝试正常退出，如果超时就强制终止
                import threading
                quit_thread = threading.Thread(target=lambda: self._driver.quit() if self._driver else None)
                quit_thread.daemon = True
                quit_thread.start()
                quit_thread.join(timeout=10)
                if quit_thread.is_alive():
                    self._force_terminate_driver_process(driver_process)
        except Exception as e:
            self._log("warning", {"event": "driver_quit_error", "error": str(e)})
        finally:
            self._browser = None
            self._driver = None

    def _force_terminate_driver_process(self, process) -> None:
        """强制终止当前会话的 ChromeDriver 子进程

        @param process: Selenium 启动的 ChromeDriver Popen 对象
        @type  process: subprocess.Popen | None
        """
        if process is None:
            self._log("warning", {
                "event": "driver_process_unavailable",
                "reason": "无法获取当前 ChromeDriver 子进程",
            })
            return

        pid = getattr(process, "pid", None)
        try:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
            self._log("warning", {
                "event": "driver_process_force_terminated",
                "pid": pid,
            })
        except Exception as exc:
            self._log("warning", {
                "event": "driver_process_terminate_failed",
                "pid": pid,
                "error": str(exc),
            })


FORMAT = "%(asctime)s [%(levelname)s] %(funcName)s:%(lineno)d %(message)s"


def setup_logging(log_file: str = None) -> logging.Logger:
    """配置日志系统

    @param log_file: 日志文件路径，默认保存在项目根目录的 logs 目录中
    @type  log_file: str
    @return: 配置好的日志记录器
    @rtype:  logging.Logger
    """
    logger = logging.getLogger("51cto_uploader")
    logger.setLevel(logging.DEBUG)

    if log_file is None:
        log_file = _DEFAULT_LOG_DIR / "51cto_uploader.log"

    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    rotating_handler = logging.handlers.TimedRotatingFileHandler(
        log_file,
        when="midnight",
        interval=1,
        backupCount=7,
        encoding="utf-8"
    )
    rotating_handler.setLevel(logging.DEBUG)
    rotating_handler.setFormatter(logging.Formatter(FORMAT, datefmt="%Y-%m-%d %H:%M:%S"))

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(
        logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
    )

    logger.addHandler(rotating_handler)
    logger.addHandler(console_handler)

    return logger


def parse_arguments() -> argparse.Namespace:
    """解析命令行参数

    @return: 解析后的命令行参数对象
    @rtype:  argparse.Namespace
    """
    parser = argparse.ArgumentParser(
        description="51CTO 博客批量上传工具 - 将本地 Markdown 文件发布到 51CTO 博客"
    )

    parser.add_argument(
        "path",
        nargs="?",
        type=str,
        help="要上传的 Markdown 文件路径或包含多个 Markdown 文件的目录路径"
    )

    parser.add_argument(
        "--retry-manifest",
        nargs="?",
        const=str(_DEFAULT_RETRY_MANIFEST),
        default=None,
        help="重传清单路径；不提供值时使用默认清单"
    )

    parser.add_argument(
        "--discard-manifest",
        nargs="?",
        const=str(_DEFAULT_RETRY_MANIFEST),
        default=None,
        help="丢弃重试清单中的保留文件；不提供值时使用默认清单"
    )

    parser.add_argument(
        "--max-retries",
        type=int,
        default=_MAX_RETRIES_DEFAULT,
        help=f"即时重试次数，默认: {_MAX_RETRIES_DEFAULT}"
    )

    parser.add_argument(
        "--personal-category",
        type=str,
        default=None,
        help="整批文章统一使用的个人分类名称；不提供时不修改个人分类"
    )

    parser.add_argument(
        "--list-personal-categories",
        action="store_true",
        help="登录后只读取并输出个人分类列表，不上传文件"
    )

    parser.add_argument(
        "-l", "--log",
        default=None,
        help="日志文件路径, 默认: 项目根目录下的 logs 目录"
    )

    args = parser.parse_args()
    selected_modes = sum([
        bool(args.path),
        args.retry_manifest is not None,
        args.discard_manifest is not None,
        args.list_personal_categories,
    ])
    if selected_modes != 1:
        parser.error(
            "必须且只能提供 path、--retry-manifest、--discard-manifest、"
            "--list-personal-categories 中的一种"
        )
    if args.max_retries < 0:
        parser.error("--max-retries 不能小于 0")
    if args.personal_category is not None:
        args.personal_category = args.personal_category.strip()
        if not args.personal_category:
            parser.error("--personal-category 不能为空")
        if args.list_personal_categories:
            parser.error("--list-personal-categories 不能与 --personal-category 同时使用")
    return args


def print_personal_categories(categories: list[str]) -> None:
    """打印个人分类列表

    @param categories: 当前个人分类名称
    @type  categories: list[str]
    """
    print("\n" + "=" * 50)
    print("51CTO 个人分类列表")
    print("=" * 50)
    if categories:
        print(f"当前共 {len(categories)} 个个人分类：")
        for category in categories:
            print(f"  - {category}")
    else:
        print("当前没有个人分类。")
    print("\n请由用户明确选择：")
    print("  - 使用上方一个已有分类")
    print("  - 输入一个新分类名称")
    print("  - 不设置个人分类")
    print("=" * 50)


def print_upload_summary(result: UploadResult, manifest_path: Optional[str] = None) -> None:
    """打印上传结果汇总

    @param result: 上传结果
    @type  result: UploadResult
    @param manifest_path: 重试清单路径
    @type  manifest_path: Optional[str]
    """
    print("\n" + "=" * 50)
    print("上传结果汇总")
    print("=" * 50)
    print(f"成功: {result.success_count} 篇")
    print(f"失败: {result.fail_count} 篇")
    print(f"个人分类: {result.personal_category or '未指定'}")

    if result.success_files:
        print("\n成功列表:")
        for name in result.success_files:
            print(f"  - {name}")

    if result.fail_files:
        print("\n失败列表:")
        for name, reason in result.fail_files:
            print(f"  - {name}: {reason}")

    if result.retained_files:
        print("\n暂时保留的文件:")
        for entry in result.retained_files:
            print(f"  - {entry['title']}")
            print(f"    路径: {entry['path']}")
            print(f"    尝试次数: {entry['attempts']}")
            print(f"    失败阶段: {entry['stage']}")
            print(f"    原因: {entry['reason']}")
        print(f"\n重试清单: {manifest_path or _DEFAULT_RETRY_MANIFEST}")
        print("请向用户确认是否重传这些文件；用户拒绝后再删除保留文件。")

    print("\n请访问 51CTO 博客用户中心查看:")
    print("https://blog.51cto.com/creative-center/manager")
    print("=" * 50)


def print_discard_summary(stats: dict) -> None:
    """打印保留文件清理结果

    @param stats: 清理统计
    @type  stats: dict
    """
    print("\n" + "=" * 50)
    print("保留文件清理结果")
    print("=" * 50)
    print(f"已删除: {len(stats.get('deleted', []))} 篇")
    print(f"文件不存在: {len(stats.get('missing', []))} 篇")
    print(f"删除失败: {len(stats.get('remaining', []))} 篇")
    for path in stats.get("deleted", []):
        print(f"  - 已删除: {path}")
    for entry in stats.get("remaining", []):
        print(f"  - 删除失败: {entry.get('path', '')}")
    print("=" * 50)


def print_login_notice() -> None:
    """打印 51CTO 登录提示"""
    print("=" * 50)
    print("请事先在浏览器中完成 51CTO 博客的用户登陆操作")
    print("读取个人分类或上传文章需要有效登录；如需登录，请在打开的 Chrome 中完成操作。")
    print("=" * 50)
    print()


def main() -> int:
    """主入口函数

    @return: 程序退出码，0 表示成功，非 0 表示有错误
    @rtype:  int
    """
    try:
        args = parse_arguments()
        logger = setup_logging(args.log)

        if args.discard_manifest is not None:
            uploader = C51ctoUploader(logger)
            try:
                stats = uploader.discard_retry_manifest(args.discard_manifest)
                print_discard_summary(stats)
                return 0 if not stats.get("remaining") else 1
            finally:
                uploader.cleanup()

        if args.list_personal_categories:
            logger.info("开始读取 51CTO 个人分类列表")
            print_login_notice()
            uploader = C51ctoUploader(logger)
            try:
                categories = uploader.list_personal_categories()
                print_personal_categories(categories)
                return 0
            finally:
                uploader.cleanup()

        target = args.path if args.path else args.retry_manifest
        logger.info(f"开始 51CTO 博客上传任务: {target}")

        print_login_notice()

        uploader = C51ctoUploader(logger)

        try:
            if args.retry_manifest is not None:
                result = uploader.retry_from_manifest(
                    args.retry_manifest,
                    personal_category=args.personal_category,
                )
                manifest_path = args.retry_manifest
            else:
                result = uploader.upload_files(
                    args.path,
                    max_retries=args.max_retries,
                    personal_category=args.personal_category,
                )
                manifest_path = str(_DEFAULT_RETRY_MANIFEST)
            print_upload_summary(result, manifest_path)

            if result.fail_count > 0:
                return 1
            return 0

        finally:
            uploader.cleanup()

    except LoginRequiredError as e:
        print(f"\n{e.failure.format_for_user()}", file=sys.stderr)
        return 1

    except PersonalCategoryError as e:
        print(f"\n个人分类处理失败: {e}", file=sys.stderr)
        return 1

    except ValueError as e:
        print(f"\n参数错误: {e}", file=sys.stderr)
        print("使用 --help 查看帮助信息", file=sys.stderr)
        return 2

    except KeyboardInterrupt:
        print("\n\n操作已取消", file=sys.stderr)
        return 130

    except Exception as e:
        print(f"\n未知错误: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
