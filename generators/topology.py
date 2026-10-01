"""骨架形状 —— 语料库长什么样，而不是有多少条。

---
为什么单独一个模块
----------------

上一轮的语料库只会造**一种长相**：连通的随机图。量出来两件事：

    焦点机制全程空转：1416 条分歧记录塌成 **1 个焦点**
    （焦点用「共享节点」并查集，那是**传递闭包**；连通图上它恒等于 1）

    形状覆盖近乎为零：空视图 0%、只有节点没有边的视图 0%、
    节点集完全不相交 2%、视图完全相等 0%、含孤立节点 0%

所以「语料库不够」不是条目少，是**它表达不了要测的形状**。这个模块负责前半句。

⚠️ 加这个模块会让 `checks/scope.py` 的目录检查报出「generators 多出 topology」——
**那条检查的作用正是逼我为多出来的东西解释一句**，所以本模块的存在就是那句解释：
语料库的形状参数与视图构造是两件事，混在一个 700 行的文件里，
以后没人分得清「改了形状」和「改了构造」。

---
四种骨架，对应四种真实结构的简化
------------------------------

    random   连通随机图 —— **上一轮唯一有的那种**，作为对照保留
    forest   k 个互不相连的树 —— Scaffold 的 Topic→Position→Claim→Evidence
    chain    链 —— arena 的论证推理链
    star     星 —— 一个议题下的多方立场（hub = Topic）

⚠️ `forest` 不是装饰。**它是唯一能让 §十一 的焦点机制产生 >1 个焦点的形状**：
焦点靠共享节点并簇，所以只有在「结构上互相不连通的区域各自发生分歧」时，
才会形成多个焦点。连通图上无论多少条分歧都只会并成一个。
"""

from __future__ import annotations

VOCAB = ("alpha", "beta", "gamma", "delta", "epsilon",
         "zeta", "eta", "theta", "iota", "kappa")

# ⚠️ 合成语料只用 arena **产品代码真的会创建**的关系种类。
# 上一版是 `("supports", "refines", "related_to")` —— 三条边里两条用的种类
# 在上游产品路径里**从不产生**（见 `core/edge.py` 的 `SPEC_ONLY_KINDS`）。
# 那等于在一个真实数据里不存在的形态上验证 DCE。
#
# 这里取的是产品种类里**结构上够中性**的一批：`contains` 是 Scaffold 的
# 层级关系，`supports` / `qualifies` / `explains` / `assumes` 是 §C4 那张表里的，
# 和 `contradicts` 有声明过的互斥关系 —— 于是「种矛盾」有足够多的落脚点。
KINDS = ("contains", "supports", "qualifies", "explains", "assumes", "challenged_by")


def _xs(state: int) -> int:
    """自写 xorshift。**不用 `random`** —— 语料必须逐字节可复现。"""
    x = state & 0xFFFFFFFFFFFFFFFF
    x ^= (x << 13) & 0xFFFFFFFFFFFFFFFF
    x ^= x >> 7
    x ^= (x << 17) & 0xFFFFFFFFFFFFFFFF
    return x & 0xFFFFFFFFFFFFFFFF


def node_id(i: int) -> str:
    """Scaffold 形状的节点 id（`^[a-z]{2,6}-\\d{4}$`），这样 strict 校验能用。"""
    prefix = ("con", "judge", "arg", "stance", "cond")[i % 5]
    return f"{prefix}-{(i // 5) + 1:04d}"


def _pick(st: int, n: int) -> tuple:
    st = _xs(st)
    return st, st % n


def _edge(a: str, b: str, k: int) -> tuple:
    if a == b:
        raise ValueError("自环")
    if a > b:
        a, b = b, a
    return (a, b, KINDS[k % len(KINDS)])


def random_graph(nodes: list, n_edges: int, st: int) -> tuple:
    """连通随机图（上一层唯一的那种）。**保留作对照。**"""
    n = len(nodes)
    seen, edges = set(), []
    guard = 0
    while len(edges) < n_edges and guard < 10000:
        guard += 1
        st, i = _pick(st, n)
        st, j = _pick(st, n)
        if i == j:
            continue
        e = _edge(nodes[i], nodes[j], len(edges))
        if (e[0], e[1]) in seen:
            continue
        seen.add((e[0], e[1]))
        edges.append(e)
    return edges, st


def forest(nodes: list, n_edges: int, n_components: int, st: int) -> tuple:
    """k 个互不相连的树。**唯一能让焦点 >1 的形状。**

    先把节点均分成 k 组，每组内建一棵随机生成树（保证连通），
    再把剩下的边**只在组内**加 —— 组间绝不连边，否则又不连通了。
    """
    n = len(nodes)
    k = max(1, min(n_components, n))
    groups = [nodes[i::k] for i in range(k)]
    groups = [g for g in groups if g]
    seen, edges = set(), []

    # 每组一棵生成树
    for g in groups:
        for i in range(1, len(g)):
            st, j = _pick(st, i)
            e = _edge(g[i], g[j], len(edges))
            if (e[0], e[1]) in seen:
                continue
            seen.add((e[0], e[1]))
            edges.append(e)

    # 组内补边
    guard = 0
    while len(edges) < n_edges and guard < 20000:
        guard += 1
        st, gi = _pick(st, len(groups))
        g = groups[gi]
        if len(g) < 2:
            continue
        st, i = _pick(st, len(g))
        st, j = _pick(st, len(g))
        if i == j:
            continue
        e = _edge(g[i], g[j], len(edges))
        if (e[0], e[1]) in seen:
            continue
        seen.add((e[0], e[1]))
        edges.append(e)
    return edges, st


def chain(nodes: list, n_edges: int, n_components: int, st: int) -> tuple:
    """链（或若干条链）—— arena 的论证推理链。"""
    n = len(nodes)
    k = max(1, min(n_components, max(1, n // 2)))
    groups = [nodes[i::k] for i in range(k)]
    groups = [g for g in groups if len(g) >= 2]
    seen, edges = set(), []
    for g in groups:
        for i in range(len(g) - 1):
            e = _edge(g[i], g[i + 1], len(edges))
            seen.add((e[0], e[1]))
            edges.append(e)
    # 链上补弦（仍在同一条链内）
    guard = 0
    while len(edges) < n_edges and guard < 20000:
        guard += 1
        st, gi = _pick(st, len(groups))
        g = groups[gi]
        st, i = _pick(st, len(g))
        st, j = _pick(st, len(g))
        if i == j:
            continue
        e = _edge(g[i], g[j], len(edges))
        if (e[0], e[1]) in seen:
            continue
        seen.add((e[0], e[1]))
        edges.append(e)
    return edges, st


def star(nodes: list, n_edges: int, n_components: int, st: int) -> tuple:
    """星 —— 一个议题（hub）下的多方立场。

    ⚠️ 补弦必须**只在同一个 hub 的叶子之间**加。
    第一版从全部叶子里随机挑两个，于是把不同 hub 的叶子连起来了 ——
    k=3 的 `star` 量出来只有 1 个连通分量，**它声称的形状是假的**。
    """
    n = len(nodes)
    k = max(1, min(n_components, n))
    hubs = nodes[:k]
    leaves = nodes[k:]
    by_hub: dict[str, list] = {h: [] for h in hubs}
    seen, edges = set(), []
    for i, leaf in enumerate(leaves):
        hub = hubs[i % k]
        by_hub[hub].append(leaf)
        e = _edge(hub, leaf, len(edges))
        seen.add((e[0], e[1]))
        edges.append(e)
    # 补弦：只在同一 hub 的叶子之间
    guard = 0
    pools = [v for v in by_hub.values() if len(v) >= 2]
    while len(edges) < n_edges and guard < 20000 and pools:
        guard += 1
        st, gi = _pick(st, len(pools))
        g = pools[gi]
        st, li = _pick(st, len(g))
        st, lj = _pick(st, len(g))
        if li == lj:
            continue
        e = _edge(g[li], g[lj], len(edges))
        if (e[0], e[1]) in seen:
            continue
        seen.add((e[0], e[1]))
        edges.append(e)
    return edges, st


TOPOLOGIES = {
    "random": random_graph,
    "forest": forest,
    "chain": chain,
    "star": star,
}


def labels_for(nodes: list, components: dict | None = None,
               region: int = 3) -> dict:
    """给每个节点一个短标签串。

    ⚠️ 为什么需要标签：§十六 的基线 A/B 是「Embedding 相似度」与「相似度 + 聚类」。
    若节点只有 id（`con-0001`），**它们没有任何内容可比** —— 那两个基线会退化成常数，
    比较就变成了打稻草人。

    标签**按结构区域**造：同区域共享词根，于是相似度与结构正相关。
    这是刻意让基线 A/B 处在**有利**位置 —— 若连这样都测不出东西，
    结论就不是「基线实现得差」，而是「相似度这件事答不了这个问题」。

    `components` 给定时按**连通分量**分区域（比按下标分更贴近结构）。
    """
    out = {}
    for i, n in enumerate(nodes):
        r = components[n] if components else i // max(1, region)
        out[n] = (f"{VOCAB[r % len(VOCAB)]} {VOCAB[(r + 1) % len(VOCAB)]} "
                  f"{VOCAB[(r + 2) % len(VOCAB)]} tok{i}")
    return out


def components_of(nodes: list, edges: list) -> dict:
    """连通分量编号。给标签分区与「焦点应有多少个」的上界用。"""
    parent = {n: n for n in nodes}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for e in edges:
        a, b = find(e[0]), find(e[1])
        if a != b:
            parent[b] = a
    roots = {}
    out = {}
    for n in nodes:
        r = find(n)
        if r not in roots:
            roots[r] = len(roots)
        out[n] = roots[r]
    return out


def make_skeleton(n_nodes: int = 12, n_edges: int = 14, seed: int = 20261001,
                  topology: str = "random", n_components: int = 1) -> dict:
    """造骨架。返回 `{nodes, edges, labels, components, topology}`。"""
    if topology not in TOPOLOGIES:
        raise ValueError(f"未知骨架形状 {topology!r}，只认 {sorted(TOPOLOGIES)}")
    nodes = [node_id(i) for i in range(n_nodes)]
    fn = TOPOLOGIES[topology]
    if topology == "random":
        edges, _st = fn(nodes, n_edges, seed)
    else:
        edges, _st = fn(nodes, n_edges, n_components, seed)
    edges = sorted(set(edges))
    comp = components_of(nodes, edges)
    return {
        "nodes": nodes,
        "edges": edges,
        "labels": labels_for(nodes, {n: comp[n] for n in nodes}),
        "components": comp,
        "n_components_actual": len(set(comp.values())),
        "topology": topology,
    }
