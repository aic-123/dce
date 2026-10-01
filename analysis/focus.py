"""分歧焦点 —— **结构聚类，不排序**。

---
§十一 的三条要求与我的取舍
-------------------------

设计稿 §十一 说：

    不能简单地「把所有 divergence 排序」。因为排序很容易变成
    「DCE 替用户决定什么最重要」。

    第一版只做结构聚类。聚类依据：shared nodes / shared edges / local graph distance
    而不是：importance score / truth score / model confidence

前两条**无参数**，本模块直接实现（并查集，共享一个结构端点就并簇）。
第三条 **`local graph distance` 需要一个半径** —— 半径是几？一跳还是两跳？

    §T0.3：「不得为 `§C7.2` 的任何观测点提**具体阈值**……
            没有基线数据的阈值一律是拍脑袋」

所以 MVP **不做距离聚类**，登记为延后。这不是偷懒：距离聚类一旦落地，
「几跳之内算同一个焦点」就会变成 DCE 唯一一个没人能解释的参数，
而它的取值会直接改变焦点个数 —— 那正是 §十一 想避免的那类隐藏决定。

---
焦点编号**不按大小排**
--------------------

簇按**其中最小的单元键**排序，编号 `F1, F2, …`。不按簇大小排。

⚠️ 严格说，按大小排并不违反 #5 —— `§C7.1 ①` 把「某类争议反复出现的次数」
列为**允许**信号（禁止的是投票数 / 热度 / 参与量 / 曝光量）。所以簇大小是个
合法的结构量。这里仍然按键排，是因为「按大小排」和「按重要度排」在输出上
长得一模一样，而读者分不出这是哪一种。**排一次就把排序权交出去了，不值得。**
簇大小照报，作为描述性事实。

由 —— 见下。

---
⚠️ 半径：显式参数，但**它的上界是算出来的，不是拍出来的**
-----------------------------------------------------

§十一 列的第三条聚类依据是 `local graph distance`。上一版**故意没做**，
理由是它需要一个半径，而 `§T0.3` 说「不得为观测点提**具体阈值**……
没有基线数据的阈值一律是拍脑袋」。

那个理由**只对了一半**。`§T0.3` 禁的是**断言一个没有基线数据的具体值**，
不是禁「有一个显式参数」。区别在这里：

    ✗ 拍一个半径，当成正确值用                    → 违规
    ✓ 让半径是个显式参数，把整条曲线报出来，
      并且它的**上界由结构算出来**                → 不违规

        radius = 0   共享节点（传递闭包）
        radius = k   两个分歧的锚点在**结构图**上的距离 ≤ k 就并簇

    上界 `r*` = **焦点塌成 1 的最小半径**。超过它，焦点这个中间层
    不再携带任何信息（只有一簇，等于没聚）。`r*` 是**从图里算出来的**，
    不是选的 —— 数据一多它自动重算，**那就是校准**。

    可用区间 = `[0, r*−1]`；`r* = 0` 意味着**没有可用区间**，
    即这个形状下半径帮不上忙。那不是失败，是结论。

⚠️ 为什么半径只可能让焦点**变少**：半径越大并得越多，所以
`焦点数(k)` 单调不增。这条被钉成断言 —— 它同时是对实现的检查。
"""

from __future__ import annotations

from collections import deque

from core import provenance as prov


def anchors(record) -> set:
    """一条分歧记录**贴着哪些节点**。

    - `omission` / `refinement`：单元的端点（节点单元就是它自己）
    - `contradiction`：`from` / `to`
    - `alternative`：`source` 与各后继
    """
    t = record["type"]
    if t in ("omission", "refinement"):
        kind, key = record["unit"]["kind"], record["unit"]["key"]
        return {key} if kind == "node" else {key[0], key[1]}
    if t == "contradiction":
        return {record["from"], record["to"]}
    if t == "alternative":
        out = {record["source"]}
        for targets in record["views"].values():
            out |= set(targets)
        return out
    raise ValueError(f"未知的记录类型 {t!r}")


def structure_graph(views) -> dict:
    """**共享结构空间**的无向邻接表 —— 由全部视图的边的并集构成。

    ⚠️ 用它当「距离」的底图是有理由的：`§七` 的前提就是视图已经映射到
    一个共享节点空间，所以两点之间的距离应当在**那个共享空间**上量，
    而不是在某个视图自己的子图里量（后者会随视图不同而不同）。
    """
    adj: dict[str, set] = {}
    for v in views:
        for e in v["edges"]:
            adj.setdefault(e["from"], set()).add(e["to"])
            adj.setdefault(e["to"], set()).add(e["from"])
    for n in {n for v in views for n in v["nodes"]}:
        adj.setdefault(n, set())
    return adj


def _within(adj, src: str, radius: int) -> set:
    """从 `src` 出发、结构距离 ≤ `radius` 的节点集合（含自身）。"""
    if radius <= 0:
        return {src}
    seen, q = {src}, deque([(src, 0)])
    while q:
        cur, d = q.popleft()
        if d >= radius:
            continue
        for x in adj.get(cur, ()):  # noqa: E741
            if x not in seen:
                seen.add(x)
                q.append((x, d + 1))
    return seen


class _UF:
    """并查集。路径压缩 + 按秩合并，纯标准库。"""

    def __init__(self, n):
        self.p = list(range(n))
        self.r = [0] * n

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.r[ra] < self.r[rb]:
            ra, rb = rb, ra
        self.p[rb] = ra
        if self.r[ra] == self.r[rb]:
            self.r[ra] += 1


def cluster(records, radius: int = 0, adj=None) -> list:
    """按「结构距离 ≤ radius」把记录并成簇。

    `radius=0` 就是上一版的行为（共享一个节点，即距离 0），
    所以**默认不改变任何既有结果**。
    """
    if radius > 0 and adj is None:
        raise ValueError(
            f"radius={radius} 需要结构图（`adj`）才能算距离。"
            "不传就无从判断两点有多远 —— 而**猜一个距离**正是 §T0.3 要防的。"
        )
    n = len(records)
    uf = _UF(n)
    if radius <= 0:
        owner: dict[str, int] = {}
        for i, r in enumerate(records):
            for a in sorted(anchors(r)):
                if a in owner:
                    uf.union(owner[a], i)
                else:
                    owner[a] = i
        return [sorted(v) for v in _groups(uf, n).values()]

    # radius > 0：判据是 **dist(锚点集A, 锚点集B) ≤ radius**。
    #
    # ⚠️ 第一版算的是「两边的**半径球**相交」，而两个半径 k 的球相交等价于
    # `dist ≤ 2k` —— **实际生效的阈值是半径的两倍**。语义差了一倍，
    # 而它不会报错，只会让曲线在比预期早一半的地方塌下去。
    #
    # 抓出它的是 `checks/radius.py` 的「中间地带」用例：两簇锚点最近距离 5，
    # 曲线却在 radius=3 就并成了 1 个。
    #
    # 精确写法：先建「锚点 → 记录」的索引，然后对每条记录，看**它自己锚点的
    # 半径邻域里有没有别人的锚点**。
    anchor_owner: dict[str, list] = {}
    for i, r in enumerate(records):
        for a in anchors(r):
            anchor_owner.setdefault(a, []).append(i)
    for i, r in enumerate(records):
        ball: set = set()
        for a in anchors(r):
            ball |= _within(adj, a, radius)
        for node in ball:
            for j in anchor_owner.get(node, ()):
                uf.union(i, j)
    return [sorted(v) for v in _groups(uf, n).values()]


def _groups(uf, n) -> dict:
    out: dict[int, list] = {}
    for i in range(n):
        out.setdefault(uf.find(i), []).append(i)
    return out



def _unit_key_of(record):
    """一条记录的「单元键」，用于确定性排序。"""
    t = record["type"]
    if t in ("omission", "refinement"):
        kind, key = record["unit"]["kind"], record["unit"]["key"]
        return (kind, str(key))
    if t == "contradiction":
        return ("edge", f"{record['from']}->{record['to']}")
    return ("alt", f"{record['source']}-{record['relation']}")


def foci(divergence: dict, radius: int = 0, views=None) -> list:
    """把四类分歧聚成焦点。返回 `[{focus, types, units, anchors, sources, size}]`。

    `types` 是各类型在本焦点里的条数 —— **描述性**，不做任何加权。

    `radius=0`（默认）就是「共享节点」那一版的行为，**不改变任何既有结果**。
    `radius>0` 需要 `views`（用来构造共享结构图）；不传就报错，
    因为**猜一个距离**正是 `§T0.3` 要防的。
    """
    records = []
    for t in ("refinement", "contradiction", "alternative", "omission"):
        records.extend(divergence.get(t, []))

    adj = structure_graph(views) if (radius > 0 and views is not None) else None
    clusters = cluster(records, radius=radius, adj=adj)
    # 按簇内最小单元键排序 → 编号确定，不随输入顺序变，也不随大小变
    clusters.sort(key=lambda idxs: min(_unit_key_of(records[i]) for i in idxs))

    out = []
    for n, idxs in enumerate(clusters, start=1):
        recs = [records[i] for i in idxs]
        types: dict[str, int] = {}
        for r in recs:
            types[r["type"]] = types.get(r["type"], 0) + 1
        units = []
        for r in recs:
            if "unit" in r:
                units.append((r["unit"]["kind"], r["unit"]["key"]))
            elif r["type"] == "contradiction":
                for rel in r["relations"]:
                    units.append(("edge", (r["from"], r["to"], rel)))
            else:
                for vid, targets in r["views"].items():
                    for x in targets:
                        units.append(("edge", (r["source"], x, r["relation"])))
        an = sorted(set().union(*[anchors(r) for r in recs])) if recs else []
        out.append({
            "focus": f"F{n}",
            "size": len(recs),
            "types": {k: types[k] for k in sorted(types)},
            "units": sorted(set(units), key=lambda x: (x[0], str(x[1]))),
            "anchors": an,
            "sources": prov.merge(*[r["sources"] for r in recs]) if recs else [],
        })
    return out


# ── 半径的**校准**：上界由结构算出来，不由人选 ──────────────────────

def diameter(adj) -> int:
    """结构图的直径（最长最短路径）。空图或单点图为 0。"""
    if not adj:
        return 0
    best = 0
    for src in adj:
        seen, q = {src}, deque([(src, 0)])
        while q:
            cur, d = q.popleft()
            best = max(best, d)
            for x in adj.get(cur, ()):
                if x not in seen:
                    seen.add(x)
                    q.append((x, d + 1))
    return best


def radius_curve(divergence: dict, views) -> list:
    """`[(radius, 焦点数)]`，从 0 扫到结构图直径。

    这是校准的原料：**曲线本身要报出来，而不是只报一个选定的半径。**
    """
    adj = structure_graph(views)
    d = diameter(adj)
    return [(k, len(foci(divergence, radius=k, views=views)))
            for k in range(0, d + 1)]


def calibrate(divergence: dict, views) -> dict:
    """从曲线里**导出**可用区间与建议半径。**不拍任何值。**

    `r*` = **焦点塌成 1 的最小半径** —— 超过它焦点这个中间层不携带信息。

        可用区间 = [0, r*−1]
        建议半径 = r*−1（最后一个还有信息的值）
        r* = 0  →  **没有可用区间**，即这个形状下半径帮不上忙

    三者都是从图里算出来的。数据一多，`r*` 自动重算 —— **那就是校准**：

        radius 从「有人选的常数」变成「由结构 + 数据算出来的量」。
        `§T0.3` 禁的是前者，不是后者。
    """
    curve = radius_curve(divergence, views)
    r_star = None
    for k, n in curve:
        if n <= 1:
            r_star = k
            break
    usable = list(range(0, r_star)) if r_star is not None else \
        [k for k, _ in curve]
    at_zero = curve[0][1] if curve else 0
    flat = len({n for _k, n in curve}) == 1
    if at_zero <= 1:
        note = ("**没有可用区间**：radius=0 时焦点已经塌成 1，"
                "加大半径只会更糟 —— 这个形状下半径帮不上忙（**并得太早**）")
    elif flat:
        note = ("**没有可用区间**：焦点数不随半径变化 —— "
                "并集图是碎的，半径再大也跨不过分量（**永远并不上**）。"
                "`r*` 不存在，**不是 0**")
    elif r_star is None:
        note = (f"焦点数降到 {curve[-1][1]} 就不再降（直径 "
                f"{curve[-1][0]} 内不塌成 1）—— 可用区间 [0, {max(usable)}]，"
                "但 `r*` 在此直径内不存在")
    else:
        note = (f"可用区间 [0, {max(usable)}]；上界由结构算出（r*={r_star}）")
    return {
        "curve": curve,
        "r_star": r_star,                        # 塌成 1 的最小半径
        "usable_max": (max(usable) if usable else None),
        "suggested": (max(usable) if usable else 0),
        "degenerate_at_zero": at_zero <= 1,
        "flat": flat,
        "note": note,
    }
