"""概念格与二级概括的检查。

---
这一层守的三条
-------------

一、**`Sep` 用独立实现交叉核对。** 主实现按「外延严格包含且无中间者」算覆盖关系，
   本模块另写一个**直接按定义**的暴力版本（对每个概念，枚举它的全部下位概念，
   取极大的那些），两者必须逐位相等。**判据写两遍就一定会漂** ——
   这个仓库吃过一次亏（`refinement`），所以两遍要写，但**必须是两条独立的路径**。

二、**格不会爆，而爆了要拒绝不要截断。** 截断过的格与真正的格在输出上长得一样，
   而 `Sep` 依赖覆盖关系，截断会把它算错。

三、**二级概括不是「总是更好」，显示规则必须是结构性的。**
   实测：桶大时它概括（真实语料 192 条 → 25 条，7.7x），
   桶小时它只是展开（立场材料 20 条 → 22 条，0.9x）。
   规则是「二级概念数 < 桶内记录数」。**没有阈值。**
"""

from __future__ import annotations

from analysis import concepts as K


def _brute_separation(concepts: list) -> dict:
    """**独立实现**：直接按定义算 `Sep`。

    对每个概念 C：先取它的**全部**真下位概念（外延 ⊊ Ext(C) 的那些），
    再从中挑出**极大**的作为直接子概念，最后
    `Sep = |Ext(C)| − |∪ 直接子概念的外延|`。

    与主实现的路径不同：主实现是先 `e < ext` 再筛「没有中间者」，
    这里是先取全部下位再取极大。**两条路算出来的必须一样。**
    """
    extents = [c[1] for c in concepts]
    out = {}
    for _int, ext in concepts:
        downs = [e for e in extents if e < ext]
        kids = [e for e in downs if not any(e < m for m in downs if m != e)]
        covered = set()
        for k in kids:
            covered |= set(k)
        out[ext] = len(ext) - len(covered)
    return out


def _positions():
    from generators import positions as POS
    views, _i = POS.build()
    return views


def run_all() -> list:
    from analysis import divergence as D
    from analysis import focus as F
    out = []

    views = _positions()
    d = D.analyse(views)
    recs = F._all_records(d)

    # ① 形式背景的形状
    ctx = K.context(recs, views)
    out.append(("形式背景：对象 = 记录，属性 = 特征",
                ctx["n_objects"] == len(recs) and ctx["n_attrs"] > 0,
                f"{ctx['n_objects']} 条记录 × {ctx['n_attrs']} 个特征"))

    # ② 每个对象至少在闭包里 —— 即 R1 覆盖
    lat = K.lattice(recs, views)
    covered = set()
    for s in lat["seps"]:
        covered |= set(s["extent"])
    out.append(("R1 覆盖：每条记录至少在一个概念的外延里",
                len(covered) == len(recs),
                f"{len(covered)}/{len(recs)} 条被覆盖；"
                f"全格 {lat['n_concepts']} 个概念"))

    # ③ **`Sep` 的独立实现交叉核对**
    mine = {s["extent"]: s["sep"] for s in lat["seps"]}
    brute = _brute_separation(lat["seps"] and
                              [(s["intent"], s["extent"]) for s in lat["seps"]])
    diff = [(e, mine[e], brute[e]) for e in mine if mine[e] != brute.get(e)]
    out.append(("`Sep` 两条独立路径逐位一致",
                not diff and len(mine) == len(brute),
                f"不符 {diff[:3]}" if diff else
                f"{len(mine)} 个概念的 Sep 两条路径全部相同"))

    # ④ 非冗余 + 冗余 = 全格
    out.append(("非冗余（Sep>0）与冗余（Sep=0）恰好划分全格",
                len(lat["irredundant"]) + len(lat["redundant"]) == lat["n_concepts"],
                f"非冗余 {len(lat['irredundant'])} + 冗余 {len(lat['redundant'])} "
                f"= {lat['n_concepts']}"))

    # ⑤ 规模：不爆，且**超限时拒绝而不是截断**
    from checks import realdata as RD
    from adapters import scaffold as SC
    dd = RD.corpus_dir()
    sizes = [("立场材料", len(recs), lat["n_concepts"])]
    if dd:
        nodes = SC.load_corpus_dir(dd)
        rv = [a.view for a in SC.split_views(nodes, split_by="source.kind")]
        if len(rv) >= 2:
            rd = D.analyse(rv)
            rrecs = F._all_records(rd)
            rlat = K.lattice(rrecs, rv)
            sizes.append(("真实语料", len(rrecs), rlat["n_concepts"]))
    out.append(("规模：格在本仓库的量级上不爆",
                all(nc < 10 * n + 500 for _n, n, nc in sizes),
                "；".join(f"{n} 记录 → {nc} 概念" for n, _x, nc in
                          [(a, b, c) for a, b, c in sizes])))
    try:
        K.lattice(recs, views, max_concepts=5)
        out.append(("超限时拒绝而不是截断", False, "竟然没报错"))
    except K.ConceptError as e:
        out.append(("超限时拒绝而不是截断（截断过的格算不对 Sep）",
                    "拒绝算" in str(e), f"报错：{str(e)[:56]}…"))

    # ⑥ 显示规则：桶大时概括、桶小时只是展开 —— **两边都要出现**
    s_pos = K.second_level_summary(d, views)
    out.append(("二级：小桶上它只是**展开**（所以要能识别出来）",
                s_pos["level2_compression"] < 2,
                f"立场材料 {s_pos['n_records']} 条 → 一级 "
                f"{s_pos['n_level1']} + 二级 {s_pos['n_level2']} = "
                f"{s_pos['total_after_level2']} 条（{s_pos['level2_compression']:.1f}x）"
                " —— **二级不是总是更好**"))
    if dd and len(rv) >= 2:
        s_real = K.second_level_summary(rd, rv)
        out.append(("二级：大桶上它**概括**（7x 以上）",
                    s_real["level2_compression"] > 3,
                    f"真实语料 {s_real['n_records']} 条 → 一级 "
                    f"{s_real['n_level1']} + 二级 {s_real['n_level2']} = "
                    f"{s_real['total_after_level2']} 条"
                    f"（{s_real['level2_compression']:.1f}x）"))

    # ⑦ 过滤开关按**结构判据**工作（不是阈值）
    lv2_all = K.second_level(d, views, only_if_compresses=False)
    lv2_flt = K.second_level(d, views, only_if_compresses=True)
    dropped = [e["parent"] for e, f2 in zip(lv2_all, lv2_flt)
               if e["concepts"] and not f2["concepts"]]
    out.append(("显示规则：`only_if_compresses` 只滤掉「展开」的那些桶",
                all(e["expands"] for e, f2 in zip(lv2_all, lv2_flt)
                    if e["concepts"] and not f2["concepts"]),
                f"滤掉 {dropped}（判据是「二级概念数 ≥ 桶内记录数」，无阈值）"))

    # ⑧ 确定性
    a = [(e["parent"], tuple(e["concepts"] and
                             [(c["intent"], c["sep"]) for c in e["concepts"]] or ()))
         for e in K.second_level(d, views)]
    b = [(e["parent"], tuple(e["concepts"] and
                             [(c["intent"], c["sep"]) for c in e["concepts"]] or ()))
         for e in K.second_level(D.analyse(list(reversed(views))), views)]
    out.append(("确定性：输入逆序不改变二级结果", a == b,
                f"{len(a)} 个一级焦点" + ("" if a == b else "，逆序后不同")))

    return out


def report() -> list:
    from analysis import divergence as D
    from analysis import focus as F
    rows = []
    views = _positions()
    d = D.analyse(views)
    s = K.second_level_summary(d, views)
    rows.append(("立场材料", f"{s['n_records']} 条 → 一级 {s['n_level1']}（"
                             f"{s['level1_compression']:.1f}x）→ "
                             f"一+二级 {s['total_after_level2']} "
                             f"({s['level2_compression']:.1f}x)  **展开**"))
    from checks import realdata as RD
    from adapters import scaffold as SC
    dd = RD.corpus_dir()
    if dd:
        nodes = SC.load_corpus_dir(dd)
        rv = [a.view for a in SC.split_views(nodes, split_by="source.kind")]
        if len(rv) >= 2:
            sr = K.second_level_summary(D.analyse(rv), rv)
            rows.append(("真实语料", f"{sr['n_records']} 条 → 一级 {sr['n_level1']}（"
                                    f"{sr['level1_compression']:.0f}x）→ "
                                    f"一+二级 {sr['total_after_level2']} "
                                    f"({sr['level2_compression']:.1f}x)  **概括**"))
            for e in sr["levels"][:2]:
                rows.append((f"  {e['parent']} {e['label']}",
                             f"{e['n_records']} 条 → 二级 {len(e['concepts'])} 条"))
                for c in e["concepts"][:3]:
                    rows.append((f"     Sep={c['sep']}", c["label"]))
    rows.append(("位置", "**二级的正确位置是「桶大时展开一层」**，不是替换一级。"
                         "全格在立场材料上是 62 个概念 > 20 条记录 —— 它违反 R2。"))
    return rows


if __name__ == "__main__":
    import sys
    print("── 度量 ──")
    for t, v in report():
        print(f"  {t:<34} {v}")
    print("\n── 断言 ──")
    bad = 0
    for t, ok, d in run_all():
        print(f"  {'过    ' if ok else '**红的**'} {t:<52} {d}")
        bad += 0 if ok else 1
    sys.exit(1 if bad else 0)
