#!/usr/bin/env python3
"""提供 Windows 安装根预检的公开 CLI;转交同 Skill 内部安全探测实现使用."""
import sys
from pathlib import Path

SRC = Path(__file__).resolve(strict=True).parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
from check_install_roots import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
