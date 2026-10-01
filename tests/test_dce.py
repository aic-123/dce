"""DCE 的测试。

⚠️ **为什么全部写成「纯 `def test_*()` + `assert`」而不是用 pytest 的特性**：
本机没有 pytest。§十七 同时要求「纯标准库」与「pytest」——这两条只能这样同时满足：

    pytest 在的时候   pytest tests/      能收集、能跑
    pytest 不在的时候 python tests/run_tests.py   也能跑

用的是同一个文件、同一批断言。用 fixture / parametrize 就绑死在 pytest 上了，
而「跑测试要先装东西」正是这个仓库想避开的。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis import consensus as C          # noqa: E402
from analysis import divergence as D         # noqa: E402
from analysis import focus as F              # noqa: E402
from analysis import synthesis as S          # noqa: E402
from core import edge as E                   # noqa: E402
from core import provenance as P             # noqa: E402
from core import view as V                   # noqa: E402
from generators import synthetic as SYN      # noqa: E402
from metrics import compression as CMP       # noqa: E402
from metrics import coverage as COV          # noqa: E402


def mk(vid, nodes, edges, kind="experiment"):
    return V.make_view(view_id=vid, source_ref=f"synthetic://{vid}",
                       source_kind=kind, nodes=nodes, edges=edges)


# ── core：形状校验 ──────────────────────────────────────────────────

def test_view_rejects_extra_toplevel_field():
    v = mk("A", ["con-0001"], [])
    try:
        V.verify({**v, "weight": 1.0})
    except V.ViewError:
        return
    raise AssertionError("顶层多一个 weight 竟然没被拦")


def test_view_rejects_edge_without_relation():
    v = mk("A", ["con-0001", "con-0002"], [])
    try:
        V.verify({**v, "edges": [{"from": "con-0001", "to": "con-0002"}]})
    except V.ViewError:
        return
    raise AssertionError("边缺 relation 竟然没被拦")


def test_view_rejects_dangling_edge():
    v = mk("A", ["con-0001"], [])
    try:
        V.verify({**v, "edges": [("con-0001", "con-0009", "supports")]})
    except V.ViewError:
        return
    raise AssertionError("边引用不存在的节点竟然没被拦")


def test_view_rejects_unknown_source_kind():
    try:
        V.verify(mk("A", ["con-0001"], [], kind="vibes"))
    except V.ViewError:
        return
    raise AssertionError("source.kind 不在封闭集合里竟然没被拦")


def test_fingerprint_is_insertion_order_independent():
    a = mk("A", ["con-0002", "con-0001"], [("con-0001", "con-0002", "supports")])
    b = mk("A", ["con-0001", "con-0002"], [("con-0001", "con-0002", "supports")])
    assert V.fingerprint(a) == V.fingerprint(b), "同内容不同插入顺序指纹应当相同"


def test_fingerprint_changes_when_content_changes():
    a = mk("A", ["con-0001", "con-0002"], [("con-0001", "con-0002", "supports")])
    b = mk("A", ["con-0001", "con-0002"], [("con-0001", "con-0002", "contradicts")])
    assert V.fingerprint(a) != V.fingerprint(b), "关系种类变了指纹必须变"


# ── core：边身份与词表 ─────────────────────────────────────────────

def test_edge_identity_includes_direction_and_relation():
    """§九 的反例：A supports B 与 B supports A 不是同一条结构边。"""
    assert E.key(("con-0001", "con-0002", "supports")) != \
        E.key(("con-0002", "con-0001", "supports"))
    assert E.key(("con-0001", "con-0002", "supports")) != \
        E.key(("con-0001", "con-0002", "contradicts"))
    assert E.endpoints(("con-0002", "con-0001", "supports")) == \
        E.endpoints(("con-0001", "con-0002", "supports"))


def test_relation_kinds_are_closed():
    for k in E.KNOWN_KINDS:
        E.check_kind(k)                       # 已知的不该报错
    try:
        E.check_kind("vibes_with")
    except E.EdgeError:
        return
    raise AssertionError("表外关系种类竟然被放过 —— 放过之后「种类」会退化成自由文本")


def test_exclusive_pairs_are_exactly_these():
    """钉住互斥集。想多声明一对，必须改这一行，改的时候会被看见。"""
    want = (("contradicts", "qualifies"), ("contradicts", "supports"),
            ("qualifies", "supports"))
    assert E.EXCLUSIVE_PAIRS == want, f"互斥集被改动了：{E.EXCLUSIVE_PAIRS}"


def test_exclusive_is_symmetric_and_irreflexive():
    assert E.exclusive("supports", "contradicts")
    assert E.exclusive("contradicts", "supports")
    assert not E.exclusive("supports", "supports")
    assert not E.exclusive("supports", "refines")


# ── core：溯源 ──────────────────────────────────────────────────────

def test_provenance_rejects_empty():
    try:
        P.make()
    except P.ProvenanceError:
        return
    raise AssertionError("空溯源竟然没被拦 —— §C9 #9 禁止无法追溯的结构")


def test_provenance_rejects_phantom_unit():
    a = mk("A", ["con-0001"], [])
    try:
        P.verify_against([P.ref("A", "node", "con-9999")], [a])
    except P.ProvenanceError:
        return
    raise AssertionError("指向不存在单元的溯源竟然没被拦 —— 那让溯源只是「像」溯源")


def test_provenance_rejects_focus_as_source():
    a = mk("A", ["con-0001"], [])
    try:
        P.verify_against([P.ref("A", "focus", "F1")], [a])
    except P.ProvenanceError:
        return
    raise AssertionError("focus 作为溯源来源竟然没被拦 —— 那是自引用")


def test_merge_dedups_while_make_rejects_duplicates():
    """`make()` 拒绝重复，`merge()` 允许 —— 这个区别是踩出来的。"""
    r = P.ref("A", "node", "con-0001")
    try:
        P.make(r, r)
        raise AssertionError("make 应当拒绝同一来源重复")
    except P.ProvenanceError:
        pass
    assert len(P.merge([r], [r])) == 1, "merge 应当去重后只剩一条"


def test_check_distinct_rejects_duplicates_and_singleton():
    a = mk("A", ["con-0001"], [])
    b = mk("A", ["con-0002"], [])
    try:
        V.check_distinct([a, b])
        raise AssertionError("视图 id 重复竟然没被拦")
    except V.ViewError:
        pass
    try:
        V.check_distinct([a])
        raise AssertionError("只有一个视图竟然没被拦")
    except V.ViewError:
        pass


# ── analysis：共识是合取，不是比例 ─────────────────────────────────

def test_consensus_is_conjunction_not_ratio():
    """出现在 2/3 个视图里的单元**不是**共识。这是本仓库与设计稿 §八 的分界。"""
    a = mk("A", ["con-0001", "con-0002"], [("con-0001", "con-0002", "supports")])
    b = V.clone(a); b["id"] = "B"; b["source"]["ref"] = "x://B"
    c = mk("C", ["con-0001", "con-0002"], [])
    cons = C.consensus([a, b, c])
    keys = {(r["unit"]["kind"], r["unit"]["key"]) for r in cons}
    assert ("edge", ("con-0001", "con-0002", "supports")) not in keys, \
        "只出现在 2/3 视图里的边不该算共识"
    assert ("node", "con-0001") in keys, "三个视图都有的节点该算共识"


def test_support_is_a_tuple_not_a_ratio():
    a = mk("A", ["con-0001"], [])
    b = mk("B", ["con-0001"], [])
    c = mk("C", [], [])
    assert C.support([a, b, c], ("node", "con-0001")) == (2, 3)
    assert isinstance(C.support([a, b, c], ("node", "con-0001")), tuple)


def test_support_table_is_sorted_by_key_not_by_support():
    a = mk("A", ["con-0002", "con-0001"], [])
    b = mk("B", ["con-0001"], [])
    rows = C.support_table([a, b])
    keys = [str(r["unit"]["key"]) for r in rows]
    assert keys == sorted(keys), f"support 表必须按 key 排，实测 {keys}"


# ── analysis：四类的边界 ────────────────────────────────────────────

def test_omission_vs_contradiction_boundary():
    """§五·三：B 没表态是 omission，B 说相反的话是 contradiction。"""
    a = mk("A", ["con-0001", "judge-0001"],
           [("con-0001", "judge-0001", "supports")])
    silence = mk("B", [], [])
    d = D.analyse([a, silence])
    assert len(d["omission"]) == 3 and len(d["contradiction"]) == 0, \
        "B 什么都不说是 omission，不是矛盾"

    against = mk("B", ["con-0001", "judge-0001"],
                 [("con-0001", "judge-0001", "contradicts")])
    d = D.analyse([a, against])
    assert len(d["contradiction"]) == 1, "B 说相反的话必须报矛盾"
    assert all(r["type"] != "omission" or r["unit"]["kind"] == "node"
               for r in d["omission"]), "同一对端点上不该既报矛盾又报缺失"


def test_empty_view_is_not_a_refinement_coarse():
    """空集是任何集合的子集，但「什么都没说」不是「说得比较粗」。"""
    a = mk("A", ["con-0001"], [])
    empty = mk("B", [], [])
    d = D.analyse([a, empty])
    assert len(d["refinement"]) == 0, "空视图不该被当成精炼的粗侧"
    assert len(d["omission"]) > 0, "空视图缺的东西该报成 omission"


def test_refinement_takes_precedence_over_omission():
    coarse = mk("A", ["con-0001"], [])
    fine = mk("B", ["con-0001", "judge-0001", "cond-0001"],
              [("con-0001", "judge-0001", "supports"),
               ("con-0001", "cond-0001", "refines")])
    d = D.analyse([coarse, fine])
    assert len(d["refinement"]) == 4, f"细侧多出 4 个单元，实测 {len(d['refinement'])}"
    assert len(d["omission"]) == 0, "被 refinement 认领掉的单元不该再报 omission"


def test_alternative_requires_incomparable_successor_sets():
    a = mk("A", ["con-0001", "con-0002"], [("con-0001", "con-0002", "supports")])
    b = mk("B", ["con-0001", "con-0003"], [("con-0001", "con-0003", "supports")])
    d = D.analyse([a, b])
    assert len(d["alternative"]) == 1, "后继互不包含该报竞争解释"

    # 一边是另一边的子集 → 那该归 refinement 或 omission，不是竞争解释
    c = mk("C", ["con-0001", "con-0002", "con-0003"],
           [("con-0001", "con-0002", "supports"), ("con-0001", "con-0003", "supports")])
    d2 = D.analyse([a, c])
    assert len(d2["alternative"]) == 0, "有包含关系时不该报竞争解释"


def test_focus_numbering_is_order_independent():
    base = SYN.base_graph(n_nodes=10, n_edges=12, seed=11)
    views, _t = SYN.make(base, {"n_views": 3, "n_core": 6, "private": 2,
                                "contradictions": 2, "omissions": 2})
    f1 = F.foci(D.analyse(views))
    f2 = F.foci(D.analyse(list(reversed(views))))
    assert [(x["focus"], x["anchors"]) for x in f1] == \
        [(x["focus"], x["anchors"]) for x in f2], "焦点编号与输入顺序无关"


# ── §十五 四组测试 ─────────────────────────────────────────────────

def test_section15_four_groups_all_pass():
    from checks import identity, interference, reconstruction
    for title, ok, detail in (identity.run_all() + interference.run_all()
                              + reconstruction.run_all()):
        assert ok, f"{title} 红了：{detail}"


# ── §十六 消融 ─────────────────────────────────────────────────────

def test_ablation_assertions_pass():
    from checks import ablation
    for title, ok, detail in ablation.run_all():
        assert ok, f"{title} 红了：{detail}"


def test_section20_scope_assertions_pass():
    """§二十 的排除项。盯的是**能力**有没有被实现，不是词有没有出现 ——
    因为 §十四 要求 ground truth、§十六 的基线 A 就叫 Embedding similarity，
    朴素的词扫描会把设计稿自己要求的东西扫成违规。"""
    from checks import scope
    for title, ok, detail in scope.run_all():
        assert ok, f"{title} 红了：{detail}"


def test_corpus_counterexample_scan_passes():
    """**反例扫描**：每条「必须处处成立」的结论拿到 700 个配置上撞一遍。

    上一轮的全部结论都只在**一个标题配置**上验过，而那个配置所在的语料库
    可达率只有 38%、形状覆盖近乎为零。一个点上的结论和一个扫描过的结论，
    在报告里长得一样 —— 这个测试就是用来分开它们的。
    """
    from checks import corpus
    for title, ok, detail in corpus.run_all():
        assert ok, f"{title} 红了：{detail}"


def test_recall_gap_is_explained_by_reclassification():
    """交叠配置下 strict 召回会掉，但**真漏必须是 0**。

    ⚠️ 这条钉的是本仓库对 §十五 Test 3 的收紧：
    「植入 10/20/10/5，DCE 必须能够**分别**恢复它们」这句话，
    只有在预埋项两两无歧义时才有定义 —— 而那需要「四类各占专用视图」的构造。
    真实交叠下四类会碰撞，「分别恢复」不是一个良定义的量。

    所以召回必须分三档报：strict / accounted / 真漏。
    只报 strict，会把「按定义该算另一类」和「算法漏了」算成同一个 0。
    """
    from checks import corpus
    r = corpus.scan(limit=120)
    for t, d in r["recalls"].items():
        assert d["unexplained"] == 0, f"{t} 有 {d['unexplained']} 条真漏"
    # 至少有一类在交叠下 strict 掉了 —— 否则这个测试是空转的
    dropped = [t for t, d in r["recalls"].items()
               if d["n"] and d["min_strict"] is not None and d["min_strict"] < 1.0]
    assert dropped, "没有任何一类的 strict 召回掉落 —— 交叠没被真正测到，检查是空转的"


def test_dce_partition_equals_frequency_partition():
    """**这是这一轮最重要的发现，所以钉成断言。**"""
    from checks import ablation
    r = ablation.compare(ablation.HEADLINE)
    assert r["partition_same"], \
        f"DCE 的划分竟然与 union+frequency 不同：{r['partition_diff']}"


def test_increment_is_expressiveness_not_accuracy():
    """DCE 的增量在类型上；粗任务上与基线一样准。把这条钉住，
    免得后来的人把「5 类准确率更高」读成「DCE 更准」。"""
    from checks import ablation
    r = ablation.compare(ablation.HEADLINE)
    assert r["baseline_coarse_acc"] == 1.0, \
        f"基线在粗任务上应当是满分，实测 {r['baseline_coarse_acc']}"
    assert r["dce_5class_acc"] > r["baseline_5class_acc"]


# ── §十三 两个指标 ─────────────────────────────────────────────────

def test_coverage_is_degenerate_but_not_broken():
    """Coverage 恒等于 1 是本设计的**推论**（分歧逐条罗列 → 没有第三种单元）。

    这里断言的不是「它等于 1」，而是**它不产生幻影**：
    合成里不许出现源视图里没有的单元。幻影才是 bug。
    """
    base = SYN.base_graph(n_nodes=20, n_edges=30, seed=3)
    views, _t = SYN.make(base, {"n_views": 3, "n_core": 8, "private": 2,
                                "omissions": 2})
    syn = S.build(views)
    cov = COV.coverage(views, syn)
    assert cov["phantom"] == [], f"合成里出现了源视图没有的单元：{cov['phantom']}"
    assert cov["value"] == 1.0, f"Coverage 不是 1：{cov['value']}"


def test_compression_modes_are_ordered():
    """focused 比 flat 压得更多（把一堆记录概括成焦点）。三档不许反序。"""
    base = SYN.base_graph(n_nodes=20, n_edges=30, seed=4)
    views, _t = SYN.make(base, {"n_views": 5, "n_core": 9, "private": 2})
    syn = S.build(views)
    k = CMP.compression(views, syn)["all_modes"]
    assert k["focused"] >= k["flat"], f"focused({k['focused']}) 不该低于 flat({k['flat']})"


def test_synthesis_has_no_forbidden_keys():
    base = SYN.base_graph(n_nodes=10, n_edges=12, seed=41)
    views, _t = SYN.make(base, {"n_views": 7, "n_core": 8, "private": 1,
                                "contradictions": 1, "omissions": 1,
                                "refinements": 1, "alternatives": 1})
    hits = S.forbidden_keys_in(S.build(views))
    assert not hits, f"产物里出现了评分/权重/真值词汇：{hits}"


def test_synthesis_provenance_matches_views():
    base = SYN.base_graph(n_nodes=10, n_edges=12, seed=51)
    views, _t = SYN.make(base, {"n_views": 3, "n_core": 6, "private": 2})
    syn = S.build(views)
    recorded = {p["id"]: p["fingerprint"] for p in syn["provenance"]["views"]}
    live = {v["id"]: V.fingerprint(v) for v in views}
    assert recorded == live, "合成里记的指纹与当场重算不一致"
    S.verify_synthesis(syn, views)
