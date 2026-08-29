#!/usr/bin/env python3
"""提供 Capture note plan 校验的公开 CLI;转交同 Skill 内部契约绑定实现使用."""
import sys
from pathlib import Path

SRC = Path(__file__).resolve(strict=True).parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
from validate_note_plan import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
