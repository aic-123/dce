"""DCE 的检查与四组测试。

跑法：

    python -m checks            # 全部
    python -m checks identity   # 只跑某一组

每一组返回 `[(名字, 通过与否, 说明)]`。**说明里必须带数字** ——
「通过」两字不含信息，而一个只打印「通过」的检查，读者没法判断它是不是空转的。

⚠️ 退出码只反映**断言**的结果。四组测试里有几项是**度量**（恢复率、覆盖率、
压缩比），它们有数字但不该有「过/不过」——那些走 `report()`，不进退出码。
把度量做成门禁就会诱人去压那个数，而 `§T0.3` 写着「没有基线数据的阈值一律是拍脑袋」。
"""

from __future__ import annotations

import sys

# 四组测试。后三组是「度量」性质的，走 report()，不进退出码。
# `scope` 是 §二十 排除项的可执行形式，也是断言。
# `corpus` 是**反例扫描**：把每条结论拿到一整片配置上撞一遍。
ASSERT_GROUPS = ("identity", "interference", "scope", "boundary", "realdata",
                 "positions", "radius", "beta", "approximation", "focus",
                 "concepts", "nullmodel", "consensus")
MEASURE_GROUPS = ("reconstruction", "ablation", "corpus")


def _print_asserts(mod, counters):
    """`ok` 有三态：True 过 / False 红 / **None 跳过**。

    ⚠️ 跳过必须**单独计数**，不能混进「过」。一个「语料不在就静默通过」的检查
    与一条永远通过的检查在输出上长得一样 —— 这一整轮已经在这上面栽过两次：
    runner 从不调用度量组、adapter 空输出通过全部边界检查。
    """
    total, failed, skipped = counters
    for title, ok, detail in mod.run_all():
        if ok is None:
            skipped += 1
            print(f"  跳过   {title:<40} {detail}")
            continue
        total += 1
        if not ok:
            failed += 1
        print(f"  {'过    ' if ok else '**红的**'} {title:<40} {detail}")
    return total, failed, skipped


def _load(name):
    try:
        return __import__(f"checks.{name}", fromlist=["run_all", "report"])
    except ModuleNotFoundError as e:
        if name in str(e):
            return None
        raise


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    want = args[0] if args else None

    print("DCE · 检查与四组测试（§十五 / §十六）\n")
    total = failed = skipped = 0

    for name in ASSERT_GROUPS:
        if want and want != name:
            continue
        mod = _load(name)
        if mod is None:
            continue
        print(f"── {name} ──")
        total, failed, skipped = _print_asserts(mod, (total, failed, skipped))
        print()

    # ⚠️ 度量组**也有断言**（例如 Test 3 的「每条记录过定义校验」）。
    # 第一版把度量组整个跳过 run_all()，于是那两条断言从来没跑过 ——
    # 而输出照样打印「断言 14 条，红 0 条」。**一个从不执行的检查，
    # 和一条永远通过的检查，在输出上长得一模一样。**
    for name in MEASURE_GROUPS:
        if want and want != name:
            continue
        mod = _load(name)
        if mod is None:
            continue
        if hasattr(mod, "run_all"):
            print(f"── {name} · 断言 ──")
            total, failed, skipped = _print_asserts(mod, (total, failed, skipped))
            print()
        if hasattr(mod, "report"):
            print(f"── {name} · 度量（不进退出码）──")
            for title, value in mod.report():
                print(f"  {title:<40} {value}")
            print()

    print(f"断言 {total} 条，红 {failed} 条，跳过 {skipped} 条")
    if skipped:
        print(f"⚠️ **跳过不等于通过** —— 那 {skipped} 条这次没有被验证。")
    print(f"退出码 {1 if failed else 0}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
