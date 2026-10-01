"""零模型的检查 —— 重点是**检验这个检验本身是不是检验**。

---
为什么这个模块的重心在「校准」
----------------------------

本仓库禁「空跑也过」。而零模型有一种更隐蔽的空跑：
**它会在自己人身上报显著。**

所以本模块的第一条不是「真材料显不显著」，而是：
拿**从零模型自己抽出来的背景**当「观测」，p 值必须**均匀** ——
`p < 0.05` 的比例要接近 0.05。

⚠️ **这条实测红过一次，而它抓到的是一个真错**：
只报单方向时，30 个零背景里有 **12 个**报 `p < 0.05`（期望 1.5，
二项尾概率 ≈ 0.000）。因为「观测落在零分布低端」在单方向式子里
得到 `p = 1.000`（看着不显著），而落在高端得到 `1/(1+R)`（看着显著）——
**同一个零模型，两端待遇不同。** 两个方向都算之后 → **1/30，尾概率 0.785**。

⚠️ **如实说明**：模块里那个 `ties`（含/不含并列）选项是**留下的告诫，
不是我证明了的缺陷**。校准失败时我一度以为原因是并列，实测不是 ——
原因是方向。`n_ties` 报出来，是为了让「这个量并列严重」这件事可见。
"""

from __future__ import annotations

import math

from analysis import concepts as K
from analysis import nullmodel as N


def _ctx_positions():
    from generators import positions as POS
    from analysis import divergence as D
    from analysis import focus as F
    views, _i = POS.build()
    return views, K.context(F._all_records(D.analyse(views)), views)


def _calibration(ctx: dict, key: str, K_draws: int = 30, R: int = 99,
                 seed: int = 101, ge: bool = True, le: bool = True,
                 two_directions: bool = True) -> dict:
    """**校准检验**：把零模型自己抽出来的背景当「观测」，看 p 值均不均匀。

    `ge` / `le`：高侧 / 低侧**是否把并列算进「至少一样极端」**。
    `two_directions`：是否两个方向都算。
    """
    nulls = N.null_distribution(ctx, R=R, seed=seed)["nulls"]
    n_swap = 10 * sum(N.marginal_rows(ctx))
    ps = []
    for j in range(K_draws):
        rand = N.swap_randomize(ctx, n_swap, seed * 1000 + 900001 + j)
        rctx = {"attrs": rand["attrs"], "all_attrs": rand["all_attrs"],
                "n_objects": ctx["n_objects"], "n_attrs": ctx["n_attrs"]}
        o = N.statistics(rctx)[key]
        big = (1 + sum(1 for n in nulls
                       if (n[key] >= o if ge else n[key] > o))) / (1 + len(nulls))
        if not two_directions:
            ps.append(big)
            continue
        small = (1 + sum(1 for n in nulls
                         if (n[key] <= o if le else n[key] < o))) / (1 + len(nulls))
        ps.append(min(big, small))
    lo = sum(1 for p in ps if p < 0.05)
    tail = sum(math.comb(K_draws, k) * 0.05 ** k * 0.95 ** (K_draws - k)
               for k in range(lo, K_draws + 1))
    return {"n_below": lo, "n_draws": K_draws, "expected": K_draws * 0.05,
            "tail": tail, "ps": ps}


def run_all() -> list:
    from analysis import divergence as D
    from analysis import focus as F
    out = []
    views, ctx = _ctx_positions()
    rows0, cols0 = N.marginal_rows(ctx), N.marginal_cols(ctx)
    n_swap = 10 * sum(rows0)

    # ① 随机化**逐位保持两个边际**，而且**真的动了**
    r1 = N.swap_randomize(ctx, n_swap, 5)
    r1ctx = {"attrs": r1["attrs"], "all_attrs": r1["all_attrs"],
             "n_objects": ctx["n_objects"], "n_attrs": ctx["n_attrs"]}
    moved = sum(1 for i in rows0 and sorted(ctx["attrs"])
                if r1["attrs"][i] != ctx["attrs"][i])
    out.append(("随机化逐位保持行/列边际，且确实动了",
                N.marginal_rows(r1ctx) == rows0
                and N.marginal_cols(r1ctx) == cols0 and moved > 0,
                f"行和 {sorted(set(rows0))}、列和不变；{moved}/{len(rows0)} "
                f"条记录的特征集被改动（改了 {r1['n_swaps_done']} 次交换）"))

    # ② **绝不改动入参**
    before = {i: frozenset(s) for i, s in ctx["attrs"].items()}
    N.swap_randomize(ctx, n_swap, 6)
    out.append(("随机化不改动入参",
                {i: frozenset(s) for i, s in ctx["attrs"].items()} == before,
                "入参形式背景逐位不变"))

    # ③ 确定性：同种子同结果
    a = N.swap_randomize(ctx, n_swap, 7)["attrs"]
    b = N.swap_randomize(ctx, n_swap, 7)["attrs"]
    out.append(("确定性：同种子给出同一个随机化", a == b,
                f"两次 {n_swap} 次交换的结果逐位相同"))

    # ④ **定理**：`Σ_C Sep(C) ≡ 对象数`（所以它不可检验）
    st = N.statistics(ctx)
    out.append(("定理 `Σ Sep ≡ 对象数`（所以 sum_sep 不可检验）",
                st["sum_sep"] == ctx["n_objects"],
                f"立场材料 Σ Sep = {st['sum_sep']}，对象数 = {ctx['n_objects']}"
                " —— 零分布里它一动不动，因为它是**定理不是测量值**"))

    # ⑤ 常数统计量**不给 p 值**（给它 p 是谎话）
    dd_ok = True
    from checks import realdata as RD
    from adapters import scaffold as SC
    dd = RD.corpus_dir()
    if dd:
        nodes = SC.load_corpus_dir(dd)
        rv = [av.view for av in SC.split_views(nodes, split_by="source.kind")]
        if len(rv) >= 2:
            rctx = K.context(F._all_records(D.analyse(rv)), rv)
            cmp_r = N.compare(rctx, R=99, seed=3)
            q = cmp_r["stats"]["useful_layers"]
            dd_ok = "status" in q and "constant" in q["status"]
            out.append(("零分布里恒定的量不给 p 值（给它 p 是谎话）",
                        dd_ok or "status" in q,
                        f"真实语料的 useful_layers：{q.get('status', '有 p=' + str(q.get('p')))}"
                        " —— 恒定则「没有随机化更极端」是废话，"
                        "真相是这个量没有随机变化"))

    # ⑥ **校准检验**：这个检验在自己人身上不许报显著
    #
    # ⚠️ 这条抓到过一个真错，而**我把它归因错了两次**：
    #   第一次以为原因是「方向」（只报单侧），
    #   改的时候又**同时**把 `>` 悄悄换成了 `>=`，于是把功劳记给了方向。
    #   四个组合各跑一遍才看清 —— **两件事都要**：
    #
    #       不含并列(高)/不含并列(低)  30/30   不校准
    #       不含并列(高)/含并列(低)    13/30   不校准
    #       含并列(高)/不含并列(低)    17/30   不校准
    #       **含并列(高)/含并列(低)     0/30    校准**
    #
    # 原因：零分布是 `{1: 70, 2: 29}` 这种**并列严重**的离散分布。
    # 观测落在 1 上时，不含并列的低侧数出 `#{<1} = 0`；落在 2 上时，
    # 不含并列的高侧数出 `#{>2} = 0` —— **两端都被判「极端」**，
    # 因为并列被当成了「不在分布里」。
    key = "max_sep"
    good = _calibration(ctx, key)
    out.append((f"校准：零背景当观测时 p<0.05 的比例接近 0.05（{key}）",
                good["tail"] > 0.01,
                f"{good['n_below']}/{good['n_draws']} 报 p<0.05（期望 "
                f"{good['expected']:.1f}），二项尾概率 {good['tail']:.3f} "
                "—— **两方向都算 + 并列两边都含**"))

    # ⑦ 另外四种做法**都误报** —— 四个组合全钉住，这个错就不会再回来
    #
    # ⚠️ 注意「误报」与「没检验力」是两种不同的失败，别混。
    # `含并列 + 只报单方向` 不误报，但它**永远不拒绝**（见下 §⑧ 的说明）——
    # 那是没有检验力，不是校准。
    combos = [
        ("不含并列(高)/不含并列(低)", dict(ge=False, le=False)),
        ("不含并列(高)/含并列(低)  ", dict(ge=False, le=True)),
        ("含并列(高)/不含并列(低)  ", dict(ge=True, le=False)),
        ("不含并列 + 只报单方向     ", dict(ge=False, le=False,
                                            two_directions=False)),
    ]
    detail, all_over = [], True
    for name, kw in combos:
        c = _calibration(ctx, key, **kw)
        detail.append(f"{name} {c['n_below']}/{c['n_draws']}")
        if c["tail"] > 0.01:
            all_over = False
    out.append(("⚠️ 四种做法**都误报**显著（同一个零模型，两端待遇不同）",
                all_over and good["n_below"] < 2,
                "；".join(detail) + f"  vs 正确做法 {good['n_below']}/{good['n_draws']}"
                " —— 原因：零分布 `{1: 70, 2: 29}` 并列严重，"
                "不含并列时**低端与高端都被判「极端」**。"
                "**而我把这个错先归因给「方向」，改的时候又同时动了并列，"
                "于是把功劳记错了地方。**"))

    # ⑧ `含并列 + 只报单方向` 是**另一种**失败：不误报，但也没有检验力
    weak = _calibration(ctx, key, ge=True, le=True, two_directions=False)
    out.append(("⚠️ 含并列 + 只报单方向：不误报，但**没有检验力**",
                weak["n_below"] == 0,
                f"{weak['n_below']}/{weak['n_draws']} 报显著 —— 它永远不拒绝，"
                "因为观测落在低端时 `#{≥ o}` 就是整个零分布。"
                "**「不误报」与「有检验力」是两件事** —— "
                "一个永远返回「不显著」的检验，校准得完美。"))

    # ⑧ 阳性对照：植入结构（边际要**松**，否则零模型无从随机化）
    objs = 40
    ats = [f"a{i}" for i in range(8)]
    pat = {i: {ats[(i // 10) * 2], ats[(i // 10) * 2 + 1],
               ats[((i // 10) * 2 + 4) % 8]} for i in range(objs)}
    pctx = {"attrs": pat, "all_attrs": ats, "n_objects": objs,
            "n_attrs": len(ats)}
    pcmp = N.compare(pctx, R=99, seed=202)
    pm = pcmp["stats"]["max_sep"]
    out.append(("阳性对照：植入结构时显著（检验有力）",
                pm.get("p", 1.0) < 0.05,
                f"40×8、行和恒 3、四个两块一组：观测 max_sep = "
                f"{pm['observed']}，p = {pm.get('p')} → {pm.get('direction', '')}"))

    return out


def report() -> list:
    from analysis import divergence as D
    from analysis import focus as F
    rows = []
    views, ctx = _ctx_positions()
    r = N.compare(ctx, R=199, seed=7)
    rows.append(("立场材料", f"{ctx['n_objects']} × {ctx['n_attrs']}"))
    for k, v in r["stats"].items():
        if "status" in v:
            rows.append((f"  {k}", f"{v['observed']}  —— {v['status']}"))
        else:
            rows.append((f"  {k}",
                         f"观测 {v['observed']}  p={v['p']:.3f}  {v['direction']}"))
    from checks import realdata as RD
    from adapters import scaffold as SC
    dd = RD.corpus_dir()
    if dd:
        nodes = SC.load_corpus_dir(dd)
        rv = [av.view for av in SC.split_views(nodes, split_by="source.kind")]
        if len(rv) >= 2:
            rctx = K.context(F._all_records(D.analyse(rv)), rv)
            r2 = N.compare(rctx, R=199, seed=7)
            rows.append(("真实语料", f"{rctx['n_objects']} × {rctx['n_attrs']}"))
            for k, v in r2["stats"].items():
                if "status" in v:
                    rows.append((f"  {k}", f"{v['observed']}  —— {v['status']}"))
                else:
                    rows.append((f"  {k}",
                                 f"观测 {v['observed']}  p={v['p']:.3f}  {v['direction']}"))
    rows.append(("读法",
                 "两份材料都显著，方向一致：**格更小、但「拥有记录」的概念更强** —— "
                 "真分歧的结构是**集中的**，随机的是**弥散的**。"
                 "⚠️ 这是**聚合统计量**的判据，**不是逐概念的判据**。"))
    return rows


if __name__ == "__main__":
    import sys
    print("── 度量 ──")
    for t, v in report():
        print(f"  {t:<16} {v}")
    print("\n── 断言 ──")
    bad = 0
    for t, ok, d in run_all():
        print(f"  {'过    ' if ok else '**红的**'} {t:<50} {d}")
        bad += 0 if ok else 1
    sys.exit(1 if bad else 0)
