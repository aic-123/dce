"""β 分解的检查 —— **定理用精确有理数穷尽验证，实现按声明容差对齐。**

---
这一层守的两条
-------------

一、**定理必须穷尽验证，不能靠几个例子。** `analysis/beta.py` 声称

       β_sne ≥ 0 恒成立，且 = 0 ⟺ a = 0 或 b = c

   本模块用 `fractions.Fraction` 在 `a, b, c ∈ [0, 20]` 的**全部** 9261 组上
   逐一验证。精确算术、**没有容差** —— 定理对不对与浮点实现准不准是两件事，
   混在一起测就分不清是哪一个错了。

二、**实现按声明的容差对齐。** 浮点实现与精确值比，容许 `1e-12`，
   而那个容差**必须小于**被检验的量级。`field/` 仓库在这上面栽过一次：
   容差 `1e-9` 超过了方法精度（实测偏差 4.071e-07），于是检查红得没有意义。

---
四类差异落在两个轴上：这一条是**可数值检验**的
-------------------------------------------

    consensus        →  β_总 = 0
    alternative / 矛盾 →  **纯周转**（β_sne = 0）
    refinement / 缺失  →  **纯嵌套或混合**（β_sne > 0），方向看 b−c 的符号
"""

from __future__ import annotations

from fractions import Fraction

from analysis import beta as B

TOL = 1e-12          # 浮点实现的容差，**声明在此**，不小到无意义也不大到能藏错


def _exact(a: int, b: int, c: int) -> tuple:
    """用精确有理数算 Sørensen 族的三值。"""
    total = Fraction(b + c, 2 * a + b + c) if (2 * a + b + c) else Fraction(0)
    m = min(b, c)
    turn = Fraction(m, a + m) if (a + m) else Fraction(0)
    return total, turn, total - turn


def run_all() -> list:
    out = []

    # ① 定理：β_sne ≥ 0，且 = 0 ⟺ b=c 或 (a=0 且 min(b,c)>0)。**穷尽**，精确算术。
    #
    # ⚠️ 等价式的右半边**改过一次**。第一版写的是「a = 0 或 b = c」，
    # 穷尽验证报出 **40 组反例**，全是 `a = 0 且 min(b,c) = 0`
    # —— 也就是**其中一个视图是空的**。那时 β_嵌套 = 1，
    # 而**那是对的**：空集是任何集合的子集，「一个视图什么都没有」
    # 是极端的嵌套，不是周转。**错的是我的定理陈述，不是代码。**
    #
    # 这个反例的形状与本仓库先前栽过的那次一样（空视图被当成精炼的粗侧）
    # —— 在 β 分解里它自动落在正确的一侧，不需要额外的特例。
    bad_neg, bad_iff = [], []
    n = 0
    for a in range(21):
        for b in range(21):
            for c in range(21):
                n += 1
                _t, _tu, ne = _exact(a, b, c)
                if ne < 0:
                    bad_neg.append((a, b, c, ne))
                pure_turnover = (b == c) or (a == 0 and min(b, c) > 0)
                if (ne == 0) != pure_turnover:
                    bad_iff.append((a, b, c, ne))
    out.append((f"定理：β_嵌套 ≥ 0（{n} 组穷尽，精确有理数、无容差）",
                not bad_neg, f"违反 {len(bad_neg)} 组 {bad_neg[:3]}"))
    out.append((f"定理：β_嵌套 = 0 ⟺ b=c 或 (a=0 且 min>0)（同 {n} 组）",
                not bad_iff,
                f"违反 {len(bad_iff)} 组 {bad_iff[:3]}" if bad_iff else
                "等价关系在全部 9261 组上成立"))

    # ①' 退化情形单列：a=0 且其中一个为空 → **极端嵌套**，β_嵌套 = 1
    degen = []
    for b in range(1, 8):
        for ua, ub in ((set(), {f"u{i}" for i in range(b)}),
                       ({f"u{i}" for i in range(b)}, set())):
            p = B.pairwise(ua, ub)
            degen.append((p["nestedness"], p["turnover"], p["axis"]))
    out.append(("退化情形：空视图 → 极端嵌套（不是周转）",
                all(abs(ne - 1) < TOL and abs(tu) < TOL and ax == "nestedness"
                    for ne, tu, ax in degen),
                f"{degen[:3]} —— 空集是任何集合的子集；"
                "这个形状本仓库先前栽过一次（空视图被当成精炼的粗侧）"))

    # ② 实现与精确值一致（按声明容差）
    worst = 0.0
    for a in range(21):
        for b in range(21):
            for c in range(21):
                ua = {f"x{i}" for i in range(a + b)}
                ub = {f"x{i}" for i in range(a)} | {f"y{i}" for i in range(c)}
                got = B.pairwise(ua, ub)
                t, tu, ne = _exact(a, b, c)
                worst = max(worst, abs(got["total"] - float(t)),
                            abs(got["turnover"] - float(tu)),
                            abs(got["nestedness"] - float(ne)))
    out.append((f"浮点实现与精确值一致（容差 {TOL:g}）",
                worst < TOL,
                f"最大偏差 {worst:.3e}（容差 {TOL:g}，"
                f"比偏差大 {TOL / worst if worst else float('inf'):.1e} 倍）"))

    # ③ 分量都在 [0,1] 且加起来等于总量
    bad_rng, bad_sum = [], []
    for a in range(0, 8):
        for b in range(0, 8):
            for c in range(0, 8):
                ua = {f"x{i}" for i in range(a + b)}
                ub = {f"x{i}" for i in range(a)} | {f"y{i}" for i in range(c)}
                for fam in B.FAMILIES:
                    p = B.pairwise(ua, ub, family=fam)
                    for k in ("total", "turnover", "nestedness"):
                        if not (-1e-12 <= p[k] <= 1 + 1e-12):
                            bad_rng.append((fam, a, b, c, k, p[k]))
                    if abs(p["total"] - p["turnover"] - p["nestedness"]) > TOL:
                        bad_sum.append((fam, a, b, c))
    out.append(("两个分量都在 [0,1]（两个指数族都查）", not bad_rng,
                f"越界 {bad_rng[:3]}" if bad_rng else "全部在界内"))
    out.append(("总量 = 周转 + 嵌套（两个指数族都查）", not bad_sum,
                f"不成立 {bad_sum[:3]}" if bad_sum else "恒成立"))

    # ④ 多地点版本必须在 N=2 时**逐位等于**成对版本
    #
    # 这是「推广没跑偏」的最低要求 —— 多地点公式是本层补的（手册没给），
    # 所以必须有一条硬测试守着。
    bad_m2 = []
    for a in range(0, 7):
        for b in range(0, 7):
            for c in range(0, 7):
                ua = {f"x{i}" for i in range(a + b)}
                ub = {f"x{i}" for i in range(a)} | {f"y{i}" for i in range(c)}
                for fam in B.FAMILIES:
                    p = B.pairwise(ua, ub, family=fam)
                    m = B.multi([ua, ub], family=fam)
                    for k in ("total", "turnover", "nestedness"):
                        if abs(p[k] - m[k]) > TOL:
                            bad_m2.append((fam, a, b, c, k, p[k], m[k]))
    out.append(("多地点在 N=2 时逐位等于成对（本层补的推广的最低要求）",
                not bad_m2, f"不等 {bad_m2[:3]}" if bad_m2 else
                "全部逐位相等（两个指数族、343 组）"))

    # ⑤ 四类差异确实落在两个轴上
    cases = [
        ("consensus（同一批单元）", {"u1", "u2"}, {"u1", "u2"}, "consensus", None),
        ("refinement（A ⊊ B）", {"u1"}, {"u1", "u2", "u3"}, "nestedness", "c_richer"),
        ("omission（A ⊋ B）", {"u1", "u2", "u3"}, {"u1"}, "nestedness", "b_richer"),
        ("alternative/矛盾（完全不相交）", {"u1", "u2"}, {"u3", "u4"}, "turnover", None),
        ("alternative（平衡替换）", {"u1", "u2", "u3"}, {"u1", "u4", "u5"},
         "turnover", None),
    ]
    bad_axis = []
    for name, ua, ub, want_axis, want_dir in cases:
        p = B.pairwise(ua, ub)
        if p["axis"] != want_axis:
            bad_axis.append((name, p["axis"], want_axis))
        if want_dir and p["direction"] != want_dir:
            bad_axis.append((name, p["direction"], want_dir))
    out.append(("四类差异落在两个轴上（四类 → 两轴 + 方向）",
                not bad_axis,
                f"不符 {bad_axis}" if bad_axis else
                "consensus→零；refinement/omission→嵌套（方向相反）；"
                "alternative/矛盾→纯周转"))

    # ⑥ 在真实材料上：三份立场的三对关系应当给出**三种不同的读法**
    from generators import positions as POS
    views, _intent = POS.build()
    dec = B.decompose(views)
    axes = {p["views"]: p["axis"] for p in dec["pairs"]}
    out.append(("立场材料：三对视图给出不同的两轴读法",
                len(set(axes.values())) >= 2,
                f"{axes}"))

    return out


def report() -> list:
    from generators import positions as POS
    views, _intent = POS.build()
    dec = B.decompose(views)
    rows = [("立场材料的三对视图（Sørensen 族）", "")]
    for p in dec["pairs"]:
        rows.append((f"  {p['views'][0]} × {p['views'][1]}",
                     f"a={p['a']} b={p['b']} c={p['c']}  "
                     f"总 {p['total']:.4f} = 周转 {p['turnover']:.4f} "
                     f"+ 嵌套 {p['nestedness']:.4f}  →  **{p['axis']}**"
                     f"（{p['direction']}）"))
    m = dec["multi"]
    rows.append(("多地点（3 个视图一起）",
                 f"总 {m['total']:.4f} = 周转 {m['turnover']:.4f} "
                 f"+ 嵌套 {m['nestedness']:.4f}"))
    rows.append(("Jaccard 族（本层重建的变换，未核正文）",
                 "、".join(f"{p['views'][0]}×{p['views'][1]} "
                          f"总 {p['total']:.4f}/周转 {p['turnover']:.4f}"
                          for p in B.decompose(views, family=B.JACCARD)["pairs"])))
    return rows


if __name__ == "__main__":
    import sys
    for t, v in report():
        print(f"  {t:<44} {v}")
    print()
    bad = 0
    for t, ok, d in run_all():
        print(f"  {'过    ' if ok else '**红的**'} {t:<52} {d}")
        bad += 0 if ok else 1
    sys.exit(1 if bad else 0)
