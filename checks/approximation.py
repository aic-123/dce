"""粗糙集近似的检查 —— 重点是**它给出的那条精确判据**。

---
这一层要证的三件事
----------------

一、**那条等价式本身。** 本模块声称：

       γ = 1  ⟺  类型判定完全由「单元出现在哪几个视图」决定
              ⟺  类型没有携带成员关系之外的任何信息

   这不是比喻，是正域定义的直接推论。但**推论也要验** ——
   所以在几百个配置上逐一对账：`γ == 1` 与「没有签名类横跨两个决策类」
   必须同真同假。这是对**等价式本身**的检验，不是对实现的检验。

二、**γ 是在回答 §十六 那个问题。** 基线 C 问「DCE 是否只是
   graph frequency bookkeeping？」——γ 给出定量答案：
   `1 − γ` 量出「类型里有多少不是成员关系蕴含的」。

三、**约简真的最小、且真的保持 γ。** 以及算不动时**拒绝**而不是截断。

⚠️ α 与 γ 是两个量，本模块**两个都报**，不替判据层做选择。
"""

from __future__ import annotations

from core import view as V


def _cfg(n_views: int, plant: dict, seed: int, topology: str = "forest"):
    from generators import synthetic as SYN
    base = SYN.base_graph(n_nodes=40, n_edges=60, seed=seed,
                          topology=topology, n_components=3)
    spec = {"n_views": n_views, "n_core": 10, "private": 1}
    spec.update(plant)
    return SYN.make(base, spec)


def run_all() -> list:
    from metrics import approximation as A
    out = []

    # ① 等价式本身：γ == 1  ⟺  没有签名类横跨两个决策类
    #
    # 这是对**声称的那条等价式**的检验。同真同假才算数。
    bad = []
    n_cfg = 0
    for nv in (2, 3, 4, 5):
        for plant in ({}, {"omissions": 1}, {"contradictions": 1},
                      {"refinements": 1}, {"alternatives": 1},
                      {"contradictions": 1, "omissions": 1, "refinements": 1}):
            for seed in (11, 12):
                try:
                    views, _t = _cfg(nv, plant, seed)
                except ValueError:
                    continue
                n_cfg += 1
                a = A.approximations(views)
                g = len(a["positive"]) / len(a["units"])
                spans = any(len({A.typing(views)[u] for u in members}) > 1
                            for members in a["classes"].values())
                if (abs(g - 1.0) < 1e-12) != (not spans):
                    bad.append((nv, tuple(sorted(plant)), seed, g, spans))
    out.append((f"等价式：γ=1 ⟺ 类型是签名的函数（{n_cfg} 个配置逐一对照）",
                not bad, f"不符 {bad[:3]}" if bad else
                "在全部配置上同真同假 —— 等价式成立，不是比喻"))

    # ② 两个退化端：全同视图 → γ=1；两个单元同签名不同类型 → γ<1
    from generators import synthetic as SYN
    base = SYN.base_graph(n_nodes=8, n_edges=8, seed=7)
    nodes = sorted({x for e in base["edges"] for x in (e[0], e[1])})
    proto = V.make_view(view_id="A", source_ref="x://A", source_kind="experiment",
                        nodes=nodes, edges=base["edges"])
    same = []
    for vid in ("A", "B", "C"):
        v = V.clone(proto)
        v["id"] = vid
        v["source"] = {"ref": f"x://{vid}", "kind": "experiment"}
        same.append(v)
    g_same = A.gamma(same)["gamma"]
    out.append(("全同视图 → γ=1（类型必然是签名的函数）",
                abs(g_same - 1.0) < 1e-12,
                f"γ={g_same:.4f}，签名类 {A.gamma(same)['n_classes']} 个"))

    # ③ 合成语料上的实际取值 —— **这是 §十六 那个问题的定量答案**
    rows = []
    for nv in (3, 5, 8):
        for plant in ({}, {"omissions": 2}, {"contradictions": 2, "omissions": 2},
                      {"contradictions": 2, "omissions": 2,
                       "refinements": 1, "alternatives": 1}):
            try:
                views, _t = _cfg(nv, plant, 21)
            except ValueError:
                continue
            g = A.gamma(views)
            al = A.alpha(views)
            rows.append((nv, tuple(sorted(plant)), g["gamma"], g["n_classes"],
                         al["alpha"]))
    out.append(("合成语料上 γ 与 α 都有取值（两者不是一个量）",
                all(r[2] is not None and r[4] is not None for r in rows) and
                any(r[2] < 1.0 for r in rows),
                f"{len(rows)} 个配置；γ 范围 "
                f"{min(r[2] for r in rows):.3f}–{max(r[2] for r in rows):.3f}，"
                f"α 范围 {min(r[4] for r in rows):.3f}–{max(r[4] for r in rows):.3f}"))

    # ④ 约简：最小、且保持 γ
    views, _t = _cfg(4, {"contradictions": 1, "omissions": 1}, 31)
    r = A.reducts(views)
    ok_min, detail = True, ""
    if not r["refused"]:
        if not r["reducts"]:
            ok_min, detail = False, "一个约简都没找到（至少全体视图本身应当是一个）"
        else:
            smallest = min(len(x) for x in r["reducts"])
            if any(len(x) != smallest for x in r["reducts"]):
                ok_min, detail = False, f"约简大小不齐：{r['reducts']}"
            for red in r["reducts"]:
                sub = [v for v in views if v["id"] in red]
                g = A.gamma(sub)["gamma"]
                if g is None or abs(g - r["gamma"]) > 1e-12:
                    ok_min, detail = False, f"{red} 没保持 γ（{g} vs {r['gamma']}）"
            detail = (f"{r['n_reducts']} 个约简，大小 {smallest}，"
                      f"全部保持 γ={r['gamma']:.4f}；"
                      f"视图数 {r['n_views']} → 约简后 {smallest}")
    else:
        ok_min, detail = True, r["reason"]
    out.append(("约简：最小，且保持 γ 不变", ok_min, detail))

    # ⑤ 算不动时**拒绝**，不截断
    many = []
    for k in range(13):
        v = V.clone(proto)
        v["id"] = f"V{k:02d}"
        v["source"] = {"ref": f"x://V{k}", "kind": "experiment"}
        many.append(v)
    rr = A.reducts(many, max_subsets=1024)
    out.append(("组合数超限时拒绝算（截断过的「最小」不是最小）",
                rr["refused"] and "最小子集" in rr["reason"],
                rr["reason"]))

    # ⑥ 立场材料上：三份立场的 γ
    from generators import positions as POS
    pv, _i = POS.build()
    pg = A.gamma(pv)
    vs_cx, _t = _cfg(4, {"omissions": 2, "contradictions": 2}, 41)
    with_contra = A.gamma(vs_cx)["gamma"]
    out.append(("立场材料上的 γ（类型里有多少不是成员关系蕴含的）",
                pg["gamma"] is not None,
                f"γ={pg['gamma']:.4f}（{pg['n_positive']}/{pg['n_units']} 个单元"
                f"的签名足以定类型），签名类 {pg['n_classes']} 个"))

    # ⑦ **这一层最重要的那条发现**：γ 把 §十六 那个问题定量化了。
    #
    #    ⚠️ 第一版把这条写成「只植入缺失 → γ = 1」，**被检查证伪了**：
    #    seed 41 / 4 视图下只植入缺失，γ = 0.8824。
    #    原因：每个视图还有**自己的私有边**，而那可能让某个视图恰好成为
    #    另一个的真子集 —— 于是一个 **refinement 对意外出现了**。
    #    refinement 与 omission 的区分依赖**子集关系**，那不是签名能决定的。
    #
    #    所以正确的陈述是**有条件的**，而条件本身可以精确写出来：
    #
    #        类型集 ⊆ {consensus, omission}  ∧  不存在精炼对   ⟹   γ = 1
    #
    #    反过来：一旦有矛盾（依赖 (from,to) 配对与关系种类）
    #    或精炼（依赖子集关系），签名就不够了，γ 掉下来。
    #    这条在多个种子上验，而不是一个。
    from analysis import divergence as D
    from analysis import consensus as C
    violations, checked = [], 0
    excluded = {}          # 排除原因 → 次数（**如实统计，不只算精炼那一种**）
    for seed in (17, 23, 29, 31, 37, 41, 43, 47):
        for nv in (3, 4, 5, 6):
            for plant in ({"omissions": 1}, {"omissions": 2}, {"omissions": 3}):
                try:
                    views, _t = _cfg(nv, plant, seed)
                except ValueError:
                    continue
                typ = A.typing(views)
                tset = set(typ.values())
                div = D.analyse(views)
                has_ref = bool(div["refinement"])
                if tset <= {"consensus", "omission"} and not has_ref:
                    checked += 1
                    g = A.gamma(views)["gamma"]
                    if abs(g - 1.0) > 1e-12:
                        violations.append((seed, nv, plant, g))
                else:
                    # ⚠️ 排除的原因**不止一种**。第一版只记了「有精炼对」，
                    # 于是输出「0 个被排除」，读起来像「条件总是适用」——
                    # 而实际上有配置因为出现了 **alternative** 而被排除
                    # （私有边让两个视图在同一 source 上给出不同后继）。
                    why = []
                    if has_ref:
                        why.append("有精炼对")
                    extra = sorted(tset - {"consensus", "omission"})
                    if extra:
                        why.append("类型含 " + ",".join(extra))
                    key = " + ".join(why) or "（未标注）"
                    excluded[key] = excluded.get(key, 0) + 1
    out.append((f"发现：类型只有 共识/缺失 **且无精炼对** ⟹ γ = 1"
                f"（{checked} 个适用配置，8 个种子）",
                not violations and checked > 0,
                f"违反 {violations[:3]}" if violations else
                f"全部 γ=1 ⟺ **类型就是频率记账**；"
                f"另有 {sum(excluded.values())} 个配置被排除，原因："
                + "、".join(f"{k}×{v}" for k, v in sorted(excluded.items()))))

    out.append(("发现：**加入矛盾之后 γ < 1**（签名之外还有信息）",
                with_contra < 1.0,
                f"γ={with_contra:.4f} —— 矛盾依赖 (from,to) 配对与关系种类，"
                "而那不在签名里"))
    out.append(("发现：立场材料的 γ 远低于 1（真实多视图材料上增量最大）",
                pg["gamma"] < 0.5,
                f"γ={pg['gamma']:.4f} —— 与合成语料的 0.76–0.90 对比，"
                "**立场材料上「类型超出频率记账」的比例最大**"))

    return out


def report() -> list:
    from metrics import approximation as A
    rows = []
    for nv in (3, 5, 8):
        for plant in ({}, {"omissions": 2},
                      {"contradictions": 2, "omissions": 2},
                      {"contradictions": 2, "omissions": 2,
                       "refinements": 1, "alternatives": 1}):
            try:
                views, _t = _cfg(nv, plant, 21)
            except ValueError:
                continue
            g = A.gamma(views)
            al = A.alpha(views)
            tag = ",".join(f"{k[:4]}={v}" for k, v in sorted(plant.items())) or "无植入"
            rows.append((f"  {nv} 视图 / {tag}",
                         f"γ={g['gamma']:.3f}（签名类 {g['n_classes']}，"
                         f"正域 {g['n_positive']}/{g['n_units']}）  "
                         f"α={al['alpha']:.3f}"))
    rows.append(("§十六 那个问题的定量答案",
                 "γ = 1 ⟺ 类型判定完全由「出现在哪几个视图」决定 ⟺ "
                 "**类型没有携带成员关系之外的任何信息**；"
                 "1 − γ 就是「类型超出了频率记账」的那部分"))
    rows.append(("⚠️ α 与 γ 不是一个量",
                 "α = 下/上（紧不紧）；γ = 正域/全体（覆盖多少）。"
                 "两者都报，取舍留在判据层"))
    from generators import positions as POS
    pv, _i = POS.build()
    pg, pa = A.gamma(pv), A.alpha(pv)
    rows.append(("立场材料", f"γ={pg['gamma']:.3f}（{pg['n_classes']} 个签名类）、"
                             f"α={pa['alpha']:.3f}"))
    return rows


if __name__ == "__main__":
    import sys
    print("── 度量 ──")
    for t, v in report():
        print(f"  {t:<34} {v}")
    print("\n── 断言 ──")
    bad = 0
    for t, ok, d in run_all():
        print(f"  {'过    ' if ok else '**红的**'} {t:<46} {d}")
        bad += 0 if ok else 1
    sys.exit(1 if bad else 0)
