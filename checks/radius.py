"""半径校准检查 —— 半径是**显式参数**，它的**上界由结构算出来**。

---
`§T0.3` 到底禁的是什么
--------------------

`§T0.3`：「不得为 `§C7.2` 的任何观测点提**具体阈值**……
没有基线数据的阈值一律是拍脑袋。」

它禁的是**断言一个没有基线数据的具体值**，不是禁「有一个显式参数」：

    ✗ 拍一个半径，当成正确值用                                → 违规
    ✓ 半径是显式参数，整条曲线报出来，
      且它的**上界由结构算出来**（`focus.calibrate`）           → 不违规

`r*` = **焦点塌成 1 的最小半径**，超过它焦点这个中间层不携带信息。
`r*` 是从图里算出来的，数据一多自动重算 —— **那就是校准**。

---
本模块最要紧的一条：**证明半径不是空转的**
----------------------------------------

两个现成语料恰好落在**两个相反的退化极端**：

    立场材料（共享节点空间）  曲线 (0,1)(1,1)(2,1)(3,1)   r*=0
                              radius 0 已经全并成一团，加大只会更糟
    真实语料（按体裁切）      曲线 (0,9)(1,9)…(7,9)       半径再大也并不动
                              切面之间几近不相交，并集图是碎的

于是「半径没用」有两种完全不同的原因，而**两者都不是实现 bug**：
一个是并得太早，一个是永远并不上。若只有这两个例子，
「半径机制是死的」与「这两个语料恰好在极端」在报告上长得一样。

所以本模块**造一个中间地带的例子**：一条连通链，分歧锚在链的两端 ——
radius 0 给 2 个焦点，半径够大时并成 1 个。**那才证明机制活着，而 r* 有实际含义。**
"""

from __future__ import annotations

from analysis import divergence as D
from analysis import focus as F
from core import view as V


def _degenerate_cases() -> list:
    """两个现成的极端 + 一个**中间的**构造用例。"""
    out = []

    # ① 立场材料
    from generators import positions as POS
    views, _ = POS.build()
    out.append(("立场材料（共享节点空间）", views, D.analyse(views)))

    # ② 真实语料（按体裁切）—— 语料不在就跳过这一条
    from checks import realdata as RD
    d = RD.corpus_dir()
    if d is not None:
        from adapters import scaffold as SC
        nodes = SC.load_corpus_dir(d)
        if nodes:
            rv = [a.view for a in SC.split_views(nodes, split_by="source.kind")]
            if len(rv) >= 2:
                out.append(("真实语料（按体裁切）", rv, D.analyse(rv)))

    # ③ **中间地带**：并集图**连通**，而两簇分歧的锚点**节点不相交**且相距够远
    #
    # ⚠️ 这条改了两次才对，两次都是同一类错：**我以为构造出了中间地带，
    # 其实落回了某个极端。**
    #
    #   第一版：两端各给一半边 → 并集图**断成两个分量** → 永远并不上
    #   第二版：让 A、B 各自缺一部分边，但缺的那部分**共享节点 5**
    #           （`(4,5)` 同时出现在两边）→ 一簇在左、一簇在右，**却通过 5 并上了**
    #           → radius 0 就是 1 个焦点，仍然「并得太早」
    #
    # 现在：10 节点链，A 缺左端两条边（锚点 {1,2,3}）、B 缺右端两条边
    # （锚点 {8,9,10}）—— 两簇**节点不相交**，且最近距离是 3→8 = 5。
    # 于是 radius 0..4 给 2 个焦点，radius ≥ 5 并成 1 个 → **r* = 5，有实际含义。**
    nodes = [f"con-{i:04d}" for i in range(1, 11)]
    chain = [(nodes[i], nodes[i + 1], "contains") for i in range(len(nodes) - 1)]
    whole = V.make_view(view_id="L", source_ref="authored://radius/L",
                        source_kind="experiment", nodes=nodes, edges=chain)
    miss_left = V.make_view(view_id="A", source_ref="authored://radius/A",
                            source_kind="experiment", nodes=nodes,
                            edges=[e for e in chain if e not in chain[:2]])
    miss_right = V.make_view(view_id="B", source_ref="authored://radius/B",
                             source_kind="experiment", nodes=nodes,
                             edges=[e for e in chain if e not in chain[-2:]])
    mid = D.analyse([whole, miss_left, miss_right])
    out.append(("**中间地带**（并集图连通，两簇锚点节点不相交）",
                [whole, miss_left, miss_right], mid))
    return out


def run_all() -> list:
    out = []

    # ① 既有行为不变：radius=0 与旧签名一致
    from generators import positions as POS
    pv, _ = POS.build()
    pd = D.analyse(pv)
    n_old = len(F.foci(pd))
    n_zero = len(F.foci(pd, radius=0, views=pv))
    out.append(("radius=0 与旧签名的结果一致（默认不改变任何东西）",
                n_old == n_zero, f"foci()={n_old}、foci(radius=0)={n_zero}"))

    # ② 焦点数随半径**单调不增**（半径越大并得越多）
    bad = []
    for name, views, div in _degenerate_cases():
        curve = F.radius_curve(div, views)
        ns = [n for _k, n in curve]
        if any(ns[i] < ns[i + 1] for i in range(len(ns) - 1)):
            bad.append((name, ns))
    out.append(("焦点数随半径单调不增（半径越大只可能并得更多）",
                not bad, f"违反：{bad}" if bad else "三条曲线全部单调不增"))

    # ③ 中间地带**非退化** —— 这是「机制活着」的证据
    mid = [x for x in _degenerate_cases() if x[0].startswith("**中间")]
    name, views, div = mid[0]
    cal = F.calibrate(div, views)
    curve = cal["curve"]
    n0 = curve[0][1]
    out.append(("中间地带 radius=0 给出 >1 个焦点（机制不是死的）",
                n0 > 1, f"{name}：曲线 {curve}"))
    out.append(("中间地带半径够大时并成 1 个焦点（r* 有实际含义）",
                cal["r_star"] is not None and cal["r_star"] > 0,
                f"r*={cal['r_star']}，可用上界={cal['usable_max']}，{cal['note']}"))

    # ④ 两个现成语料**都在退化极端**，而且原因相反
    cases = _degenerate_cases()
    deg0 = [n for n, v, d in cases if not n.startswith("**中间")
            and F.calibrate(d, v)["degenerate_at_zero"]]
    flat = [n for n, v, d in cases if not n.startswith("**中间")
            and len({x for _k, x in F.radius_curve(d, v)}) == 1
            and F.calibrate(d, v)["r_star"] is None]
    out.append(("两个现成语料都在退化极端（且原因相反）",
                len(deg0) + len(flat) == len([c for c in cases
                                              if not c[0].startswith("**中间")]),
                f"radius=0 就塌成一团：{deg0}；半径再大也并不动：{flat}"))

    # ⑤ 半径 > 0 而不给视图 → 必须报错（不许猜距离）
    try:
        F.foci(pd, radius=2)
        ok, detail = False, "radius>0 不传 views 竟然没报错 —— 那就等于猜了一个距离"
    except ValueError as e:
        ok, detail = True, f"报错：{str(e)[:58]}…"
    out.append(("radius>0 而不给结构图 → 报错，不猜距离", ok, detail))

    # ⑥ 校准的产物必须自带区间与理由，不能只给一个数
    cal2 = F.calibrate(pd, pv)
    out.append(("校准产物带曲线、r*、可用区间与理由",
                set(cal2) >= {"curve", "r_star", "usable_max", "suggested", "note"},
                f"字段 {sorted(cal2)}"))

    return out


def report() -> list:
    rows = []
    for name, views, div in _degenerate_cases():
        cal = F.calibrate(div, views)
        rows.append((name, f"曲线 {cal['curve']}  r*={cal['r_star']}"))
        rows.append(("  └ 判定", cal["note"]))
    rows.append(("结论",
                 "半径只在**中间地带**有用：并集图连通、且分歧稀疏到 "
                 "radius=0 还能给出 >1 个焦点。两个现成语料都不在那里 —— "
                 "一个是并得太早，一个是永远并不上。**都不是实现 bug。**"))
    rows.append(("校准怎么发生",
                 "r* 由结构算出，数据一多自动重算；`curve` 每次都报出来，"
                 "所以「换了值」永远看得见（`synthesis.provenance.focus_radius`）"))
    return rows


if __name__ == "__main__":
    import sys
    for t, v in report():
        print(f"  {t:<40} {v}")
    print()
    bad = 0
    for t, ok, d in run_all():
        print(f"  {'过    ' if ok else '**红的**'} {t:<46} {d}")
        bad += 0 if ok else 1
    sys.exit(1 if bad else 0)
