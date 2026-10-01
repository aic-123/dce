"""零模型：把概念格上的量与**保持边际的随机背景**比 —— 借自空间统计的蒙特卡洛检验。

---
为什么要它（而且现在为什么要）
----------------------------

本仓库有条规矩（§T0.3）：**不许在缺少基线数据时拍一个阈值。**
而 §11.12 的结论是 `stability` **没有无阈值的判据**（`σ = 1` 从不出现），
所以它「要用就得给阈值」。**零模型给的就是那条被允许的线** ——
它用数据自己造基线，于是阈值不再是我拍的，而是**从随机背景里读出来的**。

于是这个模块的用途很具体：**给 `Sep` / `stability` / 格规模这些量配上基线。**

---
判据先写下来（在测之前）
----------------------

**零模型选哪个** —— 这是本模块最关键的决定，而它会影响结论（`PRIOR-ART.md` 里
早就标了「零模型怎么写会直接影响结论」）。四个候选：

    (a) 保持**行与列两个边际**的随机化（二分图的度保持交换）
    (b) 只保持行和（每条记录的特征数）
    (c) 只保持列和（每个特征被多少条记录拥有）
    (d) 什么都不保持

**选 (a)**，理由：形式背景是「记录 × 特征」的二分结构，而我们要问的问题是
「**记录的共现模式**是否比随机更结构化」。(a) 恰好只破坏共现、保留
「每条记录有几个特征」与「每个特征被几条记录拥有」——
这正是 `scanstatistics` 的 `permute_matrix` 保行列边际的同一件事，
也是生态学里「固定-固定」零模型的同一件事。

**统计量**（各算一个，**不合成一个分** —— 理由见 §11.12）：

    n_concepts     格规模
    n_irredundant  Sep > 0 的概念数（「拥有记录」的概念数）
    n_summarizing  Sep > 0 **且** |Ext| > 1 的概念数（「真的概括了」的概念数）
    max_sep        最大的 Sep
    useful_layers  「有用层」的个数（§11.7 那条判据）

⚠️ **`Σ_C Sep(C) ≡ 对象数` 是一条定理，不是一个测量值。**
所以 `sum_sep` **不参与检验**（它在任何零分布里都一动不动）。证明：

    固定一个对象 o，令 F_o = { C : o ∈ Ext(C) }。F_o 在格序下**上闭**。
    F_o 的极小元唯一 —— 就是 (o'', o')：
      任何含 o 的概念 (A,B) 都有 B ⊆ o'，于是 A = B' ⊇ o''。
    而 Σ_C Sep(C) 对每个 o 数的是「F_o 里没有子概念也在 F_o 中的那些 C」，
    也就是 F_o 的极小元个数 = **1**。
    ⇒ Σ_C Sep(C) = 对象数  ▮

**p 值**（逐字核自 CRAN `scanstatistics` 参考手册）：

    φ = (1 + Σ_{i=1..R} I(λ_i > λ*)) / (1 + R)

单侧、蒙特卡洛。`+1` 不是修正，是**把观测本身也算进那个分布里**
（否则 R 很小时会得到 0，而 0 是谎话：它声称「不可能更极端」）。

⚠️ **但那个式子是单侧的，而「更低」也是一种偏离。** 真实语料的格规模
（34）远低于零分布（84–95），单侧报出来是 `p = 1.000` —— 读起来像「不显著」，
其实是**显著地更低**。所以本模块**两个方向都算**，并把偏离方向明白写出来。
（这与本仓库记过的那条同一族：**两个数有距离 ≠ 检验它们是否有差别**。）

⚠️ **在零分布里一动不动的统计量无法检验**（`sum_sep` 是定理，
`useful_layers` 在真实语料上恰好恒为 2）—— 那时报「p = 1/(1+R)」是**谎话**：
它在说「没有随机化更极端」，而真相是「这个量根本没有随机变化」。
所以本模块对它明确报 `constant`，**不给 p 值**。

---
在测之前写下的**预测**（以及什么会证伪它）
---------------------------------------

    P1  真实语料上，`n_summarizing` 与 `useful_layers` **很可能不比随机显著**。
        理由：那份语料 192 条**全是 omission**，它的结构几乎完全由边际
        （哪个体裁漏得多）决定，而 (a) 恰好保留边际。
        → 若 p 很大，则 §11.4 那句「四个体裁切面彼此嵌套/冗余」是**边际的产物**，
          不是共现结构的产物；那句话要降级。

    P2  立场材料（20 条、四种类型齐全、`authored://`）上，`n_summarizing`
        **应当显著** —— 因为它的共现是构造出来的（P1/P2/P3 的分歧确实成组）。
        → 若 p 很大，则说明我的特征选取没能抓住那份材料的结构。

    P3  一个**随机生成**的背景应当**不显著**（p 大），一个**植入结构**的背景
        应当**显著**（p 小）。这是零模型自己的双重可证伪性检查 ——
        **一个只能往一个方向出的检验不是检验。**

⚠️ 上面三条是**我写的**，不是量出来的。跑完之后要么改代码，要么改这三条并说明为什么。
"""

from __future__ import annotations

import random

from analysis import concepts as K

DEFAULT_R = 200


class NullModelError(Exception):
    """参数或前提不对。"""


def marginal_rows(ctx: dict) -> list:
    """每行的和（每条记录的特征数）。"""
    return [len(ctx["attrs"][i]) for i in sorted(ctx["attrs"])]


def marginal_cols(ctx: dict) -> list:
    """每列的和（每个特征被多少条记录拥有）。"""
    return [sum(1 for i in ctx["attrs"] if m in ctx["attrs"][i])
            for m in ctx["all_attrs"]]


def swap_randomize(ctx: dict, n_swaps: int, seed: int) -> dict:
    """**度保持**的二分随机化：对 (对象, 特征) 矩阵做 2×2 棋盘交换。

        交换前           交换后
        a1  a2           a1  a2
    o1   1   0      →    0   1
    o2   0   1           1   0

    行列和都**逐位不变**。`n_swaps` 是尝试次数（成功的交换可能少于它）。
    **绝不改动入参** —— 返回一份新的 `attrs`。
    """
    attrs = {i: set(s) for i, s in ctx["attrs"].items()}
    objs = sorted(attrs)
    all_attrs = list(ctx["all_attrs"])
    rng = random.Random(seed)
    done = 0
    for _ in range(n_swaps):
        o1, o2 = rng.sample(objs, 2)
        # 需要 o1 有 a1 没有 a2、o2 有 a2 没有 a1（或反过来）
        a1, a2 = rng.sample(all_attrs, 2)
        if (a1 in attrs[o1] and a2 not in attrs[o1]
                and a2 in attrs[o2] and a1 not in attrs[o2]):
            attrs[o1].discard(a1); attrs[o1].add(a2)
            attrs[o2].discard(a2); attrs[o2].add(a1)
            done += 1
    return {"attrs": attrs, "all_attrs": all_attrs,
            "n_objects": ctx["n_objects"], "n_attrs": ctx["n_attrs"],
            "n_swaps_done": done}


def statistics(ctx: dict, max_concepts: int = K.MAX_CONCEPTS) -> dict:
    """一个形式背景上的统计量。格太大时**拒绝**（不截断）。"""
    got = K.all_concepts(ctx, max_concepts=max_concepts)
    seps = K.separation(got["concepts"])
    lv = K.levels(ctx, seps)
    return {
        "n_concepts": got["n_concepts"],
        "n_irredundant": sum(1 for s in seps if s["sep"] > 0),
        "n_summarizing": sum(1 for s in seps
                             if s["sep"] > 0 and len(s["extent"]) > 1),
        "max_sep": max((s["sep"] for s in seps), default=0),
        # ⚠️ 定理：Σ_C Sep(C) ≡ 对象数。所以这不是一个可检验的量，
        # 列出来是为了**看见**它对不上（对不上就是 Sep 实现错了）。
        "sum_sep": sum(s["sep"] for s in seps),
        "useful_layers": len(lv["useful_intent_sizes"]),
    }


def null_distribution(ctx: dict, R: int = DEFAULT_R, seed: int = 0,
                      max_concepts: int = K.MAX_CONCEPTS) -> dict:
    """R 次度保持随机化的统计量分布。**入参不变。**

    单次随机化算不动（格太大）时**记下来并跳过**，不悄悄用一个小格顶替 ——
    那会让零分布偏向「格小」的一侧，而统计量正是格规模。
    """
    rows0, cols0 = marginal_rows(ctx), marginal_cols(ctx)
    # 交换次数：取 10 倍「1 的个数」，这个倍数本身不是判据（混匀用，不是阈值）
    ones = sum(rows0)
    n_swaps = 10 * ones
    out, skipped = [], 0
    for r in range(R):
        rand = swap_randomize(ctx, n_swaps, seed * 100003 + r)
        rctx = {"attrs": rand["attrs"], "all_attrs": rand["all_attrs"],
                "n_objects": ctx["n_objects"], "n_attrs": ctx["n_attrs"]}
        # 自检：边际必须逐位不变
        if marginal_rows(rctx) != rows0 or marginal_cols(rctx) != cols0:
            raise NullModelError("随机化破坏了边际 —— 那它就不是保持边际的零模型")
        try:
            out.append(statistics(rctx, max_concepts=max_concepts))
        except K.ConceptError:
            skipped += 1
    return {"nulls": out, "R_requested": R, "R_used": len(out),
            "skipped": skipped, "seed": seed, "n_swaps": n_swaps}


def pvalue(observed: float, nulls: list, key: str,
           direction: str = "greater", ties: str = "conservative") -> float:
    """蒙特卡洛单侧 p 值。**`ties="strict"` 那支逐字核自 CRAN `scanstatistics`**：

        φ = (1 + Σ_{i=1..R} I(λ_i > λ*)) / (1 + R)

    `+1` 不是修正 —— 它把**观测本身也算进那个分布**里。

    ⚠️ **但那个式子在离散统计量上是错的，而这一点是量出来的。**
    它给泊松计数那种近乎连续的扫描统计量设计；一旦零分布**大量并列**
    （`max_sep` 在立场材料上只取 1 和 2），只要观测落在零分布的最大值上，
    `#{> 观测} = 0`，于是 `p = 1/(1+R) ≈ 0.01` —— **报「显著」**。

    实测：拿 30 个**从零模型自己抽出来的背景**当「观测」，
    `strict` 版本有 **12 个**报 p < 0.05（期望 1.5；二项尾概率 ≈ 0.000）。
    **一个会在自己人身上报显著的检验不是检验。**

    所以默认走 `"conservative"`：把**并列**也算进「至少一样极端」，
    即 `(1 + Σ I(λ_i ≥ λ*)) / (1 + R)`。并列多时它偏保守，
    而**保守的代价（少报）比冒进的代价（多报）小** —— 这里多报会把
    随机波动说成结构。

    ⚠️ 无论走哪支，**都要看 `n_ties`**：它才是「这个统计量能不能检验」的指示。
    """
    if not nulls:
        raise NullModelError("零分布是空的 —— 算不出 p 值，不许默认给一个")
    if direction == "greater":
        cmp = (lambda v: v > observed) if ties == "strict" else \
              (lambda v: v >= observed)
    elif direction == "less":
        cmp = (lambda v: v < observed) if ties == "strict" else \
              (lambda v: v <= observed)
    else:
        raise NullModelError(f"direction 只认 greater / less，收到 {direction!r}")
    k = sum(1 for n in nulls if cmp(n[key]))
    return (1 + k) / (1 + len(nulls))


def n_ties(observed: float, nulls: list, key: str) -> int:
    """零分布里与观测**并列**的个数。并列多 → 这个统计量分不出细微差别。"""
    return sum(1 for n in nulls if n[key] == observed)


def is_constant(nulls: list, key: str) -> bool:
    """零分布里这个统计量是否**一动都不动**。动不了的量无法检验。"""
    vals = {n[key] for n in nulls}
    return len(vals) <= 1


def compare(ctx: dict, R: int = DEFAULT_R, seed: int = 0,
            max_concepts: int = K.MAX_CONCEPTS,
            untestable: tuple = ("sum_sep",),
            ties: str = "conservative") -> dict:
    """观测 vs 零分布，逐统计量给**两个方向**的 p 值。**不合成一个总分。**

    ⚠️ 每个统计量各自一个 p，**不做多重比较校正，也不取最小值当结论** ——
    那会把「六个量里有一个显著」当成「这材料显著」。
    要下结论就得先指定**哪一个**统计量是判据（那是判据层的决定，不是本模块的）。

    ⚠️ 零分布里**恒定**的统计量不给 p 值，标 `constant`。
    给它 `p = 1/(1+R)` 是谎话：那在说「没有随机化更极端」，
    而真相是「这个量根本没有随机变化」。

    `untestable`：已知恒定的量（`sum_sep` 是定理）。
    """
    obs = statistics(ctx, max_concepts=max_concepts)
    dist = null_distribution(ctx, R=R, seed=seed, max_concepts=max_concepts)
    out = {}
    for k in obs:
        if k in untestable:
            out[k] = {"observed": obs[k], "status": "定理（Σ Sep ≡ 对象数），不可检验"}
            continue
        if is_constant(dist["nulls"], k):
            out[k] = {"observed": obs[k], "status": "constant（零分布里恒定），不可检验",
                      "null_value": dist["nulls"][0][k]}
            continue
        pg = pvalue(obs[k], dist["nulls"], k, "greater", ties)
        pl = pvalue(obs[k], dist["nulls"], k, "less", ties)
        out[k] = {"observed": obs[k], "p_greater": pg, "p_less": pl,
                  "p": min(pg, pl),
                  "n_ties": n_ties(obs[k], dist["nulls"], k),
                  "n_null_values": len({n[k] for n in dist["nulls"]}),
                  "direction": "观测更低" if pl < pg else "观测更高"}
    return {"stats": out, "observed": obs, "null": dist, "ties": ties}
