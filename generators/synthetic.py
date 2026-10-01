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

# ⚠️ 关系种类只用 arena **产品代码真的会创建**的那 10 种里的。
# 本模块原先自己写了一份 `("supports", "refines", "contains")` ——
# 三条里两条是产品从不产生的（`SPEC_ONLY_KINDS`），也就是在验证一个
# 上游不存在的形态。骨架那边的种类清单是同一份，直接用 `topology.KINDS`，
# **不再各写一份**（判据写两遍就一定会漂，这个教训本仓库已经吃过一次）。
from . import topology as _topo  # noqa: E402

KINDS = _topo.KINDS

# 造标签用的词根。只为让相似度基线有东西可比（见 `_labels`）。
VOCAB = _topo.VOCAB

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


def _spread(edges: list, n: int) -> list:
    """从边表里**均匀取样** n 条，而不是取前 n 条。

    ⚠️ 为什么必须这样：边表是排序过的（按 `(from, to)`），所以 `edges[:n]`
    会把语料永久锁在字典序最靠前的一小撮节点上。上一轮量出来的证据：
    40 个节点的骨架、90 条边，`n_core=12` 只用到 14 个节点，
    而同样 12 条边随机取会用到平均 18.5 个 —— **参数放大了，材料没有变。**

    均匀取样是确定性的、无参数的，且把 core 铺到整个 id 空间与所有连通分量上。
    """
    if n <= 0:
        return []
    if n >= len(edges):
        return list(edges)
    step = len(edges) / n
    out, used = [], set()
    for i in range(n):
        idx = int(i * step)
        while idx in used and idx + 1 < len(edges):
            idx += 1
        used.add(idx)
        out.append(edges[idx])
    return out


def base_graph(n_nodes: int = 12, n_edges: int = 14, seed: int = 20261001,
               topology: str = "random", n_components: int = 1) -> dict:
    """骨架。**形状交给 `generators/topology.py`，本函数只是它的门面。**

    ⚠️ 上一轮这里是内联的连通随机图，而那让语料库只会造一种长相 ——
    最直接的后果是 §十一 的焦点机制全程空转（连通图上焦点恒等于 1）。
    形状参数与视图构造是两件事，所以在模块层面分开了。
    """
    from . import topology as T
    return T.make_skeleton(n_nodes=n_nodes, n_edges=n_edges, seed=seed,
                           topology=topology, n_components=n_components)


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

    形状旋钮（上一轮完全没有，见模块 docstring 里的覆盖率数字）：

        empty_views     有几个视图**什么都没有**（单元集 = ∅）
        node_only_views 有几个视图**只有节点、没有边**
        disjoint_views  有几个视图用**与 core 不相交**的另一批节点
        equal_views     强制几个视图**逐字节相同**
        allow_overlap   允许四类共用视图（默认 True）。False 时退回上一轮的
                        「四类各需专用视图」，放不下就报错
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
    n_empty = int(spec.get("empty_views", 0))
    n_nodeonly = int(spec.get("node_only_views", 0))
    n_disjoint = int(spec.get("disjoint_views", 0))
    n_equal = int(spec.get("equal_views", 0))
    allow_overlap = bool(spec.get("allow_overlap", True))

    nodes, edges = base["nodes"], list(base["edges"])
    if n_core > len(edges):
        raise ValueError(f"n_core={n_core} 超过边数 {len(edges)}")

    # ⚠️ core 必须**铺开取**，不能取 `edges[:n_core]`。
    # 边表排过序（按 from,to），于是前 n 条全部挤在字典序最靠前的那一小撮 id 上 ——
    # 上一轮量出来「前 12 条边里有 7 条起点都是 arg-0001」。
    # 后果是无论把基础图造多大，语料库用到的节点永远是同一小撮：
    # **参数放大了，材料没有变。**
    core = _spread(edges, n_core)

    # ⚠️ 再保证 core 里有**足够多可互斥的边**。
    # 种类是轮转分配的，可互斥的只占三分之一，于是小 core 上「种 2 条矛盾」
    # 这个要求在图上根本无法满足 —— 而上一轮的表现是**直接报错、拒掉 62% 的配置**。
    # 那是把生成器的取法问题提给了调用方：要求是合理的，取法该由生成器负责。
    # 这里把 core 里非互斥的边换成 rest 里互斥的，长度不变。
    if n_contra > 0:
        _pool = [e for e in edges if e[2] in _CONTRADICTABLE]
        _have = [e for e in core if e[2] in _CONTRADICTABLE]
        _need = n_contra - len(_have)
        if _need > 0:
            _spare = [e for e in _pool if e not in set(core)]
            _swap = [e for e in core if e[2] not in _CONTRADICTABLE]
            for i in range(min(_need, len(_spare), len(_swap))):
                core[core.index(_swap[i])] = _spare[i]

    rest = [e for e in edges if e not in set(core)]
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
                mine.append((a, b, "contains"))
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
    # ⚠️ 第三版（上一轮）的修法是「四类各需专用视图，不够就报错」。
    # 它确实让 Test 3 全绿了 —— 但量出来的代价是：**144 个配置只有 54 个建得出来
    # （38% 可达）**，而且 54/54 都是「四类视图完全不重叠」的干净情形。
    # 真实视图不会体贴地各占一个视图，所以那套语料**测不到交叠**，
    # 也就测不到我上一轮自己发现的「同一单元两个主语」那个歧义。
    #
    # 所以现在改成：**优先专用，放不下就共用**（`allow_overlap`，默认开）。
    # 共用会带来「分类本来就该是别的类型」的样本 —— 那不是要消灭的噪声，
    # 那是**要测的东西**。它的处置在 `_classify_plantings()`：
    # 记下每个预埋项**按定义**该算哪一类，而不是一律当成漏报。
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
    if len(free) < need and not allow_overlap:
        raise ValueError(
            f"allow_overlap=False 时四类各需专用视图：精炼占用 {len(reserved)} 个，"
            f"剩下 {len(free)} 个可用，但还需要 {need} 个。"
            f"请把 n_views 提到至少 {len(reserved) + need}，或减少植入量。"
        )
    if len(free) < need:
        # 共用模式：拿全部视图当候选池。交叠会造出「按定义该算另一类」的样本，
        # 由 `_classify_plantings()` 逐条判定，不当成漏报。
        free = list(vids)
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
            cand = (a, b, "contains")
            if cand not in raw[fine] and cand not in extra:
                extra.append(cand)
        raw[fine] = sorted(set(list(raw[coarse]) + list(raw[fine]) + extra))
        for e in extra:
            truth["refinement"].add((coarse, fine, "edge", e))

    # ③ 矛盾：翻转关系
    if n_contra:
        # ⚠️ `% len(free)`：共用模式下 free = 全部视图，而 need 可能超过视图数
        # （例如 2 个视图要种 4 类）。不回绕就 IndexError —— 而那个错会穿到
        # 调用方，看起来像「生成器坏了」，其实是共用模式的正常情形。
        cview = free[cursor % len(free)]
        cursor += 1
        for (a, b, r) in contra_slice:
            raw[cview] = [e for e in raw[cview] if not (e[0] == a and e[1] == b)]
            raw[cview].append((a, b, "contradicts"))
            truth["contradiction"].add((a, b, r, "contradicts"))

    # ④ 缺失：删边（最后做，删了就不该再有人加回来）
    dropped = []
    if n_omit:
        oview = free[cursor % len(free)]
        cursor += 1
        for e in omit_slice:
            if e in raw[oview]:
                raw[oview] = [x for x in raw[oview] if x != e]
                dropped.append((oview, e))
                truth["omission"].add((oview, "edge", e))

    # ⑤ 形状旋钮：让语料能表达**上一轮表达不了的长相**。
    #
    # ⚠️ 上一轮量出来的覆盖率：空视图 0%、只有节点没有边的视图 0%、
    # 节点集完全不相交 2%、视图完全相等 0%、含孤立节点 0%。
    # 也就是说语料库只会造一种长相，而 DCE 在别的长相上会不会崩，
    # **一次都没测过**。这四类形状不是装饰，是能在实现里找出真 bug 的输入
    # （比如 `refinement_pairs` 曾把空视图当成「较粗」的一侧，
    # 而空视图正是这里造出来的）。
    #
    # 这些视图**不参与四类植入**（植入已经做完了），所以加进来不会污染 truth；
    # 它们带来的缺失会被 `_classify_plantings()` 当作「定义使然的额外检出」。
    shape_views = []
    shape_truth = {"empty": [], "node_only": [], "disjoint": [], "equal": []}
    used_nodes = {x for e in core for x in (e[0], e[1])}
    spare = [n for n in nodes if n not in used_nodes]
    for i in range(n_empty):
        shape_views.append(("E%d" % (i + 1), [], []))
        shape_truth["empty"].append("E%d" % (i + 1))
    for i in range(n_nodeonly):
        ns = sorted(used_nodes)[i::max(1, n_nodeonly)][:3] or sorted(used_nodes)[:1]
        shape_views.append(("N%d" % (i + 1), ns, []))
        shape_truth["node_only"].append("N%d" % (i + 1))
    for i in range(n_disjoint):
        chunk = spare[i::max(1, n_disjoint)][:4]
        if len(chunk) < 2:
            continue
        es = [(chunk[j], chunk[j + 1], "contains") for j in range(len(chunk) - 1)]
        shape_views.append(("D%d" % (i + 1), sorted(chunk), es))
        shape_truth["disjoint"].append("D%d" % (i + 1))
    for i in range(n_equal):
        # 与 V1 逐字节相同 —— Test 1（Identity）的单点版本，嵌在别的配置里
        base_es = sorted(set(raw[vids[0]]))
        shape_views.append(("Q%d" % (i + 1),
                            sorted({x for e in base_es for x in (e[0], e[1])}),
                            base_es))
        shape_truth["equal"].append("Q%d" % (i + 1))

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
    for vid, ns, es in shape_views:
        views.append(V.make_view(
            view_id=vid, source_ref=f"synthetic://{vid}",
            source_kind="experiment", nodes=ns, edges=es,
            metadata={"labels": {n: base["labels"].get(n, n) for n in ns}},
        ))

    # 共识的 ground truth = **定义**（全部视图的交集），不是「我以为共享的那些」
    from analysis import consensus as C
    truth["consensus"] = set.intersection(*[C.units_of(v) for v in views]) \
        if views else set()
    truth["n_views"] = n_views
    truth["core"] = set(core)
    truth["dropped"] = dropped
    truth["shapes"] = shape_truth
    truth["n_units"] = sum(len(C.units_of(v)) for v in views)

    # ── 存活校验 / 交叠分类 ─────────────────────────────────────────────
    #
    # ⚠️ 存活校验是踩出来的。上一轮四类依次植入，而**精炼那一步取的是并集** ——
    # 它把先前种下的矛盾翻转和缺失**又加回去了**。结果是：truth 里有 20 条缺失、
    # 10 条矛盾，而视图里一条都不剩，于是召回全是 0，看起来像 DCE 完全失效，
    # 其实是生成器自己把自己种的东西抹掉了。
    # **静默地种失败，在报告上长得和「算法漏报」一模一样。**
    #
    # ⚠️ 但上一轮的处置过头了：它**直接报错**，于是配置空间的 62% 被拒，
    # 而且剩下的 54/54 全是「四类各占专用视图」的干净情形。
    # 现在分两档：
    #
    #   allow_overlap=False  交叠一律当错误（上一轮的行为，保留作对照）
    #   allow_overlap=True   交叠**不报错**，而是逐条判定「按定义它该算哪一类」，
    #                        分不清的才报错。交叠本身是要测的东西，不是噪声。
    problems = _survival_problems(views, truth)
    truth["reclassified"] = []
    if allow_overlap:
        truth["reclassified"], hard = _classify_plantings(views, truth)
        # 硬错误只剩「预埋项在最终视图里根本不存在」那一类 ——
        # 那说明生成器没种上，与分类无关。
        problems = hard
    if problems:
        raise ValueError(
            "植入的结构没能活到视图构造结束：\n  - " + "\n  - ".join(problems[:8])
            + f"\n（共 {len(problems)} 条）。这是生成器的问题，不是 DCE 的问题。"
        )
    return views, truth


def _classify_plantings(views, truth) -> tuple:
    """把「预埋了 A 却按定义该算 B」逐条分出来。返回 `(reclassified, hard)`。

    ⚠️ 为什么需要它：交叠植入必然造出**分类本来就该是另一类**的样本。
    比如某个视图既是精炼的粗侧、又被删了一条边 —— 那条缺失按定义会被
    refinement 认领（`refinement_covered`），所以它**正确地**不该报成 omission。

    这不是要消灭的噪声，是**要测的东西**：它正是「同一单元、两个主语」那个歧义的
    具体形态。把它一律记成漏报，恢复率就会因为定义问题而不是错误变差 ——
    上一轮我用「precision 走定义校验」绕过了这一点，但那是**绕过**，不是测。

    这里把每条预埋项的**应有类型**独立算出来（用的是与 DCE 不同的代码路径：
    直接调定义判据，不跑 `divergence.analyse`），于是：
      - 应有的类型 == 预埋的类型   → 正常，DCE 该报出来
      - 应有的类型 != 预埋的类型   → reclassified，记下原因
      - 预埋的单元在视图里不存在    → hard（生成器没种上）
    """
    from analysis import consensus as C
    from analysis import divergence as D
    by_id = {v["id"]: v for v in views}
    unit_of = {v["id"]: C.units_of(v) for v in views}
    ref_covered = {v["id"]: D.refinement_covered(v, views) for v in views}
    reclassified, hard = [], []

    for (vi, kind, key) in truth["omission"]:
        if vi not in unit_of:
            hard.append(f"缺失：视图 {vi} 不存在")
            continue
        u = (kind, key)
        if u in unit_of[vi]:
            hard.append(f"缺失：{vi} 仍然有 {key}")
            continue
        if u in ref_covered[vi]:
            reclassified.append({
                "planted": "omission", "subject": (vi, kind, str(key)),
                "actually": "refinement",
                "why": f"{vi} 是某个精炼对的粗侧，这条缺失被 refinement 认领",
            })
        elif kind == "edge" and D._has_exclusive_counterpart(
                by_id[vi], key[0], key[1], key[2]):
            reclassified.append({
                "planted": "omission", "subject": (vi, kind, str(key)),
                "actually": "contradiction",
                "why": f"{vi} 在同一对端点上说了互斥的话",
            })

    for (a, b, r1, r2) in truth["contradiction"]:
        holders = {r: [vid for vid, us in unit_of.items() if ("edge", (a, b, r)) in us]
                   for r in (r1, r2)}
        if not holders[r1] or not holders[r2]:
            hard.append(f"矛盾：{a}->{b} 的 {r1}/{r2} 有一边一个视图都没有")
        elif set(holders[r1]) & set(holders[r2]):
            reclassified.append({
                "planted": "contradiction", "subject": (a, b, r1, r2),
                "actually": "同视图内部不一致",
                "why": f"两种关系同时出现在 {sorted(set(holders[r1]) & set(holders[r2]))} "
                       "里 —— 同视图内部的不一致不算跨视图分歧",
            })

    for (coarse, fine, kind, key) in truth["refinement"]:
        if coarse not in unit_of or fine not in unit_of:
            hard.append(f"精炼：视图 {coarse}/{fine} 不存在")
            continue
        if not (unit_of[coarse] < unit_of[fine]):
            reclassified.append({
                "planted": "refinement", "subject": (coarse, fine, kind, str(key)),
                "actually": "无（不再是精炼对）",
                "why": f"{coarse} ⊂ {fine} 不成立 —— 交叠植入把子集关系破坏了",
            })
        elif (kind, key) not in (unit_of[fine] - unit_of[coarse]):
            reclassified.append({
                "planted": "refinement", "subject": (coarse, fine, kind, str(key)),
                "actually": "无（单元不在差集里）",
                "why": f"{key} 不在 {fine} 比 {coarse} 多出来的部分里",
            })

    for item in truth["alternative"]:
        src, rel, t1, t2, va, vb = item
        def succ(vid):
            return {e["to"] for e in by_id[vid]["edges"]
                    if e["from"] == src and e["relation"] == rel}
        sa, sb = succ(va), succ(vb)
        if not sa or not sb:
            hard.append(f"竞争解释：{src}--{rel} 有一边没有后继（{va}/{vb}）")
        elif sa <= sb or sb <= sa:
            reclassified.append({
                "planted": "alternative", "subject": (src, rel, str(t1), str(t2)),
                "actually": "refinement/omission",
                "why": f"{va}/{vb} 的后继集合有包含关系",
            })
    return reclassified, hard


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
