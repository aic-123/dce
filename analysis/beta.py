"""β 多样性：把差异拆成**周转 / 嵌套**两个分量 —— 借自群落生态学。

---
为什么要借它：它正面解开四类边界会移动那个毛病
--------------------------------------------

本仓库量出过一个判据层面的毛病：**四类的边界随构造移动。**
同一个单元可以既是「相对 A 的精炼」又是「相对 C 的缺失」，
于是 strict 召回 15/115 而 accounted 100%。

生态学早就放弃了这种互斥标签。它把两个地点之间的组成差异拆成两个分量：

    β_总  =  β_周转  +  β_嵌套        （**不是两类东西，是同一个量的两个分量**）
    β_周转   两地**互相替换** —— 谁也不是谁的子集
    β_嵌套   一地的组成是另一地的**子集**

而**嵌套分量天生是有方向的**（谁嵌套谁）—— 那正好对上本仓库发现的
「精炼的主语是 (粗, 细, 单元)，缺失的主语是 (视图, 单元)」。

⚠️ 出处与「哪些是核过的、哪些是我自己补的」：

    已核对正文：`betapart` 1.6.1 的 CRAN 参考手册（维护者 Andres Baselga，
    即 Baselga 2010 / 2012 那两篇的作者）。核到的是：
      · 包装的是什么（`Partitioning Beta Diversity into Turnover and Nestedness Components`）
      · **两个指数族**：sorensen 与 jaccard
      · `beta.pair` / `beta.multi` 各返回 **3 个**值，名字是
        beta.sor/beta.sim/beta.sne 与 beta.jac/beta.jtu/beta.jne
      · **Sørensen 族的周转分量用 Simpson 指数**
      · `beta.multi` 是**多地点**版本（不是只有成对）
    手册**没有给公式**，只给了名字与结构。所以下面：

      已核对：Sørensen 族的三个式子（a/b/c 是标准记号，与手册的名字一致）
      本层补的：**Jaccard 族用 Sørensen↔Jaccard 的单调变换导出**。
                这一步是我做的重建，**没有对着正文核过** —— 见 `_to_jaccard()`

⚠️ 另一处必须说清的：**命名并不统一。** `betapart` 手册的参考文献里同时列着
Legendre 2014，他那两个分量叫 **replacement / richness difference**，不叫 nestedness；
还有 Baselga & Leprieur 2015《Comparing methods to separate components of beta diversity》。
**所以「嵌套」这个命名本身是有争论的**，本仓库借的是 Baselga 这一支，并在此声明。

---
与 DCE 四类的对应（这一条有**定理**支撑，不是类比）
------------------------------------------------

设 `a = |A∩B|`、`b = |A−B|`、`c = |B−A|`。可以证明（见 `checks/beta.py` 的穷尽验证）：

    β_sne = a·(M − m) / [(2a + m + M)(a + m)]      （m = min(b,c)，M = max(b,c)）

    β_sne ≥ 0   恒成立
    β_sne = 0   ⟺  b = c  或  (a = 0 且 m > 0)
    即：**纯周转 ⟺ 差异完全平衡，或两个非空视图完全不相交**

⚠️ **退化情形要单列**（`a = 0` 且 `m = 0`，即**其中一个视图是空的**）：
那时上式分母为 0，简化不成立，而 `β_嵌套 = 1` —— **那是对的，不是 bug。**
空集是任何集合的子集，所以「一个视图什么都没有」是**极端的嵌套**，
不是周转。这正是本仓库先前栽过一次的形状（空视图被当成精炼的粗侧）；
在 β 分解里它自动落在正确的一侧，**不需要额外的特例**。

于是四类落在两个轴上：

    DCE consensus                →  β_总 = 0
    DCE alternative / contradiction →  **纯周转**（β_sne = 0，有替换无嵌套）
    DCE refinement / omission     →  **纯嵌套或混合**（β_sne > 0），方向由 b−c 的符号给出

**refinement 与 omission 不是两类**，是同一个嵌套现象的两个方向。
"""

from __future__ import annotations

SORENSEN = "sorensen"
JACCARD = "jaccard"
FAMILIES = (SORENSEN, JACCARD)


class BetaError(Exception):
    """参数不对。"""


def _abc(ua, ub) -> tuple:
    """标准三记号：`a` = 共有，`b` = 只在 A，`c` = 只在 B。"""
    a = len(ua & ub)
    b = len(ua - ub)
    c = len(ub - ua)
    return a, b, c


def _to_jaccard(sor: float) -> float:
    """Sørensen 值 → Jaccard 值。

    ⚠️ **这一步是本层补的，没有对着正文核过。** 关系式
    `β_jac = 2·β_sor / (1 + β_sor)` 是两族之间的单调变换
    （a=0,b=1,c=1 时两边都是 1；a=1,b=1,c=0 时 1/3 → 1/2）。
    手册确认了「两族并存、各有三个同名分量」，**但没给这条变换**。
    要用 Jaccard 族的结论前，先核这一步。
    """
    return (2 * sor) / (1 + sor) if sor != -1 else 0.0


def pairwise(units_a: set, units_b: set, family: str = SORENSEN) -> dict:
    """两个视图之间的 β 分解。

    `units_a` / `units_b` 是各自的**单元集合**（`consensus.units_of` 的输出）。
    """
    if family not in FAMILIES:
        raise BetaError(f"未知指数族 {family!r}，只认 {list(FAMILIES)}")
    a, b, c = _abc(units_a, units_b)

    denom = 2 * a + b + c
    total_sor = (b + c) / denom if denom else 0.0
    m = min(b, c)
    turn_sor = m / (a + m) if (a + m) else 0.0
    nest_sor = total_sor - turn_sor          # ≥ 0 恒成立，见模块 docstring

    if family == SORENSEN:
        total, turn, nest = total_sor, turn_sor, nest_sor
    else:
        total, turn = _to_jaccard(total_sor), _to_jaccard(turn_sor)
        nest = total - turn

    return {
        "family": family,
        "a": a, "b": b, "c": c,
        "total": total,
        "turnover": turn,
        "nestedness": nest,
        # 方向：谁是谁的子集。b>c 表示 A 多出来的更多 → B 更接近 A 的子集
        "direction": ("b_richer" if b > c else "c_richer" if c > b else "balanced"),
        # 两轴读法（**DCE 四类的替代表述**）
        "axis": ("consensus" if total == 0 else
                 "turnover" if nest == 0 else
                 "nestedness" if turn == 0 else "mixed"),
    }


def multi(units_list: list, family: str = SORENSEN) -> dict:
    """**多地点**版本：N 个视图的 β 分解（`beta.multi` 对应物）。

    ⚠️ 本层用的是「**成对求和**」的推广：把 a / b / c 与周转分量都按全部
    视图对求和，再代入同一组式子。**这一步也是本层补的** —— 手册确认了
    `beta.multi` 存在且返回三个值（Sørensen 族与 Jaccard 族各三个），
    **但没给多地点公式**。

    内部一致性由一条硬测试守着：**N=2 时必须与 `pairwise()` 逐位相等**。
    那是「推广没跑偏」的最低要求。
    """
    if family not in FAMILIES:
        raise BetaError(f"未知指数族 {family!r}，只认 {list(FAMILIES)}")
    n = len(units_list)
    if n < 2:
        raise BetaError(f"至少 2 个视图，收到 {n}")

    A = B = M = 0
    for i in range(n):
        for j in range(i + 1, n):
            a, b, c = _abc(units_list[i], units_list[j])
            A += a
            B += b
            M += min(b, c)

    denom = 2 * A + B + sum(  # c 的总和：对每对取 |S_j − S_i|
        len(units_list[j] - units_list[i])
        for i in range(n) for j in range(i + 1, n))
    C = denom - 2 * A - B
    total_sor = (B + C) / denom if denom else 0.0
    turn_sor = M / (A + M) if (A + M) else 0.0
    nest_sor = total_sor - turn_sor

    if family == SORENSEN:
        total, turn, nest = total_sor, turn_sor, nest_sor
    else:
        total, turn = _to_jaccard(total_sor), _to_jaccard(turn_sor)
        nest = total - turn
    return {"family": family, "n_views": n,
            "a": A, "b": B, "c": C,
            "total": total, "turnover": turn, "nestedness": nest}


def decompose(views, family: str = SORENSEN) -> dict:
    """对一组视图做完整的 β 分解：全部成对 + 一个多地点总览。

    ⚠️ 与四类差异的**关系**是这一层的重点，不是替代：
    四类说的是「哪一条结构属于哪一类」，β 说的是「**这一对视图之间**，
    差异里有多少是替换、多少是嵌套」。两者粒度不同，可以并存。
    """
    from analysis import consensus as C
    units = [C.units_of(v) for v in views]
    pairs = []
    for i in range(len(views)):
        for j in range(i + 1, len(views)):
            rec = pairwise(units[i], units[j], family=family)
            rec["views"] = (views[i]["id"], views[j]["id"])
            pairs.append(rec)
    pairs.sort(key=lambda r: (r["views"][0], r["views"][1]))
    return {"family": family, "pairs": pairs,
            "multi": multi(units, family=family) if len(views) >= 2 else None}
