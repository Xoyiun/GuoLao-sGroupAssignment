"""專案測試驅動程式。

在專案根目錄執行 ``python TestDriver.py`` 即可執行整個測試套件；
額外參數會原樣傳給 pytest，例如 ``python TestDriver.py -m normal``。
"""

from __future__ import annotations

import sys

import pytest


def main(arguments: list[str] | None = None) -> int:
    """執行根目錄下的測試並回傳 pytest 結果碼。"""
    pytest_arguments = ["-q"] if arguments is None else arguments
    return pytest.main(pytest_arguments)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or None))
