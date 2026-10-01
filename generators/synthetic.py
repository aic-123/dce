"""合成语料生成器（§十四）—— **带 ground truth**。

§十四 的要求：

    不要一开始接真实 LLM。先做 synthetic ground truth。
    生成 Base Graph，然后人为生成 View A / B / C，控制变量：
    shared nodes / shared edges / contradictions / omissions / refinements / alternatives
    然后检查 DCE 能不能恢复预先植入的结构。

所以本模块的核心产出不是视图，是 **`(views, truth)` 一对**。
truth 是「我埋了什么」，没有它就没法测恢复。

---
一个测量设计上的坑（不处理的话 precision 会因为定义问题而不是错误变差）
--------------------------------------------------------------------

若 B 精炼了 A，则 B 多出来的那些单元，**相对视图 C 而言是真的 omission**
（C 确实没有它们）。那不是算法错，是「两个不同的主语」：

    同一个单元，相对 A 是 refinement，相对 C 是 omission

所以 truth 里必须同时记下**主语**，恢复率按主语算：

    hit          预埋的 (主语, 类型) 被报出来了
    type_confuse 主语对，但报成了别的类型      ← 真错误
    spurious     主语根本没预埋                ← 需要人工看，可能是定义使然

`recovery()` 把三者分开报，不合成一个数。把 type_confuse 混进 spurious 里，
或者拿一个 F1 把两者抹平，都会让「算法错了」和「定义如此」看起来一样。

---
构造保证「预埋的结构是正确分类」
------------------------------

每个视图都**至少有一条自己的私有边**，所以任何两个视图的单元集**互不包含**
（除非我显式造 refinement）。这条不变量很重要：少了它，丢一条边就可能让某个视图
变成另一个的子集，于是预埋的 omission 会被 refinement 正当地吞掉 ——
测试会红，但红得没有意义。
"""

from __future__ import annotations

from core import view as V

KINDS = ("supports", "refines", "related_to")
EXCLUSIVE = ("contradicts", "supports")

# 造标签用的词根。只为让相似度基线有东西可比（见 `_labels`）。
VOCAB = ("alpha", "beta", "gamma", "delta", "epsilon",
         "zeta", "eta", "theta", "iota", "kappa")

# 能种矛盾的关系种类：**必须在声明的互斥集里有对应**（见 core/edge.py 的 EXCLUSIVE_PAIRS）。
# 从 edge 模块推出来，不手写 —— 手写就会与声明漂开，而漂开的表现是「DCE 漏报」，
# 看起来像算法错，其实是生成器种错了地方。
from core.edge import EXCLUSIVE_PAIRS  # noqa: E402

_CONTRADICTABLE = frozenset(
    k for pair in EXCLUSIVE_PAIRS for k in pair
)


def _xs(state: int) -> int:
    x = state & 0xFFFFFFFFFFFFFFFF
    x ^= (x << 13) & 0xFFFFFFFFFFFFFFFF
    x ^= x >> 7
    x ^= (x << 17) & 0xFFFFFFFFFFFFFFFF
    return x & 0xFFFFFFFFFFFFFFFF


def _nid(i: int) -> str:
    """Scaffold 形状的节点 id（`^[a-z]{2,6}-\\d{4}$`），这样 strict 校验能用。"""
    prefix = ("con", "judge", "arg", "stance", "cond")[i % 5]
    return f"{prefix}-{(i // 5) + 1:04d}"


def _labels(nodes: list, region: int = 3) -> dict:
    """给每个节点一个短标签串。

    ⚠️ 为什么合成语料需要标签：§十六 的基线 A/B 是「Embedding 相似度」与
    「相似度 + 聚类」。若节点只有 id（`con-0001`），**它们没有任何内容可比** ——
    那两个基线在合成 ground truth 上会退化成常数，比较就变成了打稻草人。
    加上标签，比较才有意义。

    标签**按区域**造：相邻区域的节点共享词根，于是相似度与结构正相关。
    这是刻意让基线 A/B 处在**有利**位置 —— 若连这样都测不出东西，
    结论就不是「基线实现得差」，而是「相似度这件事答不了这个问题」。
    """
    out = {}
    for i, n in enumerate(nodes):
        r = i // max(1, region)
        out[n] = (f"{VOCAB[r % len(VOCAB)]} {VOCAB[(r + 1) % len(VOCAB)]} "
                  f"{VOCAB[(r + 2) % len(VOCAB)]} tok{i}")
    return out


def base_graph(n_nodes: int = 12, n_edges: int = 14, seed: int = 20261001) -> dict:
    """无向骨架 + 有向类型的边。确定性。"""
    nodes = [_nid(i) for i in range(n_nodes)]
    st = seed
    seen = set()
    edges = []
    guard = 0
    while len(edges) < n_edges and guard < 10000:
        guard += 1
        st = _xs(st)
        i = st % n_nodes
        st = _xs(st)
        j = st % n_nodes
        if i == j:
            continue
        a, b = nodes[i], nodes[j]
        if a > b:
            a, b = b, a
        if (a, b) in seen:
            continue
        seen.add((a, b))
        # ⚠️ 种类**确定性轮转**，不是随机取。
        # 随机取会造出一个「小 core 里一条 supports 都没有」的图，于是
        # 「种 2 条矛盾」这个要求在图上根本无法满足 —— 而那会被误读成 DCE 漏报。
        # 轮转保证种类均匀，去掉这一整类不稳定。
        edges.append((a, b, KINDS[len(edges) % len(KINDS)]))
    edges.sort()
    return {"nodes": nodes, "edges": edges, "labels": _labels(nodes)}


def make(base: dict, spec: dict, seed: int = 20261002) -> tuple:
    """造视图并返回 `(views, truth)`。

    spec 的旋钮（都可省，省即 0）：

        n_views        视图数（≥2，默认 3）
        n_core         全网共享的边数（→ 共识）
        contradictions 植入的矛盾数
        omissions      植入的缺失数
        refinements    植入的精炼对数
        alternatives   植入的竞争解释数
        private        每个视图的私有边数（默认 1，见模块 docstring）
    """
    n_views = int(spec.get("n_views", 3))
    if n_views < 2:
        raise ValueError("至少 2 个视图")
    n_core = int(spec.get("n_core", 6))
    n_private = int(spec.get("private", 1))
    n_contra = int(spec.get("contradictions", 0))
    n_omit = int(spec.get("omissions", 0))
    n_refine = int(spec.get("refinements", 0))
    n_alt = int(spec.get("alternatives", 0))

    nodes, edges = base["nodes"], list(base["edges"])
    if n_core > len(edges):
        raise ValueError(f"n_core={n_core} 超过边数 {len(edges)}")

    core = edges[:n_core]
    rest = edges[n_core:]
    vids = [f"V{i + 1}" for i in range(n_views)]

    # 每个视图 = core + 自己的私有边（私有边优先从 rest 取，不够就现场造）
    st = seed
    priv = {}
    pool = list(rest)
    for vi in vids:
        mine = []
        for _ in range(n_private):
            if pool:
                mine.append(pool.pop(0))
            else:
                st = _xs(st)
                a = nodes[st % len(nodes)]
                st = _xs(st)
                b = nodes[st % len(nodes)]
                if a == b:
                    b = nodes[(nodes.index(a) + 1) % len(nodes)]
                mine.append((a, b, "related_to"))
        priv[vi] = mine

    raw = {vi: (list(core) + list(priv[vi])) for vi in vids}
    truth = {"contradiction": set(), "omission": set(),
             "refinement": set(), "alternative": set()}

    # ── 植入：四类用**互不重叠的 core 切片** ─────────────────────────────
    #
    # ⚠️ 这条是刻意加的，不是随手。第一版四类共用 core[0..k]，于是同一条边
    # 可能既被某个视图翻转、又被另一个视图丢掉 —— 那会造出**分类本来就该是别的类型**
    # 的样本，而 §十五 Test 3 要的是「**分别**恢复它们」。
    # 预埋的结构必须落在正确的类型上，否则测的是我的生成器，不是 DCE。
    #
    # ⚠️ 第二条同样重要：**矛盾只能种在「有互斥对应」的关系种类上。**
    # 本仓库声明的互斥集是 arena §C4 那个单元格 {supports, contradicts, qualifies}
    # （见 core/edge.py）。core 上的边种类是 supports / refines / related_to，
    # 所以只有 `supports` 那一部分能种矛盾 —— 把 contradicts 种在 `refines` 上，
    # **按我自己声明的词表它就不是矛盾**，DCE 不报是对的。
    # 第一版没管这条，于是一百条里只有约三分之一能中，recall 0.2 全是这个来的。
    eligible = [e for e in core if e[2] in _CONTRADICTABLE]
    if n_contra > len(eligible):
        raise ValueError(
            f"要种 {n_contra} 条矛盾，但 core 里只有 {len(eligible)} 条边的种类"
            f"有互斥对应（{sorted(_CONTRADICTABLE)}）。"
            "矛盾种在没有互斥对应的种类上，按声明它就不是矛盾 —— 那不是 DCE 漏报。"
        )
    if n_contra + n_omit > len(core):
        raise ValueError(
            f"植入量超过 core：contradictions({n_contra}) + omissions({n_omit}) "
            f"> n_core({len(core)})。四类用互不重叠的切片，所以必须留得下"
        )
    contra_slice = eligible[:n_contra]
    used = {e for e in contra_slice}
    omit_slice = [e for e in core if e not in used][:n_omit]

    # ── 植入顺序与**视图分工**（都是有依赖的，不能随便排）──────────────
    #
    # ⚠️ 第一版按 矛盾→缺失→精炼→竞争解释 依次植入，结果精炼那一步取并集，
    # 把先前种下的矛盾翻转与缺失又加回去了：truth 里 20 条缺失、10 条矛盾
    # 在视图里一条不剩，召回全是 0。**它看起来像「DCE 完全失效」。**
    #
    # ⚠️ 第二版只重排了顺序，还是不行：从精炼的**细**侧删边同样会破坏 `粗 ⊂ 细`，
    # 而精炼取并集之后两个视图的后继集合会变得可比，竞争解释就没了。
    #
    # 所以结论是一条硬约束：**四类同时植入需要各自专用的视图。**
    # 这不是偷懒 —— 一个视图既参与精炼又被删边，那本来就是在造一个
    # 「分类该算哪一类都对」的样本，而 §十五 Test 3 要的是「**分别**恢复它们」。
    # 视图不够时本函数**直接报错**，不悄悄种出一个不可能通过的测试床。
    ref_plan = []
    used_by_ref = set()
    for k in range(n_refine):
        coarse = vids[k % n_views]
        fine = vids[(k + 1) % n_views]
        # 两个视图都不能已经参与过任何精炼对 —— 否则会造出 V1⊂V2⊂V3 的链，
        # 而链会让「谁是谁的粗侧」不再唯一，恢复率就算不清了。
        if coarse == fine or coarse in used_by_ref or fine in used_by_ref:
            continue
        ref_plan.append((coarse, fine))
        used_by_ref |= {coarse, fine}
    reserved = {v for p in ref_plan for v in p}
    free = [v for v in vids if v not in reserved]
    need = (2 if n_alt else 0) + (1 if n_contra else 0) + (1 if n_omit else 0)
    if len(free) < need:
        raise ValueError(
            f"四类各需专用视图：精炼占用 {len(reserved)} 个，剩下 {len(free)} 个可用，"
            f"但还需要 {need} 个（竞争解释 2、矛盾 1、缺失 1）。"
            f"请把 n_views 提到至少 {len(reserved) + need}，或减少植入量。\n"
            "**这不是实现限制，是测试床的要求**：一个视图既参与精炼又被删边，"
            "就是在造「分类该算哪一类都对」的样本，而 Test 3 要的是分别恢复。"
        )
    cursor = 0

    # ① 竞争解释：专用 2 个视图，后继集合互不包含
    alt_views = free[cursor:cursor + 2] if n_alt else []
    cursor += 2 if n_alt else 0
    for k in range(n_alt):
        src = nodes[(k * 3) % len(nodes)]
        fresh = [n for n in nodes if n != src][k * 2 % max(1, len(nodes) - 1):][:4]
        if len(fresh) < 2:
            continue
        va, vb = alt_views[0], alt_views[1]
        ea = (src, fresh[0], "supports")
        eb = (src, fresh[1], "supports")
        raw[va] = [e for e in raw[va] if not (e[0] == src and e[1] == fresh[1])]
        raw[vb] = [e for e in raw[vb] if not (e[0] == src and e[1] == fresh[0])]
        if ea not in raw[va]:
            raw[va].append(ea)
        if eb not in raw[vb]:
            raw[vb].append(eb)
        truth["alternative"].add((src, "supports", fresh[0], fresh[1], va, vb))

    # ② 精炼：fine = coarse ∪ fine ∪ extras（真超集）。只碰自己那两个视图。
    for (coarse, fine) in ref_plan:
        extra = []
        guard = 0
        while len(extra) < 2 and guard < 500:
            guard += 1
            st = _xs(st)
            a = nodes[st % len(nodes)]
            st = _xs(st)
            b = nodes[st % len(nodes)]
            if a == b:
                continue
            cand = (a, b, "related_to")
            if cand not in raw[fine] and cand not in extra:
                extra.append(cand)
        raw[fine] = sorted(set(list(raw[coarse]) + list(raw[fine]) + extra))
        for e in extra:
            truth["refinement"].add((coarse, fine, "edge", e))

    # ③ 矛盾：专用视图，翻转关系
    if n_contra:
        cview = free[cursor]
        cursor += 1
        for (a, b, r) in contra_slice:
            raw[cview] = [e for e in raw[cview] if not (e[0] == a and e[1] == b)]
            raw[cview].append((a, b, "contradicts"))
            truth["contradiction"].add((a, b, r, "contradicts"))

    # ④ 缺失：专用视图，删边（最后做，删了就不该再有人加回来）
    dropped = []
    if n_omit:
        oview = free[cursor]
        cursor += 1
        for e in omit_slice:
            if e in raw[oview]:
                raw[oview] = [x for x in raw[oview] if x != e]
                dropped.append((oview, e))
                truth["omission"].add((oview, "edge", e))

    views = []
    for vi in vids:
        es = sorted(set(raw[vi]))
        ns = sorted({x for e in es for x in (e[0], e[1])})
        views.append(V.make_view(
            view_id=vi,
            source_ref=f"synthetic://{vi}",
            source_kind="experiment",
            nodes=ns, edges=es,
            # 标签放 metadata —— 视图顶层是白名单，多一个字段会被 verify() 拦掉，
            # 而 metadata 正是白名单里留给这类附加物的位置。
            metadata={"labels": {n: base["labels"][n] for n in ns}},
        ))

    # 共识的 ground truth = **定义**（全部视图的交集），不是「我以为共享的那些」
    from analysis import consensus as C
    truth["consensus"] = set.intersection(*[C.units_of(v) for v in views]) \
        if views else set()
    truth["n_views"] = n_views
    truth["core"] = set(core)
    truth["dropped"] = dropped

    # ── 存活校验：种下去的结构必须活到视图构造结束 ──────────────────────
    #
    # ⚠️ 这条是踩出来的。第一版四类依次植入，而**精炼那一步取的是并集** ——
    # 它把先前种下的矛盾翻转和缺失**又加回去了**。结果是：truth 里有 20 条缺失、
    # 10 条矛盾，而视图里一条都不剩，于是召回全是 0，看起来像 DCE 完全失效，
    # 其实是生成器自己把自己种的东西抹掉了。
    #
    # 所以这里逐条核对，不活下来就当场报错 —— **静默地种失败，
    # 在报告上长得和「算法漏报」一模一样。**
    bad = _survival_problems(views, truth)
    if bad:
        raise ValueError(
            "植入的结构没能活到视图构造结束：\n  - " + "\n  - ".join(bad[:8])
            + f"\n（共 {len(bad)} 条）。这是生成器的问题，不是 DCE 的问题。"
        )
    return views, truth


def _survival_problems(views, truth) -> list:
    """逐条核对预埋结构在最终视图里是否成立。"""
    from analysis import consensus as C
    from analysis import divergence as D
    by_id = {v["id"]: v for v in views}
    unit_of = {v["id"]: C.units_of(v) for v in views}
    ref_covered = {v["id"]: D.refinement_covered(v, views) for v in views}
    problems = []

    for (vi, kind, key) in truth["omission"]:
        if vi not in unit_of:
            problems.append(f"缺失：视图 {vi} 不存在")
            continue
        u = (kind, key)
        if u in unit_of[vi]:
            problems.append(f"缺失：{vi} 仍然有 {key}")
        if u in ref_covered[vi]:
            problems.append(f"缺失：{vi} 缺 {key}，但它被 refinement 解释掉了（会归到另一类）")
        if kind == "edge":
            f, t, r = key
            if D._has_exclusive_counterpart(by_id[vi], f, t, r):
                problems.append(f"缺失：{vi} 在 {f}->{t} 上说了互斥的话（会归到矛盾）")

    for (a, b, r1, r2) in truth["contradiction"]:
        holders = {r: [vid for vid, us in unit_of.items() if ("edge", (a, b, r)) in us]
                   for r in (r1, r2)}
        if not holders[r1] or not holders[r2]:
            problems.append(f"矛盾：{a}->{b} 的 {r1}/{r2} 有一边一个视图都没有")
        elif set(holders[r1]) & set(holders[r2]):
            problems.append(
                f"矛盾：{a}->{b} 的两种关系出现在同一个视图里"
                f"（{sorted(set(holders[r1]) & set(holders[r2]))}）——"
                "同视图内部的不一致不算跨视图分歧"
            )

    for (coarse, fine, kind, key) in truth["refinement"]:
        if coarse not in unit_of or fine not in unit_of:
            problems.append(f"精炼：视图 {coarse}/{fine} 不存在")
            continue
        if not (unit_of[coarse] < unit_of[fine]):
            problems.append(f"精炼：{coarse} ⊂ {fine} 不成立")
        if (kind, key) not in (unit_of[fine] - unit_of[coarse]):
            problems.append(f"精炼：{key} 不在 {fine} 比 {coarse} 多出来的部分里")

    # ⚠️ 只验**预埋的那一对视图**，不验全局。
    # 第一版验的是「所有有后继的视图两两不可比」——那是全局性质，
    # 而 core 里别的视图本来就可能在同一 source 上有后继，
    # 于是 4 条预埋报出 20 条「失败」，全是别的视图对。**校验范围写错，
    # 报出来的数字就与要测的东西无关。**
    for (src, rel, t1, t2, va, vb) in truth["alternative"]:
        def succ(vid):
            return {e["to"] for e in by_id[vid]["edges"]
                    if e["from"] == src and e["relation"] == rel}
        sa, sb = succ(va), succ(vb)
        if not sa or not sb:
            problems.append(f"竞争解释：{src}--{rel} 有一边没有后继（{va}/{vb}）")
        elif sa <= sb or sb <= sa:
            problems.append(
                f"竞争解释：{src}--{rel} 在 {va}/{vb} 上有包含关系"
                f"（{sorted(sa)} vs {sorted(sb)}）")
    return problems


# ── 旋钮网格：给 Coverage × Compression 的「区域」用（§十三）────────────
def grid(n_views=(2, 3, 5), n_core=(3, 6, 9), planted=(0, 4)) -> list:
    """一个确定性的参数网格。每一项是一个可直接喂给 `make()` 的 spec。"""
    out = []
    for nv in n_views:
        for nc in n_core:
            for p in planted:
                out.append({
                    "n_views": nv, "n_core": nc, "private": 1,
                    "contradictions": p, "omissions": p,
                    "refinements": min(p, 1), "alternatives": min(p, 1),
                })
    return out
