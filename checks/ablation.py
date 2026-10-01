"""§十六 消融：三个基线，以及 DCE 相对它们到底多了什么。

设计稿 §十六 给的三个基线：

    Baseline A   Embedding similarity          「相似度能不能找到相近内容？」
    Baseline B   Embedding + clustering        「聚类能不能形成主题区域？」
    Baseline C   Graph union + frequency       「**DCE 是否只是 graph frequency bookkeeping？**」

最后一句是这一整组消融真正的问题。所以本模块的重点在 C。

---
三个必须先说清的取舍
-------------------

**一、Embedding 换成声明过的替代品。** §十七 要求纯标准库，而 Embedding 需要一个模型。
本模块用的是 **字符二元组 Dice**（rl-scaffold `tools/find_path.py` 的 `MATCH_SPEC`
就是这一条），并**明确标成「相似度的替代品，不是 embedding」**。
不这么做就只有两条路：引入一个被禁的依赖，或者假装一个不存在的东西跑过了。

**二、基线 B 需要一条线，DCE 不需要。** "聚类"必须有一个切分阈值；
`§T0.3` 禁止拍阈值。所以本模块把 B 的阈值**当旋钮扫描，报它最好的一档** ——
**给基线它最强的一击**，然后同时报出「它需要一条扫出来的线，而 DCE 没有这条线」。
不这么做，比较就赢在一个我自己选的阈值上。

**三、划分可能完全相同。** 「哪些单元是共识、哪些是分歧」这个划分，
DCE 与 baseline C **在定义上就是同一个**（都是 `出现次数 == 视图数`）。
所以本模块把这条**算出来并断言下来**，而不是回避它：

    DCE 的增量**不在划分上**，在**类型**上。

这是一个**表达力**增量（2 类 → 5 类），不是粗任务上的**准确率**增量。
把它说成「DCE 比 union 更准」是错的 —— 粗任务上两者一样准。
"""

from __future__ import annotations

from analysis import consensus as C
from analysis import synthesis as S

# DCE 认的种类（设计稿 §六 的树）。
DCE_CLASSES = ("consensus", "contradiction", "alternative", "omission", "refinement")
# 基线的种类：只有「共识 / 分歧」两档。
BASELINE_CLASSES = ("consensus", "divergence")


# ── Baseline A 的替代品：字符二元组 Dice ──────────────────────────────
def bigrams(s: str) -> set:
    s = " ".join((s or "").lower().split())
    return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) > 1 else ({s} if s else set())


def dice(a: str, b: str) -> float:
    A, B = bigrams(a), bigrams(b)
    if not A or not B:
        return 0.0
    return 2 * len(A & B) / (len(A) + len(B))


def label_of(view, node: str) -> str:
    return ((view.get("metadata") or {}).get("labels") or {}).get(node, node)


def unit_surprise(views) -> dict:
    """Baseline A 的排分：单元的「意外度」= 1 − 两端标签的相似度。

    节点单元的意外度取 0（一个孤立节点没有"两端"）—— 这是**定义**，
    不是为了让结果好看而挑的。相似度这个方法本来就只对"关系"说话。
    """
    out = {}
    for v in views:
        for e in v["edges"]:
            u = ("edge", (e["from"], e["to"], e["relation"]))
            out[u] = 1.0 - dice(label_of(v, e["from"]), label_of(v, e["to"]))
        for n in v["nodes"]:
            out.setdefault(("node", n), 0.0)
    return out


# ── Baseline B：相似度 + 聚类（阈值当旋钮扫）──────────────────────────
def cluster_nodes(view, cut: float) -> dict:
    """按「相似度 ≥ cut」把节点并成簇。并查集，确定性。"""
    nodes = list(view["nodes"])
    idx = {n: i for i, n in enumerate(nodes)}
    parent = list(range(len(nodes)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            if dice(label_of(view, nodes[i]), label_of(view, nodes[j])) >= cut:
                a, b = find(i), find(j)
                if a != b:
                    parent[b] = a
    return {n: find(idx[n]) for n in nodes}


def cross_cluster_score(views, cut: float) -> dict:
    """Baseline B 的排分：单元的端点是否落在不同簇。跨簇 = 更可能是分歧。"""
    out = {}
    for v in views:
        cl = cluster_nodes(v, cut)
        for e in v["edges"]:
            u = ("edge", (e["from"], e["to"], e["relation"]))
            out[u] = 1.0 if cl[e["from"]] != cl[e["to"]] else 0.0
    return out


# ── Baseline C：并集 + 频次 ──────────────────────────────────────────
def union_frequency(views) -> dict:
    """每个单元出现过的视图数。**就是设计稿 §八 的 `support`。**"""
    out = {}
    for v in views:
        for u in C.units_of(v):
            out[u] = out.get(u, 0) + 1
    return out


def frequency_partition(views) -> dict:
    """把频次划分成 共识 / 分歧。**唯一的无参数划分：出现次数是否等于视图数。**"""
    freq = union_frequency(views)
    n = len(views)
    return {u: ("consensus" if c == n else "divergence") for u, c in freq.items()}


# ── DCE 的划分（独立算一遍，不复用 frequency 的代码）────────────────
def dce_partition(views) -> dict:
    syn = S.build(views)
    cons = {(r["unit"]["kind"], r["unit"]["key"]) for r in syn["consensus"]["records"]}
    out = {}
    for u in C.universe(views):
        out[u] = "consensus" if u in cons else "divergence"
    return out


def dce_typed(views) -> dict:
    """DCE 在 5 类上的判词：单元 → 类型。共识优先，其余按记录类型。"""
    syn = S.build(views)
    out = {(r["unit"]["kind"], r["unit"]["key"]): "consensus"
           for r in syn["consensus"]["records"]}
    for rec in syn["divergence"]:
        t = rec["type"]
        if t in ("omission", "refinement"):
            out.setdefault((rec["unit"]["kind"], rec["unit"]["key"]), t)
        elif t == "contradiction":
            # 矛盾的两条边都算「矛盾」这一类的载体
            for rel in rec["relations"]:
                out.setdefault(("edge", (rec["from"], rec["to"], rel)), t)
        elif t == "alternative":
            for _vid, targets in rec["views"].items():
                for x in targets:
                    out.setdefault(("edge", (rec["source"], x, rec["relation"])), t)
    return out


def _auc(pos: list, neg: list) -> float:
    """优超概率（与 field 仓库同一个定义：并列按 0.5）。无阈值、无分布假设。"""
    if not pos or not neg:
        return None
    w = 0.0
    for a in pos:
        for b in neg:
            w += 1.0 if a > b else (0.5 if a == b else 0.0)
    return w / (len(pos) * len(neg))


def compare(spec: dict, seed: int = 20261010) -> dict:
    """在同一张植入测试床上比 DCE 与三个基线。"""
    from generators import synthetic as SYN
    base = SYN.base_graph(n_nodes=max(30, spec.get("n_core", 40) * 2),
                          n_edges=max(60, spec.get("n_core", 40) * 3), seed=seed)
    views, truth = SYN.make(base, spec, seed=seed + 1)
    syn = S.build(views)

    # ① 划分是否相同
    fp = frequency_partition(views)
    dp = dce_partition(views)
    same = fp == dp
    diff = [u for u in fp if fp[u] != dp.get(u)]

    # ② 类型分辨率
    dce_cls = dce_typed(views)

    # ③ 植入项上的 5 类准确率
    planted = []      # (unit, 真类型)
    for (vi, kind, key) in truth["omission"]:
        planted.append(((kind, key), "omission"))
    for (a, b, r1, r2) in truth["contradiction"]:
        planted.append((("edge", (a, b, r1)), "contradiction"))
    for (coarse, fine, kind, key) in truth["refinement"]:
        planted.append(((kind, key), "refinement"))
    for item in truth["alternative"]:
        src, rel, t1, t2 = item[0], item[1], item[2], item[3]
        planted.append((("edge", (src, t1, rel)), "alternative"))
    for u in truth["consensus"]:
        planted.append((u, "consensus"))

    dce_hit = sum(1 for u, t in planted if dce_cls.get(u) == t)
    # 基线 C 只能给两档：共识说得对，其余四类一律只能说「分歧」
    base_hit = sum(1 for u, t in planted if t == "consensus"
                   and fp.get(u) == "consensus")
    # 基线 C 在粗任务（共识/分歧）上的准确率
    base_coarse = sum(1 for u, t in planted
                      if (fp.get(u) == "consensus") == (t == "consensus"))

    # ④ 分歧单元上的 AUC：DCE 的判据是二值的，基线的排分是连续的
    planted_div = [u for u, t in planted if t != "consensus"]
    planted_con = [u for u, t in planted if t == "consensus"]
    surp = unit_surprise(views)
    a_pos = [surp.get(u, 0.0) for u in planted_div]
    a_neg = [surp.get(u, 0.0) for u in planted_con]
    auc_a = _auc(a_pos, a_neg)

    best_b, best_cut = None, None
    for cut in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9):
        cc = cross_cluster_score(views, cut)
        v = _auc([cc.get(u, 0.0) for u in planted_div],
                 [cc.get(u, 0.0) for u in planted_con])
        if v is not None and (best_b is None or v > best_b):
            best_b, best_cut = v, cut

    return {
        "views": len(views), "units": len(C.universe(views)),
        "partition_same": same, "partition_diff": diff[:5],
        "n_planted": len(planted),
        "dce_5class_acc": dce_hit / len(planted) if planted else None,
        "baseline_5class_acc": base_hit / len(planted) if planted else None,
        "baseline_coarse_acc": base_coarse / len(planted) if planted else None,
        "dce_classes": len(DCE_CLASSES), "baseline_classes": len(BASELINE_CLASSES),
        "auc_similarity": auc_a,
        "auc_similarity_cluster_best": best_b, "cut_best": best_cut,
        "n_planted_div": len(planted_div), "n_planted_con": len(planted_con),
        "syn": syn,
    }


HEADLINE = {"n_views": 16, "n_core": 40, "private": 3,
            "contradictions": 10, "omissions": 20,
            "refinements": 5, "alternatives": 5}


def report() -> list:
    r = compare(HEADLINE)
    f = lambda x, d=3: "—" if x is None else f"{x:.{d}f}"    # noqa: E731
    return [
        ("测试床", f"{r['views']} 个视图 / {r['units']} 个单元 / 植入 {r['n_planted']} 项"
                   f"（分歧 {r['n_planted_div']}、共识 {r['n_planted_con']}）"),
        ("① 划分是否与 union+frequency 相同", f"**{r['partition_same']}**"
         + ("" if r['partition_same'] else f"，不同 {len(r['partition_diff'])} 处")),
        ("② 类别分辨率：DCE vs 基线",
         f"{r['dce_classes']} 类 vs {r['baseline_classes']} 类"),
        ("③ 植入项上的 5 类准确率：DCE", f(r["dce_5class_acc"])),
        ("   同一任务上基线 C 的**最好可能**",
         f"{f(r['baseline_5class_acc'])}（它只会说「共识」，其余四类一律说「分歧」）"),
        ("   基线 C 在**粗任务**（共识/分歧）上", f(r["baseline_coarse_acc"])),
        ("④ 分歧 vs 共识 的 AUC：相似度（基线 A）", f(r["auc_similarity"])),
        ("   相似度+聚类（基线 B，扫阈值取最好）",
         f"{f(r['auc_similarity_cluster_best'])}（最好那档 cut={r['cut_best']}）"),
    ]


def run_all() -> list:
    """能当断言用的三条。**都是相对比较，不是拍出来的绝对线。**

    ⚠️ 第三条尤其重要：它把「DCE 的增量在类型上、不在划分上」这个结论**钉死**。
    少了它，很容易把「5 类准确率高于基线」读成「DCE 更准」——
    而粗任务上两者一样准，那是个表达力差别。
    """
    r = compare(HEADLINE)
    out = [
        ("消融① DCE 的划分与 union+frequency 完全相同",
         r["partition_same"],
         "两者在定义上就是同一个（出现次数 == 视图数）"
         if r["partition_same"] else f"不同 {len(r['partition_diff'])} 处"),
        ("消融③ DCE 的 5 类准确率 > 基线的最好可能",
         (r["dce_5class_acc"] or 0) > (r["baseline_5class_acc"] or 0),
         f"{r['dce_5class_acc']:.3f} vs {r['baseline_5class_acc']:.3f}"),
        ("消融④ 基线在**粗任务**上与 DCE 一样准（增量在类型，不在划分）",
         abs((r["baseline_coarse_acc"] or 0) - 1.0) < 1e-9,
         f"基线粗任务准确率 {r['baseline_coarse_acc']:.3f} —— "
         "所以「DCE 更准」这句话只在 5 类任务上成立"),
    ]
    return out
