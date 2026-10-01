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


# ── 自然近邻 + kNN 分量：**换一种合并规则，而不是换一个尺度** ──────────
#
# ⚠️ 这一节的存在理由，是一条推导出来的结论：
#
#     并查集是**传递闭包**。在连通的共享节点空间上，**任何半径**（含 0）
#     都会把所有分歧并成一团。所以「半径该取多大」这个问题
#     **在连通图上没有正确答案** —— 毛病不在尺度，在**合并规则**。
#
# 而 `knn_zones`（scanstatistics）给的是另一半：**kNN 图是稀疏的**
# （每个点只连最近的 k 个），所以它的**连通分量不会塌成一团**。
# 两者合起来才是完整方案：
#
#     距离            用结构图上的跳数（共享节点空间，§七 的前提）
#     候选邻域        每条记录只连最近的 k 条
#     分组            取 kNN 图的**弱连通分量**（不是全可达）
#     k 取多少        **自然近邻**准则（不选 k，取饱和点）
#
# 自然近邻（natural nearest neighbor，改自 Zhu/Feng/Huang 2016, PRL 80:30-36；
# 出处是 CRAN `FuzzySpec` 参考手册）：让 k 从 1 递增，统计 kNN 图里
# **入度为 0**（没有任何人是它的近邻）的点的个数，**该数不再下降时停**。
# 原文称这是 `parameter-free way to adaptively set the neighbourhood size`。


def _dist_between(adj, sa: set, sb: set, cap: int):
    """两个锚点集之间在结构图上的最短跳数。超过 `cap` 返回 `None`（不硬凑）。"""
    if sa & sb:
        return 0
    seen = set(sa)
    frontier = set(sa)
    d = 0
    while frontier and d < cap:
        d += 1
        nxt = set()
        for u in frontier:
            for x in adj.get(u, ()):
                if x in sb:
                    return d
                if x not in seen:
                    seen.add(x)
                    nxt.add(x)
        frontier = nxt
    return None


def record_distances(records, adj, cap: int = 8) -> list:
    """分歧记录两两之间的距离。返回上三角距离表 `{(i,j): dist or None}`。

    距离 = **两个锚点集在结构图上的最短跳数**。用共享节点空间来量是有理由的：
    `§七` 的前提就是视图已经映射到那个空间。
    """
    an = [anchors(r) for r in records]
    out = {}
    for i in range(len(records)):
        for j in range(i + 1, len(records)):
            out[(i, j)] = _dist_between(adj, an[i], an[j], cap)
    return out


def _nearest(dists, n, i, k):
    """第 i 条记录的 k 个最近邻（距离为 `None` 的不算）。平局按键序，保证确定性。"""
    cand = []
    for j in range(n):
        if j == i:
            continue
        d = dists.get((i, j), dists.get((j, i)))
        if d is None:
            continue
        cand.append((d, j))
    cand.sort()
    return [j for _d, j in cand[:k]]


def natural_k(records, adj, kmax: int = 10, cap: int = 8) -> dict:
    """**自然近邻**：k 递增到「入度为 0 的记录数」不再下降为止。

    ⚠️ 计数的是**入度为 0**（没有任何记录把谁当作最近邻），不是「没有邻居」——
    后者在 k=1 时就恒为 0，准则会立刻失效。这一点容易写错，所以单列出来。
    """
    n = len(records)
    dists = record_distances(records, adj, cap=cap)
    trace, prev = [], None
    for k in range(1, kmax + 1):
        indeg = [0] * n
        for i in range(n):
            for j in _nearest(dists, n, i, k):
                indeg[j] += 1
        zeros = sum(1 for x in indeg if x == 0)
        trace.append((k, zeros))
        if prev is not None and zeros >= prev:
            return {"k": k - 1 if k > 1 else 1, "trace": trace,
                    "reason": f"k={k} 时入度为 0 的记录数不再下降（{prev}→{zeros}）"}
        prev = zeros
    return {"k": kmax, "trace": trace,
            "reason": f"到 kmax={kmax} 仍在下降，取 kmax"}


def knn_foci(divergence: dict, views, k: int | None = None,
             cap: int = 8) -> dict:
    """用 **kNN 图的弱连通分量**分焦点 —— 换合并规则，不是换尺度。

    `k=None` 时用自然近邻准则定 k（**不选 k**）。返回
    `{foci, k, natural, n_isolated}`。

    ⚠️ 与 `foci()` 的区别是**合并规则**，不是参数：
    `foci()` 用「距离 ≤ r 就并」（传递闭包，连通图上必塌成一团）；
    本函数只连最近的 k 条，再取**弱连通分量** —— 图是稀疏的，所以不会塌。
    """
    records = []
    for t in ("refinement", "contradiction", "alternative", "omission"):
        records.extend(divergence.get(t, []))
    n = len(records)
    if n == 0:
        return {"foci": [], "k": 0, "natural": None, "n_isolated": 0}

    adj = structure_graph(views)
    nat = natural_k(records, adj, cap=cap)
    kk = nat["k"] if k is None else k
    dists = record_distances(records, adj, cap=cap)

    uf = _UF(n)
    indeg = [0] * n
    for i in range(n):
        for j in _nearest(dists, n, i, kk):
            uf.union(i, j)
            indeg[j] += 1
    groups = [sorted(v) for v in _groups(uf, n).values()]
    groups.sort(key=lambda idxs: min(_unit_key_of(records[i]) for i in idxs))
    return {"foci": _materialize(groups, records), "k": kk, "natural": nat,
            "n_isolated": sum(1 for x in indeg if x == 0),
            "n_records": n}


def _materialize(clusters, records) -> list:
    """把簇下标列表变成焦点记录（与 `foci()` 同一个形状）。"""
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
                for _vid, targets in r["views"].items():
                    for x in targets:
                        units.append(("edge", (r["source"], x, r["relation"])))
        out.append({
            "focus": f"F{n}",
            "size": len(recs),
            "types": {k: types[k] for k in sorted(types)},
            "units": sorted(set(units), key=lambda x: (x[0], str(x[1]))),
            "anchors": sorted(set().union(*[anchors(r) for r in recs])),
            "sources": prov.merge(*[r["sources"] for r in recs]),
        })
    return out


# ══════════════════════════════════════════════════════════════════════
# 按**主语**分组 —— 换的是依据，不是参数
# ══════════════════════════════════════════════════════════════════════
#
# ⚠️ 换掉「按结构邻近性分组」的理由是一条**量出来的**结论：
#
#     立场材料上，距离≤r 的并查集（r=0..5）**恒为 1 个焦点**；
#     kNN 图弱连通分量（k=1,2,3,5,8）**也恒为 1 个**。
#     `find.radius`（自然近邻）选出的 k **恰好是全都并上的那个**。
#
# 所以毛病既不在尺度、也不在合并规则，而在**依据**：
# 「结构邻近性」在**共享节点空间**上必然把所有分歧连成一团 ——
# 而那正是「多个立场就同一个议题争执」的定义。**越是对同一件事有分歧，越会并成一团。**
#
# 换的依据是记录的**主语**：这条分歧**是关于什么的**。而主语是记录自带的字段，
# 不依赖任何图结构。四种记录各有天然的主语（字段名都来自 `divergence` 的输出）：
#
#     omission       (`missing_in`)              「哪个视图缺了东西」
#     refinement     (`coarse`, `fine`)          「谁的粒度比谁粗」
#     contradiction  (`from`, `to`)              「哪个结构位置被争」
#     alternative    (`source`, `relation`)      「哪个位置上出现竞争解释」
#
# ---
# 划分**不是**要求，所以这里不保证划分
# ------------------------------------
#
# 焦点是一条记录能挂上的**主语**。一条记录可以同时触及几个主语，
# 于是**它可以出现在多个焦点里** —— 这正是「划分只是实现选择」的意思。
# 为此本模块给**两族**焦点，两族的种类不同、天然不冲突：
#
#     结构族  主语 = 被争的那个结构位置     （上面四种）
#     视图族  主语 = 记录牵涉到的每一个视图  （谁卷在里面）
#
# 一条记录必然同时落在「≥1 个结构焦点」与「≥1 个视图焦点」里，
# 而两族不会互相吞并 —— 它们不是同一种东西。`focus_overlap()` 把那张
# 关联表算出来（形状上就是双聚类里的 **checkerboard**）。


def subject_of(record) -> tuple:
    """一条分歧记录的**主语** —— 它「是关于什么的」。

    主语取自记录自带的字段，**不依赖任何图结构**。这是与按邻近性分组的分界。
    """
    t = record["type"]
    if t == "omission":
        return ("缺了", record["missing_in"])
    if t == "refinement":
        return ("粒度", record["coarse"], record["fine"])
    if t == "contradiction":
        return ("被争", record["from"], record["to"])
    if t == "alternative":
        return ("竞争", record["source"], record["relation"])
    raise ValueError(f"未知的记录类型 {t!r}")


def views_of(record) -> set:
    """一条记录**牵涉到哪几个视图**（视图族的主语）。

    与 `subject_of` 分开，因为这两族的主语种类不同：一个是结构位置，一个是视图。
    两族并列存在，就是允许「一条记录属于多个焦点」的具体形式。
    """
    t = record["type"]
    if t == "omission":
        # 缺的那个人 + 所有还留着的人，都卷在里面
        return {record["missing_in"]} | set(prov.views_of(record["sources"]))
    if t == "refinement":
        return {record["coarse"], record["fine"]}
    if t == "contradiction":
        return set(record["relations"][k][0] for k in record["relations"]) | \
               set(prov.views_of(record["sources"]))
    if t == "alternative":
        return set(record["views"])
    raise ValueError(f"未知的记录类型 {t!r}")


def _all_records(divergence: dict) -> list:
    return [r for t in ("refinement", "contradiction", "alternative", "omission")
            for r in divergence.get(t, [])]


LABELS = {"缺了": "哪个视图缺了东西", "粒度": "谁的粒度比谁粗",
          "被争": "哪个结构位置被争", "竞争": "哪个位置上出现竞争解释"}


def subject_foci(divergence: dict, family: str = "structure") -> list:
    """按**主语**分组。`family ∈ {"structure", "view"}`。

    返回的每一项是一个焦点：一个主语 + 挂上它的全部记录。**不是划分** ——
    同一条记录可以出现在多个焦点里（`family="view"` 时尤其明显）。
    """
    records = _all_records(divergence)
    if family not in ("structure", "view"):
        raise ValueError("family 只支持 structure / view")

    groups: dict[tuple, list] = {}
    for r in records:
        keys = ([subject_of(r)] if family == "structure"
                else [("视图", v) for v in sorted(views_of(r))])
        for k in keys:
            groups.setdefault(k, []).append(r)

    # 编号确定：按主语键排序（不按大小、不按任何权重）
    out = []
    for n, key in enumerate(sorted(groups, key=lambda k: tuple(map(str, k))), start=1):
        recs = groups[key]
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
                for _vid, targets in r["views"].items():
                    for x in targets:
                        units.append(("edge", (r["source"], x, r["relation"])))
        out.append({
            "focus": f"{'S' if family == 'structure' else 'V'}{n}",
            "family": family,
            "subject": key,
            "label": (LABELS.get(key[0], "") if family == "structure"
                      else f"视图 {key[1]} 卷入的分歧"),
            "size": len(recs),
            "types": {k: types[k] for k in sorted(types)},
            "units": sorted(set(units), key=lambda x: (x[0], str(x[1]))),
            "anchors": sorted(set().union(*[anchors(r) for r in recs])),
            "sources": prov.merge(*[r["sources"] for r in recs]),
        })
    return out


def focus_overlap(divergence: dict) -> dict:
    """两族焦点之间的关联表 —— 形状上就是双聚类的 **checkerboard**。

    ⚠️ 它存在的意义是回答「划分够不够用」。若一条记录只属于一个结构焦点、
    一个视图焦点，那张表就是分块对角的；若它同时属于几个，就是棋盘状的。
    **本函数只报事实，不判断哪种更好。**
    """
    recs = _all_records(divergence)
    s = subject_foci(divergence, "structure")
    v = subject_foci(divergence, "view")
    # 直接按主语重算，不依赖对象身份
    smap, vmap = {}, {}
    for i, r in enumerate(recs):
        smap[i] = subject_of(r)
        vmap[i] = sorted(views_of(r))
    s_index = {f["subject"]: f["focus"] for f in s}
    v_index = {f["subject"]: f["focus"] for f in v}
    pairs = {}
    for i, r in enumerate(recs):
        for vid in vmap[i]:
            key = (s_index[smap[i]], v_index[("视图", vid)])
            pairs[key] = pairs.get(key, 0) + 1
    multi_s = sum(1 for i in range(len(recs))
                  if vmap[i] and len(vmap[i]) > 1)
    return {"structure_foci": len(s), "view_foci": len(v),
            "incidence": pairs,
            "records_in_multiple_view_foci": multi_s,
            "n_records": len(recs)}



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
    # ⚠️ 物化只有**一处实现**（`_materialize`）。原先这里另写了一遍，
    # 而 `knn_foci` 又需要同一段逻辑 —— 判据写两遍就一定会漂，
    # 本仓库在 `refinement` 上已经吃过一次这个亏。
    return _materialize(clusters, records)


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
