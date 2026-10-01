"""分歧 —— 四种类型，**分类必须互斥**。

---
为什么要强调互斥
---------------

`§十五 Test 3` 的要求是：

    人工植入 10 contradictions / 20 omissions / 10 refinements / 5 alternatives，
    **DCE 必须能够分别恢复它们。**

如果分类不互斥，这个测试就**在构造上不可能通过** —— 一次精炼会同时被报成
一堆 omission，恢复出来的数字全错，而且看不出错在哪。

所以本模块**定死一个优先顺序**，每个单元最多落进一类：

    ① refinement   先认领：它解释掉的单元，不再参与 omission
    ② contradiction 同一对端点上的互斥关系
    ③ alternative   同一 source 下互不包含的后继集合
    ④ omission     剩下的「有人有、某视图没有，且那个视图没有表态反对」

⚠️ **这个顺序是我定的一条判据**，属于 `§T4.1` 的 B 类（判据，可能触碰不变量），
所以它不能只是说法：`test_types_are_disjoint` 会构造四类同时出现的输入，
断言没有任何单元落进两类。

---
`omission` 与 `contradiction` 的分界（§五·三，v2 最重要的修改）
-------------------------------------------------------------

    A 有 X     B 没有 X        ⟹  omission
    A 说 supports X   B 说 contradicts X   ⟹  contradiction

所以 omission 的判据里必须**排除**「那个视图对同一对端点说了互斥的话」：

    对边 (f, t, r) 而言，视图 v 算是 omission ⟺
        v 没有 (f,t,r)  ∧  v 没有 (f,t,r') 且 r' 与 r 互斥

第二项就是「B 不是没表态，是表了相反的态度」——那种情况归 contradiction。
"""

from __future__ import annotations

from core import edge as E
from core import provenance as prov

from . import consensus as C


def _ids(views) -> list:
    return sorted(v["id"] for v in views)


def refinement_pairs(views) -> list:
    """`(较粗, 较细)` 的视图对：较粗的单元集是较细的**真子集**，且**非空**。

    §五·四 的例子：A 有 X；B 有 X→Y、X→Z。B 的单元集严格包含 A 的。

    用**单元集**（节点 ∪ 边）而不是只用边，因为 §五·四 的例子里 X 本身也在其中。

    ⚠️ **「非空」这个条件是冒烟测出来的，不是一开始就有的。**
    少了它，一个**什么都没说**的视图（单元集 = ∅）会被判成"较粗"，
    于是它缺的每一样都被 refinement 吞掉 —— 而 omission 永远是 0。
    §五·三 的例子 `A → X, B → ∅, C → X` 正是这种情形：B 什么都不说，
    那要报的是 **omission**，不是 refinement。空集是任何集合的子集，
    但「什么都没说」不是「说得比较粗」。
    """
    out = []
    for a in views:
        ua = C.units_of(a)
        if not ua:
            continue                         # 空视图不充当「较粗」的那一侧
        for b in views:
            if a["id"] == b["id"]:
                continue
            ub = C.units_of(b)
            if ua < ub:                      # 真子集
                out.append((a["id"], b["id"]))
    return sorted(out, key=lambda p: (p[0], p[1]))


def refinement(views) -> list:
    """精炼记录。**它不是冲突** —— §六 的树里它是单独的粒度差异一类。"""
    out = []
    by_id = {v["id"]: v for v in views}
    for coarse, fine in refinement_pairs(views):
        extra = C.units_of(by_id[fine]) - C.units_of(by_id[coarse])
        for u in sorted(extra, key=lambda x: (x[0], str(x[1]))):
            kind, key = u
            out.append({
                "type": "refinement",
                "not_a_conflict": True,       # §五·四：这不是分歧，是粒度差异
                "coarse": coarse,
                "fine": fine,
                "unit": {"kind": kind, "key": key},
                "sources": prov.make(
                    prov.ref(coarse, kind, key) if u in C.units_of(by_id[coarse])
                    else prov.ref(fine, kind, key),
                    prov.ref(fine, kind, key),
                ) if u in C.units_of(by_id[coarse]) else prov.make(
                    prov.ref(fine, kind, key)),
            })
    return out


def refinement_covered(view, views) -> set:
    """这个视图里「被 refinement 解释掉」的单元（= 它缺、但更细的那个视图有的）。

    ⚠️ 判据与 `refinement_pairs()` **共用同一份**，不另写一套。
    第一版这里自己写了一遍 `uv < uo`，于是 `refinement_pairs` 加上的
    「粗的那一侧非空」没有同步过来 —— 一个空视图仍然被当成较粗的一侧，
    它缺的每一样都被吞掉，omission 变成 0。**判据写两遍就一定会漂。**
    """
    covered = set()
    by_id = {v["id"]: v for v in views}
    uv = C.units_of(view)
    for coarse, fine in refinement_pairs(views):
        if coarse == view["id"]:
            covered |= (C.units_of(by_id[fine]) - uv)
    return covered


def contradiction(views) -> list:
    """同一对端点上、被声明为互斥的两种关系。

    只比 `(from, to)` 而**不比方向反向**：`A supports B` 与 `B supports A` 是两条不同的边
    （§九），它们不构成矛盾，只是两个方向各说了一件事。
    """
    out = []
    # 按 (from, to) 归拢各视图给出的 relation
    pairs: dict[tuple, dict] = {}
    for v in views:
        for e in v["edges"]:
            pairs.setdefault((e["from"], e["to"]), {}).setdefault(v["id"], set()).add(
                e["relation"])
    for (f, t), by_view in sorted(pairs.items()):
        rels = sorted({r for rs in by_view.values() for r in rs})
        for i in range(len(rels)):
            for j in range(i + 1, len(rels)):
                r1, r2 = rels[i], rels[j]
                if not E.exclusive(r1, r2):
                    continue
                # 互斥的两种关系必须来自**不同**的视图，同一视图内部矛盾不算跨视图分歧
                v1 = sorted(vid for vid, rs in by_view.items() if r1 in rs)
                v2 = sorted(vid for vid, rs in by_view.items() if r2 in rs)
                if set(v1) & set(v2):
                    continue
                # 反向边（t, f）也参与判断：若两视图在反向上一致，不抵消本矛盾
                out.append({
                    "type": "contradiction",
                    "from": f, "to": t,
                    "relations": {r1: v1, r2: v2},
                    "sources": prov.make(
                        *[prov.ref(x, "edge", (f, t, r1)) for x in v1],
                        *[prov.ref(x, "edge", (f, t, r2)) for x in v2],
                    ),
                })
    return out


def alternative(views) -> list:
    """同一 source 下、后继集合**互不包含**的差异（§六）。

    §六：A: X→Y，B: X→Z，`Y ≠ Z`，且没有明确的 `contradicts` 边。

    判据（无参数）：对某个 `(source, relation)`，两个视图的后继集合
    **谁也不是谁的子集**。若一个是另一个的子集，那不是竞争解释，而是
    refinement 或 omission —— 那两类各自认领。
    """
    # (source, relation) -> {view_id: {target, ...}}
    succ: dict[tuple, dict] = {}
    for v in views:
        for e in v["edges"]:
            succ.setdefault((e["from"], e["relation"]), {}).setdefault(
                v["id"], set()).add(e["to"])

    out = []
    for (src, rel), by_view in sorted(succ.items()):
        vids = sorted(by_view)
        for i in range(len(vids)):
            for j in range(i + 1, len(vids)):
                a, b = vids[i], vids[j]
                sa, sb = by_view[a], by_view[b]
                if sa <= sb or sb <= sa:
                    continue                 # 子集关系 → 不是竞争解释
                out.append({
                    "type": "alternative",
                    "source": src,
                    "relation": rel,
                    "views": {a: sorted(sa), b: sorted(sb)},
                    "sources": prov.make(
                        *[prov.ref(a, "edge", (src, x, rel)) for x in sorted(sa)],
                        *[prov.ref(b, "edge", (src, x, rel)) for x in sorted(sb)],
                    ),
                })
    return out


def _has_exclusive_counterpart(view, f, t, r) -> bool:
    """这个视图是否在 (f,t) 上说了与 r 互斥的话。"""
    for e in view["edges"]:
        if e["from"] == f and e["to"] == t and E.exclusive(e["relation"], r):
            return True
    return False


def omission(views) -> list:
    """某视图没有表达某结构，**且没有表态反对**（§五·三）。

    排除两类，各有理由：

    - **被 refinement 解释掉的**：更细的视图多出来的那些单元，那是粒度差异，
      §五·四 明说「这不是分歧」。
    - **有互斥对应的**：那是 contradiction（§五·三：不能把「B 说相反的话」
      读成「B 没说」）。这正是 v2 要修的那个错。
    """
    ref_covered = {v["id"]: refinement_covered(v, views) for v in views}
    contra_pairs = {(c["from"], c["to"]) for c in contradiction(views)}

    out = []
    for v in views:
        for u in sorted(C.universe(views), key=lambda x: (x[0], str(x[1]))):
            if u in C.units_of(v):
                continue
            if u in ref_covered[v["id"]]:
                continue
            kind, key = u
            if kind == "edge":
                f, t, r = key
                if _has_exclusive_counterpart(v, f, t, r):
                    continue
                if (f, t) in contra_pairs:
                    continue
            else:
                # 节点缺失：若该视图有一条指向它的边 —— 不可能（verify 保证端点在内）。
                # 但若该视图**完全不涉及**这个节点所在的任何边，那仍算 omission。
                pass
            out.append({
                "type": "omission",
                "missing_in": v["id"],
                "unit": {"kind": kind, "key": key},
                "sources": prov.make(
                    *[prov.ref(x, kind, key) for x in C.present_in(views, u)],
                ),
            })
    return out


def analyse(views) -> dict:
    """四类一起算，**按固定顺序**，并把 refinement 先认领掉。"""
    from core import view as V
    V.check_distinct(views)
    return {
        "refinement": refinement(views),
        "contradiction": contradiction(views),
        "alternative": alternative(views),
        "omission": omission(views),
    }
