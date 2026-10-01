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
"""

from __future__ import annotations

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


def cluster(records) -> list:
    """按「共享节点」把记录并成簇。**无参数。**返回簇列表（每簇是记录下标的列表）。"""
    n = len(records)
    uf = _UF(n)
    owner: dict[str, int] = {}
    for i, r in enumerate(records):
        for a in sorted(anchors(r)):
            if a in owner:
                uf.union(owner[a], i)
            else:
                owner[a] = i
    groups: dict[int, list] = {}
    for i in range(n):
        groups.setdefault(uf.find(i), []).append(i)
    return [sorted(v) for v in groups.values()]


def _unit_key_of(record):
    """一条记录的「单元键」，用于确定性排序。"""
    t = record["type"]
    if t in ("omission", "refinement"):
        kind, key = record["unit"]["kind"], record["unit"]["key"]
        return (kind, str(key))
    if t == "contradiction":
        return ("edge", f"{record['from']}->{record['to']}")
    return ("alt", f"{record['source']}-{record['relation']}")


def foci(divergence: dict) -> list:
    """把四类分歧聚成焦点。返回 `[{focus, types, units, anchors, sources, size}]`。

    `types` 是各类型在本焦点里的条数 —— **描述性**，不做任何加权。
    """
    records = []
    for t in ("refinement", "contradiction", "alternative", "omission"):
        records.extend(divergence.get(t, []))

    clusters = cluster(records)
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
