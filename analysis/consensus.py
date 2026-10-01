"""共识 —— **合取，不是比例**。

---
这里是 DCE v2 唯一会撞上不变量 #5 的地方，所以先把判据钉死
----------------------------------------------------------

设计稿 §八 给的是：

    support(node) = 出现该节点的 View 数量 / 总 View 数量     （例子 support(X)=0.8）

而 §五·一 给的是：

    CONSENSUS(X)  ⇔  **所有**相关 View 都存在兼容结构

这两句不是一回事。**`support` 是「多少人说」，是频率，是流行度。**
arena `§C9` 不变量 #5 是 `Popularity = Evidence`；`§C7.1 ①` 把
「投票数 / 热度 / 参与量 / 曝光量」列为**禁止**信号，并把推荐定义写得很清楚：

    上层信号**不是「多少人说」，而是「是否在所有观点群里都成立」**。
    ……它的判定条件里就要求**同时**满足所有群，多数派的规模优势被抵消掉了。
    **它在结构上不可能违反 #5，不需要靠人工检查去守。**

所以本模块把 `§C7.1` 的道理照搬过来：

    CONSENSUS(u)  ⇔  u 出现在**全部**输入视图里          （support == (n, n)）
    support(u)    =  (出现了几个, 一共几个)              —— **描述性事实，仅此而已**

**没有阈值，没有「相关视图」这一层过滤。**

---
⚠️ 上面那句原先的推论是错的，这一节是更正
------------------------------------------

第一版从这里推出「MVP 里**相关 = 全部**，没有别的东西可选」，理由是
「`相关` 是个没说清的限定词，落地就是一条线」。

**那个推论混淆了两个不同的东西：**

    「相关 **View**」    哪些视图算数          —— 含糊，落地就是阈值  ✗
    「**观点群**」      视图到立场的一个划分   —— **不含糊，是结构**  ✓

`§C7.1 ①` 的原话是「是否在**所有**观点群里都成立」，那个机制的名字就叫
**观点群**；而它自己也说「不存在观点群时本机制全程休眠」——
**休眠的条件是「没有群」，不是「MVP」**。

所以正确的落地是把一般形式实现出来，而**合取是它在「每个群只有一个视图」
这个退化情形下的特例**：

    CONSENSUS(u)  ⇔  **每一个观点群**里都至少有一个视图含有 u

⚠️ 这条**在结构上不可能违反 #5**，因为它不看任何一边有多少视图：
一个群里的十个视图和一个视图，权重完全一样。

**群从哪来**（两条都是结构性的，不需要阈值）：

    groups_singleton(views)       每个视图自成一群 → **退化成合取**（默认，向后兼容）
    groups_from_refinement(views) 把有**精炼**关系的视图并进同一个群（传递闭包）

第二条的理由就在 §五·三 / §五·四 的判据里：若 `units(A) ⊊ units(B)`，
则 A 与 B 是**同一个东西的两种粒度**，**A 对 B 多出来的那些单元沉默，
不是「反对」，是「说得比较粗」**。既然如此，它在共识判定里就不该算作
一份独立的反对 —— 那正是「观点群」要处理的事（同一立场被多个视图重复表达）。

**退化端要报出来**：若精炼闭包把所有视图并成一个群，则
`CONSENSUS(u) ⇔ u 出现在至少一个视图里`，于是**全体单元都是共识**——
这句话没有信息。`consensus_curve()` 把这一点标出来，不静默接受。


---
三条不许
--------

1. **`support` 不许当排序键。** `support_table()` 按 **key** 排序，不按 support。
   按 support 排就是把「多少人说」变成了「什么重要」，那正是 #5 要防的。
2. **`support` 不许写进源视图。** `§C7.1 ④`：上层结果不得写入底层任何字段。
3. **`support` 不许出现在派生单元的字段里当「强度 / 置信度 / 分数」。**
   它只出现在 `support` 这一个键下，且是 `(n_present, n_total)` 的**元组**，
   不是比例浮点数 —— 元组不容易被顺手拿去比较大小。
"""

from __future__ import annotations

from core import provenance as prov


def units_of(view) -> set:
    """一个视图里的全部结构单元。

    节点是 `("node", id)`，边是 `("edge", (from, to, relation))` ——
    边带上三元组，因为 §九 规定身份就是这三项。
    """
    out = set()
    for n in view["nodes"]:
        out.add(("node", n))
    for e in view["edges"]:
        out.add(("edge", (e["from"], e["to"], e["relation"])))
    return out


def universe(views) -> set:
    """所有视图出现过的单元的并集。**按 key 排序返回列表**（不是按出现次数）。"""
    u = set()
    for v in views:
        u |= units_of(v)
    return set(sorted(u, key=lambda x: (x[0], str(x[1]))))


def support(views, unit) -> tuple:
    """`(出现了几个视图, 一共几个视图)`。**描述性事实。**

    刻意返回**元组而不是比例**：比例是个数，会被顺手拿去过阈值或排序；
    元组只回答「谁有、谁没有」，那才是这个量真正的内容。
    """
    n = sum(1 for v in views if unit in units_of(v))
    return (n, len(views))


def present_in(views, unit) -> list:
    """有它的视图 id，排序（**按 id 排，不按任何权重**）。"""
    return sorted(v["id"] for v in views if unit in units_of(v))


def absent_in(views, unit) -> list:
    """没有它的视图 id，排序。"""
    return sorted(v["id"] for v in views if unit not in units_of(v))


def sources_for(views, unit) -> list:
    """把它出现过的每一处都变成溯源指针。"""
    kind, key = unit
    return prov.make(*[prov.ref(v["id"], kind, key)
                       for v in views if unit in units_of(v)])


def support_table(views) -> list:
    """全部单元的 `support` 清单。**按 key 排序，绝不按 support 排序。**

    这一条是 #5 的可执行形式之一：一个按 support 排过序的表，哪怕只排一次，
    就已经把「多少人说」交付成了「什么重要」。
    """
    rows = []
    for u in sorted(universe(views), key=lambda x: (x[0], str(x[1]))):
        kind, key = u
        rows.append({
            "unit": {"kind": kind, "key": key},
            "support": support(views, u),
            "present": present_in(views, u),
            "absent": absent_in(views, u),
        })
    return rows


class ConsensusError(Exception):
    """群划分不合法。"""


def groups_singleton(views) -> list:
    """每个视图自成一群 —— 共识退化成合取。**默认，向后兼容。**"""
    return [frozenset([v["id"]]) for v in sorted(views, key=lambda v: v["id"])]


def verify_groups(views, groups) -> None:
    """群必须是全部视图的一个**划分**：互不相交、覆盖无漏、非空。

    ⚠️ 不合法就报错，**不悄悄补齐** —— 悄悄补一个群会改变共识的含义，
    而产物看起来一样。
    """
    ids = {v["id"] for v in views}
    flat = [gid for g in groups for gid in g]
    if not groups:
        raise ConsensusError("至少要有一个观点群")
    if any(not g for g in groups):
        raise ConsensusError("观点群不许为空")
    if len(flat) != len(set(flat)):
        raise ConsensusError(f"群必须互不相交，但 {len(flat) - len(set(flat))} "
                             "个视图出现在不止一个群里")
    if set(flat) != ids:
        missing = sorted(ids - set(flat))
        extra = sorted(set(flat) - ids)
        raise ConsensusError(f"群必须覆盖全部视图；漏了 {missing}，多出 {extra}")


def groups_from_refinement(views) -> list:
    """把有**精炼**关系的视图并进同一个观点群（**传递闭包**）。

    理由（就在本仓库 §五·三 / §五·四 的判据里）：若 `units(A) ⊊ units(B)`，
    则 A 与 B 是**同一个东西的两种粒度** —— A 对 B 多出来的那些单元沉默，
    **不是「反对」，是「说得比较粗」**。既然不是反对，它在共识判定里
    就不该算一份独立的反对。那正是「观点群」要处理的事。

    **不需要阈值**：精炼关系本身就是判据里的严格包含。
    视图之间没有精炼关系时返回 `None`（**不是**返回一组单元素群）——
    那两件事不同：「没有关系」与「有关系但恰好都是单的」要说清。
    """
    from analysis import divergence as D
    pairs = D.refinement_pairs(views)
    if not pairs:
        return None
    parent = {v["id"]: v["id"] for v in views}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in pairs:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra
    buckets: dict[str, set] = {}
    for vid in parent:
        buckets.setdefault(find(vid), set()).add(vid)
    return [frozenset(s) for s in
            sorted(buckets.values(), key=lambda s: sorted(s))]


def consensus(views, groups=None) -> list:
    """**每一个观点群里都至少有一个视图含有它**的单元。

    `groups=None`（默认）时每个视图自成一群 —— 那就**退化成合取**
    （出现在全部视图里），与加入本参数之前**逐位相同**。

    ⚠️ 这条**不看任何一边有多少视图**：一个群里的十个视图和一个视图权重一样。
    所以它在结构上不可能违反 `§C9 #5`（Popularity = Evidence）。
    """
    from core import view as V
    V.check_distinct(views)
    if groups is None:
        groups = groups_singleton(views)
    verify_groups(views, groups)
    uid = {v["id"]: v for v in views}
    units = {v["id"]: units_of(v) for v in views}

    out = []
    for u in sorted(universe(views), key=lambda x: (x[0], str(x[1]))):
        # 每个群各报「群里哪些视图含它」—— 全群非空才算共识
        covering = [sorted(gid for gid in g if u in units[gid])
                    for g in groups]
        if any(not c for c in covering):
            continue
        n, total = support(views, u)
        kind, key = u
        out.append({
            "type": "consensus",
            "unit": {"kind": kind, "key": key},
            "support": (n, total),          # 描述性事实，仍然只是元组
            "n_groups": len(groups),
            "covering": covering,           # 逐群的可追溯覆盖
            "sources": sources_for(views, u),
        })
    return out


def consensus_curve(views) -> dict:
    """几种群划分下的共识数量 —— **让「群怎么分」这件事可见**。

    返回 `{rule: {n_consensus, n_units, groups, degenerate, note}}`。
    """
    from core import view as V
    V.check_distinct(views)
    uni = universe(views)
    rows = {}
    for name, groups in (("singleton", groups_singleton(views)),
                         ("refinement", groups_from_refinement(views))):
        if groups is None:
            rows[name] = {"skipped": "视图之间没有精炼关系，这一条无从谈起"}
            continue
        n = len(consensus(views, groups))
        one_group = len(groups) == 1
        rows[name] = {
            "n_consensus": n,
            "n_units": len(uni),
            "n_groups": len(groups),
            "groups": [sorted(g) for g in groups],
            # 一个群 ⟹ 共识 ≡「出现在至少一个视图里」⟹ 全体单元都是共识 —— 没有信息
            "degenerate": one_group,
            "note": ("**退化**：群只有一个，于是共识 ≡「至少一个视图含它」，"
                     "全体单元都成了共识 —— 这句话没有信息"
                     if one_group else
                     f"{len(groups)} 个群"),
        }
    return rows

