#!/usr/bin/env python3
"""
51CTO 博客批量上传工具

该脚本用于将本地 Markdown 格式文件批量发布到 51CTO 博客网站。
支持单个文件或目录批量上传，使用 Selenium 操作浏览器完成自动化发布。
"""

import argparse
import logging
import logging.handlers
import os
import sys
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class UploadResult:
    """上传结果数据类"""

    success_count: int = 0
    fail_count: int = 0
    success_files: list[str] = field(default_factory=list)
    fail_files: list[tuple[str, str]] = field(default_factory=list)


class ChromeDriverManager:
    """Chrome 浏览器驱动管理器"""

    def __init__(self, driver_dir: str = "51cto_uploader/drivers/chromedriver-mac-x64"):
        """初始化 Chrome 驱动管理器

        @param driver_dir: Chrome driver 所在目录
        @type  driver_dir: str
        """
        self.driver_dir = Path(driver_dir)
        self._driver = None

    def get_driver_path(self) -> Optional[str]:
        """获取 Chrome driver 路径

        @return: Chrome driver 路径，不存在则返回 None
        @rtype:  Optional[str]
        """
        # 查找 chromedriver 可执行文件
        for name in ["chromedriver", "chromedriver.exe"]:
            driver_path = self.driver_dir / name
            if driver_path.exists():
                os.chmod(str(driver_path), 0o755)
                return str(driver_path)
        return None


class BrowserAutomation:
    """浏览器自动化操作类"""

    def __init__(self, driver_path: Optional[str] = None):
        """初始化浏览器自动化

        @param driver_path: Chrome driver 路径
        @type  driver_path: Optional[str]
        @raises ImportError: Selenium 未安装时抛出
        @raises FileNotFoundError: Chrome driver 不存在时抛出
        """
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
        except ImportError:
            raise ImportError("请安装 selenium: pip install selenium")

        self._webdriver = webdriver
        self._Service = Service
        self._Options = Options
        self._driver_path = driver_path
        self._driver = None

    def setup_driver(self) -> "webdriver.Chrome":
        """设置并返回 Chrome 驱动

        @return: Chrome WebDriver 实例
        @rtype:  webdriver.Chrome
        """
        options = self._Options()
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-infobars")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        # 使用专门为 Selenium 创建的 Chrome 用户数据目录
        # 这个目录会在首次登录后保存 Cookie，下次运行时无需重新登录
        selenium_profile_dir = os.path.expanduser("~/Library/Application Support/Google/Chrome/SeleniumProfile")
        options.add_argument(f"--user-data-dir={selenium_profile_dir}")

        if self._driver_path:
            service = self._Service(executable_path=self._driver_path)
            self._driver = self._webdriver.Chrome(service=service, options=options)
        else:
            self._driver = self._webdriver.Chrome(options=options)

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

    # 页面 URL 配置
    LOGIN_CHECK_URL = "https://blog.51cto.com/creative-center/manager"
    PUBLISH_URL = "https://blog.51cto.com/blogger/publish"

    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        driver_dir: str = "51cto_uploader/drivers/chromedriver-mac-x64"
    ):
        """初始化 51CTO 上传器

        @param logger: 日志记录器
        @type  logger: Optional[logging.Logger]
        @param driver_dir: Chrome driver 目录
        @type  driver_dir: str
        """
        self.logger = logger
        self.driver_dir = driver_dir
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

    def _get_browser(self) -> BrowserAutomation:
        """获取浏览器自动化实例

        @return: 浏览器自动化实例
        @rtype:  BrowserAutomation
        """
        if self._browser is None:
            driver_manager = ChromeDriverManager(self.driver_dir)
            driver_path = driver_manager.get_driver_path()
            self._browser = BrowserAutomation(driver_path)
        return self._browser

    def _check_login_status(self) -> bool:
        """检查用户是否已登录 51CTO

        @return: 已登录返回 True，未登录返回 False
        @rtype:  bool
        @raises Exception: 浏览器操作失败时抛出
        """
        self._log("info", {"event": "check_login_start"})

        browser = self._get_browser()
        self._driver = browser.setup_driver()

        try:
            self._driver.get(self.LOGIN_CHECK_URL)
            self._driver.implicitly_wait(5)

            current_url = self._driver.current_url
            self._log("info", {"event": "page_loaded", "url": current_url})

            # 检查是否跳转到登录页（home.51cto.com/index）
            if current_url.startswith("https://home.51cto.com/index") or "login" in current_url.lower():
                self._log("warning", {"event": "not_logged_in", "url": current_url})

                # 等待用户手动登录，最多等待60秒
                print("\n请在浏览器中完成 51CTO 博客的登录操作...")
                print("等待登录完成（最多60秒）...")

                import time
                start_time = time.time()
                while time.time() - start_time < 60:
                    current_url = self._driver.current_url
                    if not current_url.startswith("https://home.51cto.com/index"):
                        # 已跳转到非登录页，登录可能已完成
                        try:
                            self._driver.find_element("css selector", 'a.want-write')
                            self._log("info", {"event": "login_verified_after_wait"})
                            print("检测到登录成功！")
                            return True
                        except Exception:
                            pass

                    if "creative-center" in current_url and "manager" in current_url:
                        self._log("info", {"event": "login_verified_after_wait", "url": current_url})
                        print("检测到登录成功！")
                        return True

                    time.sleep(2)

                self._log("warning", {"event": "login_timeout"})

            # 检查是否存在已登录标识：写文章链接
            try:
                self._driver.find_element("css selector", 'a.want-write')
                self._log("info", {"event": "login_verified", "reason": "found_want_write_link"})
                return True
            except Exception as e:
                self._log("info", {"event": "want_write_not_found", "error": str(e)})

            # 检查 URL 是否在用户中心
            if "creative-center" in current_url and "manager" in current_url:
                self._log("info", {"event": "login_verified", "reason": "url_match"})
                return True

            # 最终判断：未找到登录标识
            self._log("warning", {"event": "not_logged_in", "reason": "no_login_indicator", "url": current_url})
            return False

        except Exception as e:
            self._log("error", {"event": "check_login_failed", "error": str(e)})
            raise

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

    def _upload_single_file(self, file_path: str) -> tuple[bool, str]:
        """上传单个 Markdown 文件

        @param file_path: Markdown 文件路径
        @type  file_path: str
        @return: (是否成功, 失败原因或成功信息)
        @rtype:  tuple[bool, str]
        @raises Exception: 上传过程发生错误时抛出
        """
        file_name, content = self._load_markdown_file(file_path)

        self._log("info", {"event": "upload_start", "file": file_name})

        try:
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC

            # 访问发布页面
            self._driver.get(self.PUBLISH_URL)

            # 显式等待标题输入框出现
            wait = WebDriverWait(self._driver, 10)
            title_input = wait.until(EC.presence_of_element_located(("xpath", "//*[@id='title']")))
            title_input.clear()
            title_input.send_keys(file_name)

            # 填写正文内容
            content_textarea = wait.until(EC.presence_of_element_located(("xpath", "//*[@id='markdownBody']/div[2]/div[1]/div/div/textarea")))
            self._driver.execute_script("arguments[0].value = arguments[1];", content_textarea, content)
            self._driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", content_textarea)

            self._log("info", {"event": "form_filled", "file": file_name})

            # 点击发布文章按钮
            publish_button = wait.until(EC.element_to_be_clickable(("xpath", "/html/body/div[1]/div[1]/ul/li[2]/button")))
            publish_button.click()
            self._log("info", {"event": "publish_clicked", "file": file_name})

            # 选择文章分类
            category = wait.until(EC.element_to_be_clickable(("xpath", "//*[@id='oneLever']/div[22]")))
            category.click()
            self._log("info", {"event": "category_selected", "file": file_name})

            # 点击最终发布按钮
            release_button = wait.until(EC.element_to_be_clickable(("xpath", "//*[@id='submitForm']")))
            release_button.click()
            self._log("info", {"event": "release_clicked", "file": file_name})

            # 等待页面响应
            self._driver.implicitly_wait(5)

            # 检查是否发布成功
            # 根据 XPath 检查成功提示元素: //*[@id="__layout"]/div/div[2]/div/div[1]/span
            try:
                success_element = self._driver.find_element("xpath", "//*[@id='__layout']/div/div[2]/div/div[1]/span")
                success_text = success_element.text
                if "发布成功" in success_text or "审核中" in success_text:
                    self._log("info", {"event": "publish_success", "file": file_name, "message": success_text})
                    return True, ""
            except Exception:
                pass

            # 备用检查：检查页面源码中是否包含成功标识
            page_source = self._driver.page_source
            if "success-word" in page_source and "发布成功" in page_source:
                self._log("info", {"event": "publish_success", "file": file_name})
                return True, ""

            error_msg = "发布后未检测到成功提示"
            self._log("warning", {"event": "publish_failed", "file": file_name, "reason": error_msg})
            return False, error_msg

        except Exception as e:
            error_msg = str(e)
            self._log("error", {"event": "upload_failed", "file": file_name, "error": error_msg})
            return False, error_msg

    def upload_files(self, file_path: str) -> UploadResult:
        """上传文件或目录中的所有 Markdown 文件

        @param file_path: 文件或目录路径
        @type  file_path: str
        @return: 上传结果
        @rtype:  UploadResult
        @raises ValueError: 路径无效时抛出
        @raises Exception: 未登录或浏览器操作失败时抛出
        """
        path = Path(file_path)
        if not path.exists():
            raise ValueError(f"路径不存在: {file_path}")

        result = UploadResult()

        # 确定要上传的文件列表
        if path.is_file():
            files = [path]
        elif path.is_dir():
            files = list(path.glob("*.md"))
        else:
            raise ValueError(f"无效的路径: {file_path}")

        if not files:
            self._log("warning", {"event": "no_md_files", "path": str(path)})
            return result

        self._log("info", {"event": "batch_upload_start", "total_files": len(files)})

        # 检查登录状态
        if not self._check_login_status():
            raise Exception("用户未登录 51CTO博客，请先在浏览器中完成登录操作，然后重新运行程序")

        # 逐个上传文件
        for file in files:
            try:
                success, msg = self._upload_single_file(str(file))
                if success:
                    result.success_count += 1
                    result.success_files.append(file.stem)
                else:
                    result.fail_count += 1
                    result.fail_files.append((file.stem, msg))
            except Exception as e:
                result.fail_count += 1
                result.fail_files.append((file.stem, str(e)))
                self._log("error", {"event": "upload_exception", "file": file.stem, "error": str(e)})
                # 发生异常时记录错误，继续处理下一个文件
                continue

        self._log("info", {
            "event": "batch_upload_complete",
            "success": result.success_count,
            "failed": result.fail_count
        })

        return result

    def cleanup(self) -> None:
        """清理资源，关闭浏览器"""
        if self._browser is None and self._driver is None:
            return

        try:
            if self._driver:
                def forceQuit():
                    import subprocess
                    # 获取 chromedriver 进程 ID 并强制终止
                    try:
                        subprocess.run(['pkill', '-f', 'chromedriver'], timeout=5)
                    except:
                        pass

                # 尝试正常退出，如果超时就强制终止
                import threading
                quit_thread = threading.Thread(target=lambda: self._driver.quit() if self._driver else None)
                quit_thread.daemon = True
                quit_thread.start()
                quit_thread.join(timeout=10)
                if quit_thread.is_alive():
                    forceQuit()
                    self._log("warning", {"event": "driver_force_quit"})
        except Exception as e:
            self._log("warning", {"event": "driver_quit_error", "error": str(e)})
        finally:
            self._browser = None
            self._driver = None


FORMAT = "%(asctime)s [%(levelname)s] %(funcName)s:%(lineno)d %(message)s"


def setup_logging(log_file: str = "logs/51cto_uploader.log") -> logging.Logger:
    """配置日志系统

    @param log_file: 日志文件路径，默认保存在项目根目录的 logs 目录
    @type  log_file: str
    @return: 配置好的日志记录器
    @rtype:  logging.Logger
    """
    logger = logging.getLogger("51cto_uploader")
    logger.setLevel(logging.DEBUG)

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
        type=str,
        help="要上传的 Markdown 文件路径或包含多个 Markdown 文件的目录路径"
    )

    parser.add_argument(
        "-l", "--log",
        default="logs/51cto_uploader.log",
        help="日志文件路径, 默认: logs/51cto_uploader.log"
    )

    parser.add_argument(
        "--driver-dir",
        default="51cto_uploader/drivers/chromedriver-mac-x64",
        help="Chrome driver 目录, 默认: 51cto_uploader/drivers/chromedriver-mac-x64"
    )

    return parser.parse_args()


def print_upload_summary(result: UploadResult) -> None:
    """打印上传结果汇总

    @param result: 上传结果
    @type  result: UploadResult
    """
    print("\n" + "=" * 50)
    print("上传结果汇总")
    print("=" * 50)
    print(f"成功: {result.success_count} 篇")
    print(f"失败: {result.fail_count} 篇")

    if result.success_files:
        print("\n成功列表:")
        for name in result.success_files:
            print(f"  - {name}")

    if result.fail_files:
        print("\n失败列表:")
        for name, reason in result.fail_files:
            print(f"  - {name}: {reason}")

    print("\n请访问 51CTO 博客用户中心查看:")
    print("https://blog.51cto.com/creative-center/manager")
    print("=" * 50)


def main() -> int:
    """主入口函数

    @return: 程序退出码，0 表示成功，非 0 表示有错误
    @rtype:  int
    """
    try:
        args = parse_arguments()
        logger = setup_logging(args.log)

        logger.info(f"开始 51CTO 博客上传任务: {args.path}")

        # 打印登录提示
        print("=" * 50)
        print("请事先在浏览器中完成 51CTO 博客的用户登陆操作")
        print("=" * 50)
        print()

        uploader = C51ctoUploader(logger, args.driver_dir)

        try:
            result = uploader.upload_files(args.path)
            print_upload_summary(result)

            if result.fail_count > 0:
                return 1
            return 0

        finally:
            uploader.cleanup()

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
