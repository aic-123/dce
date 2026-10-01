"""观点群共识的检查。

---
这一节在验什么
-------------

`analysis/consensus.py` 的一般形式是：

    CONSENSUS(u)  ⇔  **每一个观点群**里都至少有一个视图含有 u

而 `groups=None`（每个视图自成一群）**退化成合取** —— 也就是加这个参数之前的行为。
所以要验四件事：

    ① **向后兼容**：`groups=None` 与 `groups_singleton` 与旧行为**逐位相同**
    ② **群划分必须合法**：互不相交、覆盖无漏、非空；不合法就**报错，不悄悄补齐**
    ③ **退化端要被抓出来**：群只有一个时，共识 ≡「至少一个视图含它」，
       于是全体单元都成了共识 —— 那句话没有信息，必须标出来
    ④ ⚠️ **机制得在某个地方真的能工作**

第 ④ 条是这一节的重点。实测下来：

    立场材料（P1 ⊊ P3，三个立场）  群划分**一条都没救回**（没有任何单元的
                                   present 恰好是 {P2,P3}）
    真实语料（按体裁切四片）       四片是**同一个知识库的切面**，不是四个立场 ——
                                   正确的分法是**一个群**，于是退化

**两份现成材料都不触发它。** 所以不能就此收工 ——
一个从没被触发过的机制与一个坏掉的机制在输出上长得一样。
第四节用一个合成材料把它**逼出来**：造一组让精炼关系只吞掉两个视图、
而第三个视图与它们不可比，于是有一个单元**只靠群覆盖才够格当共识**。
"""

from __future__ import annotations

from analysis import consensus as C


def _view(vid, nodes, edges=()):
    from core import view as V
    return V.make_view(view_id=vid, source_ref=f"x://{vid}",
                       source_kind="experiment", nodes=sorted(nodes),
                       edges=[{"from": a, "to": b, "relation": r}
                              for a, b, r in edges])


def _rescue_case():
    """**逼出机制**的合成材料。

        A = {x}          B = {x, y}        C = {w, y}

    `A ⊊ B` → A、B 并成同一个群；而 C 与 A、B **都不可比** → C 自成一群。
    于是 `y` 只出现在 B 与 C 里：

        合取（singleton）  y 缺在 A 里        → **不是共识**
        观点群            {A,B} 由 B 覆盖 ✓
                          {C}   由 C 覆盖 ✓  → **是共识**

    **这就是「同一个立场被两个视图重复表达」要处理的事。**
    """
    return [_view("A", ["x"]),
            _view("B", ["x", "y"]),
            _view("C", ["w", "y"])]


def run_all() -> list:
    out = []

    # ① 向后兼容：groups=None 与 singleton 与旧行为逐位相同
    from generators import positions as POS
    from analysis import divergence as D
    pv, _i = POS.build()
    base = C.consensus(pv)
    same = C.consensus(pv, C.groups_singleton(pv))
    out.append(("向后兼容：`groups=None` ≡ 每视图自成一群 ≡ 加入参数之前的行为",
                base == same and len(base) == 7,
                f"两者都给 {len(base)} 条，**逐位相同**；"
                f"立场材料上共识 {len(base)}/{len(C.universe(pv))} 条"))

    # ② 群划分不合法要**报错，不悄悄补齐**
    bad_cases = [
        ("重叠", [frozenset({"P1", "P2"}), frozenset({"P2", "P3"})]),
        ("漏掉", [frozenset({"P1"}), frozenset({"P2"})]),
        ("多出", [frozenset({"P1", "P2", "P3", "P9"})]),
        ("空群", [frozenset({"P1", "P2", "P3"}), frozenset()]),
        ("没有群", []),
    ]
    msgs = []
    ok_all = True
    for name, g in bad_cases:
        try:
            C.consensus(pv, g)
            ok_all = False
            msgs.append(f"{name}: **竟然没报错**")
        except C.ConsensusError as e:
            msgs.append(f"{name}: {str(e)[:34]}")
    out.append(("群划分不合法时报错，**不悄悄补齐**", ok_all, "；".join(msgs)))

    # ③ 退化端被抓出来：一个群 ⟹ 共识 ≡「至少一个视图含它」⟹ 全体
    one = [frozenset({"P1", "P2", "P3"})]
    cons1 = C.consensus(pv, one)
    rows = C.consensus_curve(pv)
    out.append(("退化端：群只有一个时共识扩到全体，**并被标出来**",
                len(cons1) == len(C.universe(pv))
                and rows["singleton"]["degenerate"] is False,
                f"一个群时共识 {len(cons1)}/{len(C.universe(pv))} 条"
                "（= 全体，**这句话没有信息**）；"
                "而 singleton 那条没被标退化 —— 判据分得清"))

    # ④ ⚠️ **机制得真的能工作**（两份现成材料都不触发它）
    rv = _rescue_case()
    g = C.groups_from_refinement(rv)
    cons_flat = C.consensus(rv)
    cons_grp = C.consensus(rv, g)
    y_flat = any(r["unit"]["key"] == "y" for r in cons_flat)
    y_grp = [r for r in cons_grp if r["unit"]["key"] == "y"]
    out.append(("⚠️ 机制**真的能工作**：合成材料上有一个单元只靠群覆盖才够格",
                g is not None and len(g) == 2 and not y_flat and bool(y_grp),
                f"群 {[sorted(x) for x in g]}；单元 y —— 合取下 "
                f"{'是' if y_flat else '**不是**'}共识，观点群下 "
                f"{'**是**' if y_grp else '不是'}共识"
                f"（逐群覆盖 {y_grp[0]['covering'] if y_grp else '-'}）"))

    # ⑤ 精炼关系的**传递闭包**（链上三个视图应当并成一个群）
    chained = [_view("A", ["x"]), _view("B", ["x", "y"]), _view("C", ["x", "y", "z"])]
    gc = C.groups_from_refinement(chained)
    out.append(("精炼关系取**传递闭包**（A⊊B⊊C → 同一个群）",
                gc is not None and len(gc) == 1
                and set().union(*gc) == {"A", "B", "C"},
                f"群 {[sorted(x) for x in gc]} —— 链条上三个视图并成一个"))

    # ⑥ 没有精炼关系时**返回 None**（不是一组单元素群）
    #
    # 「没有关系」与「有关系但恰好都是单的」是两件事，不能混。
    from analysis import divergence as DV
    disjoint = [_view("A", ["x"]), _view("B", ["p"]), _view("C", ["q"])]
    out.append(("没有精炼关系时返回 `None`，不是一组单元素群",
                C.groups_from_refinement(disjoint) is None
                and DV.refinement_pairs(disjoint) == [],
                "「没有关系」与「有关系但恰好都是单的」是两件事"))

    # ⑦ 确定性
    a = C.groups_from_refinement(rv)
    b = C.groups_from_refinement(list(reversed(rv)))
    out.append(("确定性：输入逆序不改变群划分",
                a == b and a is not None,
                f"{[sorted(x) for x in a] if a else None}"))

    # ⑧ ⚠️ 两份**现成材料**都不触发 —— 这是事实，要报出来
    from checks import realdata as RD
    from adapters import scaffold as SC
    dist = {}
    for u in C.universe(pv):
        dist[tuple(C.present_in(pv, u))] = dist.get(tuple(C.present_in(pv, u)), 0) + 1
    rescue = dist.get(("P2", "P3"), 0)
    ok8 = rescue == 0 and rows["refinement"]["n_consensus"] == rows["singleton"]["n_consensus"]
    detail = (f"立场材料：present 恰好为 (P2,P3) 的单元 {rescue} 条 → "
              f"群划分救回 0 条（共识数 {rows['refinement']['n_consensus']} "
              f"= {rows['singleton']['n_consensus']}，**没变**）")
    pv2, _i2 = POS.build()
    if rd_ok := (RD.corpus_dir() is not None):
        nodes = SC.load_corpus_dir(RD.corpus_dir())
        rviews = [av.view for av in SC.split_views(nodes, split_by="source.kind")]
        if len(rviews) >= 2:
            rc = C.consensus_curve(rviews)
            all_one = C.consensus(rviews, [frozenset(v["id"] for v in rviews)])
            detail += (f"；真实语料：四片是**同一个知识库的切面**，正确的分法是"
                       f"一个群 → 共识 {len(all_one)}/{len(C.universe(rviews))} 条"
                       "（**退化**，被标出来）")
    out.append(("⚠️ 两份现成材料都**不触发**这个机制（事实，不是缺点）", ok8, detail))

    # ⑨ **材料自己声明的群**，以及它与「精炼导出」是否一致
    #
    # 两条**独立的路**导出了同一个分组，那本身是个信号：
    # 作者说「P3 是 P1 的变体」，而结构说 `units(P1) ⊊ units(P3)` —— 两者吻合。
    decl = C.groups_from_metadata(pv)
    ref = C.groups_from_refinement(pv)
    norm = lambda gs: sorted(sorted(g) for g in gs)
    out.append(("材料声明的群与精炼导出的群**一致**（两条独立的路）",
                C.has_declared_groups(pv) and norm(decl) == norm(ref),
                f"声明 {norm(decl)}；精炼 {norm(ref)} —— "
                "作者说「P3 是 P1 的变体」，结构与之一致"))

    # ⑩ **声明优先于推导**（两者不一致时）
    #
    # 声明的群是**材料对它自己结构的陈述**，比算法导出的更可信。
    from core import view as V
    def mkg(vid, nodes, group):
        return V.make_view(view_id=vid, source_ref=f"x://{vid}",
                           source_kind="experiment", nodes=sorted(nodes),
                           edges=[], metadata={"group": group})
    # A ⊊ B（精炼会并成一群），但作者声明 A、B 是**两个**立场
    vs = [mkg("A", ["x"], "立场一"), mkg("B", ["x", "y"], "立场二"),
          mkg("C", ["x"], "立场一")]
    g_auto, rule_auto = C.groups_for(vs, "auto")
    g_ref = C.groups_from_refinement(vs)
    out.append(("**声明优先于推导**（不一致时以声明为准）",
                rule_auto == "declared" and norm(g_auto) != norm(g_ref),
                f"auto 用 {rule_auto} → {norm(g_auto)}；而精炼会导出 "
                f"{norm(g_ref)} —— 声明赢。**材料对它自己结构的陈述比算法导出的可信**"))

    # ⑪ 声明**不完整**就报错，不悄悄补齐
    partial = [mkg("A", ["x"], "立场一"), V.make_view(
        view_id="B", source_ref="x://B", source_kind="experiment",
        nodes=["x", "y"], edges=[])]      # 这个没声明
    try:
        C.groups_from_metadata(partial)
        out.append(("声明不完整时报错，不悄悄补齐", False, "**竟然没报错**"))
    except C.ConsensusError as e:
        out.append(("声明不完整时报错，不悄悄补齐",
                    "不补默认值" in str(e),
                    f"报错：{str(e)[:56]}… —— "
                    "「没声明的那部自成一群」会让产物看起来正常而含义已变"))

    # ⑫ 诊断：分群**只会放宽**，绝不会收紧（`n_lost` 恒为 0）
    d = C.consensus_diagnostic(pv)
    out.append(("诊断：分群只会放宽共识（`n_lost` 恒为 0）",
                d["n_lost"] == 0 and d["n_consensus_grouped"] >= d["n_consensus_flat"],
                f"合取 {d['n_consensus_flat']} → 分群 {d['n_consensus_grouped']}，"
                f"救回 {d['n_rescued']}、丢失 {d['n_lost']} —— "
                "分群是**放宽合取**（每群至少一个），不可能收紧"))

    # ⑬ **禁词守卫抓到过这个键名**
    #
    # 第一版诊断的键叫 `verdict`，而 `verdict` 在 `synthesis.FORBIDDEN_KEYS` 里
    # （§二十 禁真值判断），产物检查当场拦住。改成 `reading`（读法）：
    # 它说的是「这份材料的结构能支持什么」，不是「这份材料对不对」。
    from analysis import synthesis as SY
    hits = SY.forbidden_keys_in({"consensus_diagnostic": d})
    out.append(("⚠️ 诊断的键名不撞禁词表（`verdict` → `reading`）",
                not hits,
                f"命中 {hits}" if hits else
                "`reading` 不在禁词表里 —— 第一版叫 `verdict` 被守卫拦住了。"
                "**守卫响了就改东西，不许豁免**（本仓库第二次栽在这上面，"
                "上一次是字段叫 `rank`）"))

    # ⑭ `build` 的默认**不改行为**，而 `auto` 会取声明
    from analysis import synthesis as S2
    s_def = S2.build(pv)
    s_auto = S2.build(pv, consensus_rule="auto")
    out.append(("`build` 默认用 singleton（不改行为），`auto` 才取声明",
                s_def["provenance"]["consensus_rule"] == "singleton"
                and s_auto["provenance"]["consensus_rule"] == "declared"
                and len(s_def["consensus"]["records"])
                == len(s_auto["consensus"]["records"]),
                "默认 singleton，共识 7 条；`auto` → declared，共识也是 7 条。"
                "⚠️ **默认必须是 singleton**：改成 auto 后 C2/C3 从 600/600 "
                "掉到 456/600，因为合成语料本来就植入精炼关系"))

    return out


def report() -> list:
    from generators import positions as POS
    from analysis import divergence as D
    pv, _i = POS.build()
    rows = []
    rows.append(("立场材料", "P1 ⊊ P3 → 群 {P1,P3} 与 {P2}"))
    for rule, r in C.consensus_curve(pv).items():
        if "skipped" in r:
            rows.append((f"  {rule}", r["skipped"]))
            continue
        flag = "  **退化**" if r["degenerate"] else ""
        rows.append((f"  {rule}",
                     f"共识 {r['n_consensus']}/{r['n_units']} 条，{r['n_groups']} 个群"
                     f" {r['groups']}{flag}"))
    rv = _rescue_case()
    g = C.groups_from_refinement(rv)
    rows.append(("合成（逼出机制）", f"A⊊B、C 与它们不可比 → 群 {[sorted(x) for x in g]}"))
    for tag, cons in (("合取", C.consensus(rv)), ("观点群", C.consensus(rv, g))):
        keys = [r["unit"]["key"] for r in cons]
        rows.append((f"  {tag}", f"共识 {keys} —— y {'不在' if tag == '合取' else '**在**'}其中"))
    rows.append(("读法",
                 "机制**正确但现成材料不触发**。而「一个从没被触发过的机制」与"
                 "「一个坏掉的机制」在输出上长得一样 —— 所以合成那一节是必需的。"))
    return rows


if __name__ == "__main__":
    import sys
    print("── 度量 ──")
    for t, v in report():
        print(f"  {t:<18} {v}")
    print("\n── 断言 ──")
    bad = 0
    for t, ok, d in run_all():
        print(f"  {'过    ' if ok else '**红的**'} {t:<52} {d}")
        bad += 0 if ok else 1
    sys.exit(1 if bad else 0)
