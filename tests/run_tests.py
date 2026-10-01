"""不依赖 pytest 的测试运行器。

    python tests/run_tests.py            # 跑全部
    python tests/run_tests.py test_xxx   # 只跑名字里含 test_xxx 的

⚠️ 为什么有它：§十七 同时要求「纯标准库」与「pytest」，而本机没有 pytest。
两条只能靠「同一批断言、两个入口」同时满足 —— 测试文件全部是纯
`def test_*()` + `assert`，pytest 能收集，这里也能跑。
**用 fixture / parametrize 就绑死在 pytest 上了，而「跑测试要先装东西」正是要避开的。**
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    filt = args[0] if args else None

    import test_dce
    names = [n for n in dir(test_dce) if n.startswith("test_")]
    names.sort(key=lambda n: getattr(test_dce, n).__code__.co_firstlineno)

    print("DCE 测试\n")
    passed, failed = 0, []
    for n in names:
        if filt and filt not in n:
            continue
        fn = getattr(test_dce, n)
        try:
            fn()
            passed += 1
            print(f"  过     {n}")
        except Exception as e:                       # noqa: BLE001
            failed.append((n, e))
            print(f"  **红的** {n}\n           {type(e).__name__}: {e}")
            if "-v" in args:
                traceback.print_exc()

    print(f"\n共 {passed + len(failed)} 条：过 {passed}，红 {len(failed)}")
    print(f"退出码 {1 if failed else 0}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
