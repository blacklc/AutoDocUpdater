#!/usr/bin/env python3
"""检查 LLM 环境变量配置"""

import json
import sys
from pathlib import Path


_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from env_config import check_environment, format_environment_status


def main() -> int:
    """执行环境变量预检

    @return: 0 表示配置完整，2 表示需要配置
    @rtype:  int
    """
    status = check_environment()
    print(format_environment_status(status))
    print("\nJSON:")
    print(json.dumps(status.to_dict(), ensure_ascii=False, indent=2))
    return 0 if status.configured else 2


if __name__ == "__main__":
    sys.exit(main())
