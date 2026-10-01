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


# ── §十八 adapter 与边界 ────────────────────────────────────────────

def test_adapters_boundary_assertions_pass():
    """「核心不能被上游结构带跑」的可执行形式。"""
    from checks import boundary
    for title, ok, detail in boundary.run_all():
        assert ok, f"{title} 红了：{detail}"


def test_core_never_imports_adapters():
    """方向：核心不许依赖边界层。方向一旦反过来，不会让任何测试变红 ——
    DCE 只会慢慢变成 arena 的一次重新实现。"""
    from checks import boundary
    ok, detail = boundary.check_core_does_not_import_adapters()
    assert ok, detail


def test_scaffold_view_cannot_contradict():
    """Scaffold 的关系没有种类 → 从它出来的视图**不可能产生矛盾**。
    这是形状的事实，而 adapter 必须把它声明出来，不能留给读者去猜。"""
    from adapters import scaffold as SC
    a = SC.to_view("SC", [{"id": "con-0001", "relations": ["judge-0001"]},
                          {"id": "judge-0001", "relations": []}])
    assert "contradiction" not in a.can_produce, \
        f"Scaffold 视图声称能产生矛盾：{a.can_produce}"
    assert any("没有种类" in x for x in a.losses), "「关系没有种类」这条损失没被记账"


def test_arena_view_drops_interaction_layer():
    """arena adapter 必须丢掉投票与修订，并逐条记账。"""
    from adapters import arena as A
    art = [{"id": "claim-0001", "type": "claim", "author": "u1",
            "state": "active", "created_at": "2026"},
           {"id": "vote-0001", "type": "vote", "author": "u2"}]
    rels = [{"kind": "supports", "from_id": "claim-0001", "to_id": "claim-0001",
             "seq": 3}]
    avs = A.to_views(art, rels)
    assert avs, "没产出任何视图"
    joined = " ".join(x for a in avs for x in a.losses)
    assert "vote" in joined, "丢掉投票这件事没被记账"
    # 结构里不许留下交互层字段
    import json
    blob = json.dumps([a.view for a in avs], ensure_ascii=False)
    for bad in ("vote", "revision", "seq", "state", "created_at", "superseded_by"):
        assert f'"{bad}"' not in blob, f"视图里残留了交互层字段 {bad}"


def test_adapter_can_produce_follows_the_data():
    """`can_produce` 必须跟着**实际吐出的种类**走，不能写死。

    ⚠️ 判据是「**词表里**有没有哪一种与它互斥」，不是「这组种类内部有没有互斥的一对」——
    因为**矛盾是跨视图的**：一个视图说 `supports`、另一个说 `contradicts`，
    单看前一个视图当然看不到互斥对。

    （我第一版把这条判据写成了后者，于是「只有 supports 的视图不能产生矛盾」
    被判成正确；后来发现那与矛盾的定义冲突。同一个错在
    `adapters.check_can_produce` 里也犯过一次 —— 写测试又犯一次。）
    """
    from core import edge as E
    from adapters import arena as A
    from adapters import derived_can_produce

    art = [{"id": "claim-0001", "type": "claim", "author": "u1"},
           {"id": "claim-0002", "type": "claim", "author": "u1"}]
    only_supports = [{"kind": "supports", "from_id": "claim-0001",
                      "to_id": "claim-0002"}]
    a = A.to_views(art, only_supports)[0]
    assert "contradiction" in a.can_produce, (
        "`supports` 在词表里有互斥对应（contradicts），所以这个视图**能**参与矛盾 —— "
        "矛盾是跨视图的，不需要它自己内部先有一对互斥关系"
    )
    assert E.exclusive("supports", "contradicts")

    # 真正的反例是**没有互斥对应**的种类：Scaffold 的占位种类
    from adapters import scaffold as SC
    sc = SC.to_view("SC", [{"id": "con-0001", "relations": ["judge-0001"]},
                           {"id": "judge-0001", "relations": []}])
    assert E.SCAFFOLD_UNTYPED in {e["relation"] for e in sc.view["edges"]}
    assert not any(E.exclusive(E.SCAFFOLD_UNTYPED, o)
                   for o in E.KNOWN_KINDS if o != E.SCAFFOLD_UNTYPED), \
        "占位种类不该在互斥集里有对应 —— 若有，这条测试就不再是反例了"
    assert "contradiction" not in sc.can_produce, "占位种类却声称能产生矛盾"

    assert derived_can_produce(set()) == ("consensus", "omission", "refinement"), \
        "空边集的视图不该声称能产生竞争解释或矛盾"


def test_spec_only_kinds_are_never_used_at_the_frontier():
    """合成语料与 adapter **只用 arena 产品代码真的会创建的种类**。

    这条是核心更正：原先语料用 `refines` / `related_to`（产品从不产生），
    等于在一个上游不存在的形态上验证 DCE。
    """
    from core import edge as E
    from checks import boundary
    ok, detail = boundary.check_no_scaffold_at_frontier()
    assert ok, detail
    assert "refines" in E.SPEC_ONLY_KINDS and "related_to" in E.SPEC_ONLY_KINDS
    assert not E.is_product_kind("refines") and E.is_product_kind("supports")
    assert E.SCAFFOLD_UNTYPED in E.DCE_DECLARED_KINDS, \
        "占位种类必须是**本层声明的**，不能借用上游的某个词"


def test_frontmatter_parser_handles_real_shape():
    """极简 frontmatter 解析器要能吃下真实节点的四种 YAML 形状。

    ⚠️ 这条**不需要语料库**，所以它永远会跑 —— 语料不在时，
    「解析器对真实形状有效」这件事仍然可测。
    """
    from adapters import scaffold as SC
    text = (
        "---\n"
        'id: "arg-0001"\n'
        "type: 论据\n"
        'title: "增量消融"\n'
        'aliases: ["ablation", "消融链"]\n'
        "cues:\n"
        '  - "第一句"\n'
        '  - "第二句"\n'
        'scope: "适用范围"\n'
        "source:\n"
        '  ref: "arXiv:2503.14476（DAPO）§4"\n'
        "  kind: 论文\n"
        "evidence_status: 未验证\n"
        'relations: ["stance-0001"]\n'
        "filled_by: 模型(DeepSeek-V4.1-Flash)\n"
        'notes: "备注"\n'
        "---\n正文\n"
    )
    fm = SC.parse_frontmatter(text)
    assert fm["id"] == "arg-0001"
    assert fm["type"] == "论据"
    assert fm["aliases"] == ["ablation", "消融链"]
    assert fm["cues"] == ["第一句", "第二句"], fm["cues"]
    assert fm["source"] == {"ref": "arXiv:2503.14476（DAPO）§4", "kind": "论文"}
    assert fm["relations"] == ["stance-0001"]
    assert SC.parse_frontmatter("没有 frontmatter") == {}


def test_scaffold_source_kind_is_a_different_axis():
    """**同名不同义**：Scaffold 的 `source.kind`（节点级体裁，中文）
    与 DCE 的 `source.kind`（视图级产出者，英文）不是一个轴。

    硬做一张翻译表会把「体裁」伪装成「产出者」，所以 adapter 只把它当**切分键**。
    """
    from adapters import scaffold as SC
    from core import view as V
    a = SC.to_view("SC", [{"id": "con-0001", "relations": [],
                           "source": {"ref": "x", "kind": "论文"}}])
    assert a.view["source"]["kind"] == "scaffold", \
        "视频的 source.kind 必须是产出者语义，不是节点的体裁"
    assert a.view["source"]["kind"] in V.SOURCE_KINDS
    joined = " ".join(a.declares)
    assert "同名不同义" in joined or "不是一个轴" in joined or "不做翻译" in joined, \
        "同名不同义这件事必须被显式声明出来"


def test_split_views_by_source_kind():
    """按体裁切视图。切分键只用于**切分**，不进任何字段。"""
    from adapters import scaffold as SC
    nodes = [{"id": "con-0001", "relations": [], "source": {"kind": "论文"}},
             {"id": "con-0002", "relations": ["con-0001"],
              "source": {"kind": "教材"}},
             {"id": "arg-0001", "relations": [], "source": {"kind": "教材"}}]
    adaps = SC.split_views(nodes, split_by="source.kind")
    assert len(adaps) == 2, f"该切出 2 个视图，实测 {len(adaps)}"
    sizes = {a.view["id"]: len(a.view["nodes"]) for a in adaps}
    assert sum(sizes.values()) == 3, f"节点不该在切分中丢失：{sizes}"
    from core import view as V
    V.check_distinct([a.view for a in adaps])


def test_realdata_skip_state_is_explicit():
    """语料不在时返回的必须是**显式的跳过**，而不是静默通过。

    ⚠️ 这条钉的是「跳过不等于通过」。一个「语料不在就算过」的检查，
    与一条永远通过的检查，在输出上长得一样。

    语料在本机会存在，所以要**强制**制造缺席 —— 用环境变量指向一个不存在的路径，
    而不是假设它不在（第一版就是那么假设的，于是在有语料时红得没有意义）。
    """
    import os
    from checks import realdata as RD

    r = RD.run_real(directory="C:/__这个目录不存在__")
    assert r.get("skipped") is True, f"不存在的目录竟然没被标成跳过：{r}"
    assert "why" in r, "跳过必须带理由"

    old = os.environ.get("DCE_SCAFFOLD_CORPUS")
    os.environ["DCE_SCAFFOLD_CORPUS"] = "C:/__这个目录不存在__"
    try:
        outs = RD.run_all()
    finally:
        if old is None:
            os.environ.pop("DCE_SCAFFOLD_CORPUS", None)
        else:
            os.environ["DCE_SCAFFOLD_CORPUS"] = old
    assert outs, "run_all 不该返回空"
    assert outs[0][1] is None, \
        "跳过态必须用 None 表示（True/False 都会混进「过」或「红」的计数）"


def test_realdata_on_the_real_corpus():
    """有真实语料就真跑；没有就跳过（并显式说明）。"""
    from checks import realdata as RD
    r = RD.run_real()
    if r.get("skipped"):
        print(f"    [跳过] {r['why']} —— 跳过不等于通过")
        return
    assert r["nodes"] > 0 and r["dangling"] == 0
    assert r["views"] >= 2, f"切不出多视图：{r['view_sizes']}"
    # 这份语料是一个知识库的**切面**，不是多份立场 —— 交集为 0
    assert r["intersection"] == 0
    assert r["consensus"] == 0
    # 无种类的关系 → 一条矛盾都不可能有
    assert r["types"].get("contradiction", 0) == 0
    # 真实规模下 flat 口径不可用：合成比输入大
    assert r["compression"]["flat"] < 1.0
    assert r["compression"]["focused"] > 1.0, "焦点概括该把它收回来"


def test_arena_disagreement_gap_is_measured_not_hidden():
    """**接口错位**：Arena 的两方对立形状在 DCE 的矛盾判据下报不出来。

    这条测试的价值在于把错位**固定成一个已知量**，而不是让它
    在别处以「DCE 漏报」的形式出现。现在它报 0 —— 那就是事实。
    哪一天有人改了 DCE 的判据或让 adapter 去 reify，这个数字会变，
    而那正是需要被看见的时刻。
    """
    from checks import boundary
    n, detail = boundary.measure_arena_disagreement_gap()
    assert n == 0, (f"错位测量变了（{n} 条矛盾）：{detail}\n"
                    "若这是有意改的，请一并更新这条测试与 DECLARATION 里的记录")


def test_positions_material_matches_criteria():
    """按 `CRITERIA.md` 造的三份立场，必须**按判据**分类。

    ⚠️ 这条测的**不是**「算法对不对」，而是「材料与判据是否一致」。
    不一致时改的是**材料**（`generators/positions.py`），不改判据 ——
    反过来做就是「试到好看为止」，正是 §T0.3 要防的。
    """
    from checks import positions as P
    for title, ok, detail in P.run_all():
        assert ok, f"{title} 红了：{detail}"


def test_positions_produce_all_four_types_naturally():
    """四类差异必须由**立场之间的真实差别**自然产生，
    而不是像上一轮那样把四类分别种在四个专用视图上。

    上一轮那套构造被自己的反例扫描证伪了：144 个配置只有 54 个建得出来，
    而 54/54 都是「四类各占专用视图」的干净情形。
    """
    from checks import positions as P
    r = P.analyse_positions()
    got = r["got"]
    for t in ("contradiction", "alternative", "refinement", "omission"):
        assert got[t], f"{t} 没有自然出现"
    # 立场之间必须既有共享（→ 共识）又有差别（→ 分歧）
    assert len(r["consensus"]) > 0, "三份立场没有共享结构，那就不是「同一议题上的立场」"
    # 而且不能是「一份包含另一份」的退化解
    units = [__import__("analysis.consensus", fromlist=["x"]).units_of(v)
             for v in r["views"]]
    assert not (units[0] == units[1]), "两份立场完全相同，测不到分歧"


def test_focus_collapses_on_a_shared_node_space():
    """**§十一 与 §七 的前提冲突**，钉住它。

    焦点用「共享节点」并查集 = **传递闭包**；而 §七 的前提正是
    「视图已映射到共享节点空间」。于是**让分歧可算的那个前提，同时让焦点恒等于 1**。

    真实语料上一轮量出的 9 个焦点，是**按体裁切片**（几近不相交）造出来的，
    不是立场造出来的 —— 那是材料形状的产物，不是机制的功劳。

    推论：`focused` 压缩比在焦点为 1 时是**假压缩**（= 共识 + 1），
    它只说明「全都是一团」，不是概括出了结构。
    """
    from checks import positions as P
    r = P.analyse_positions()
    n_foci = len(r["syn"]["foci"])
    assert n_foci == 1, f"焦点数变了（{n_foci}）—— 若这是有意改的，请更新本条与 DECLARATION"
    from metrics import compression as CMP
    base = len(r["syn"]["consensus"]["records"]) + n_foci
    k = CMP.compression(r["views"], r["syn"])["all_modes"]
    assert abs(k["focused"] - CMP.input_size(r["views"]) / base) < 1e-9, \
        "focused 压缩比的算式变了 —— 它现在应当等于「共识 + 1 个焦点」"


def test_positions_are_labelled_as_authored():
    """材料是**自己造的**，不许被当成从论文抽取的引用。

    节点 id 与标题取自真实语料当词汇表，但**立场结构是本层设计的** ——
    把它们当成「论文说了什么」会是伪造引用。
    """
    from generators import positions as POS
    views, _intent = POS.build()
    for v in views:
        assert v["source"]["ref"].startswith("authored://"), \
            f"{v['id']} 的来源标记不是 authored://（{v['source']['ref']}）"
        assert v["metadata"].get("authored") is True
    # 词汇表必须真的来自真实语料，且用到的节点都在表里
    assert "judge-0003" in POS.VOCAB and "con-0005" in POS.VOCAB
    for v in views:
        for n in v["nodes"]:
            assert n in POS.VOCAB, f"{n} 不在词汇表里"


def test_radius_calibration_assertions_pass():
    """半径：显式参数，上界由结构算出。§T0.3 禁的是**断言一个具体阈值**，
    不是禁「有一个显式参数」—— 区别在值由谁定。"""
    from checks import radius
    for title, ok, detail in radius.run_all():
        assert ok, f"{title} 红了：{detail}"


def test_radius_zero_is_backward_compatible():
    """`radius=0` 必须与旧签名结果一致 —— 加参数不许改变既有行为。"""
    from generators import positions as POS
    from analysis import divergence as D
    from analysis import focus as F
    views, _ = POS.build()
    d = D.analyse(views)
    assert len(F.foci(d)) == len(F.foci(d, radius=0, views=views))


def test_radius_requires_structure_graph():
    """`radius>0` 必须给结构图。不给就报错 —— 因为**猜一个距离**
    正是 §T0.3 要防的。"""
    from generators import positions as POS
    from analysis import divergence as D
    from analysis import focus as F
    views, _ = POS.build()
    d = D.analyse(views)
    try:
        F.foci(d, radius=2)
    except ValueError as e:
        assert "结构图" in str(e)
        return
    raise AssertionError("radius>0 不传 views 竟然没报错")


def test_radius_semantics_is_exact_distance():
    """**距离语义必须是精确的**：并簇当且仅当锚点集距离 ≤ radius。

    ⚠️ 这条是抓 bug 的。第一版算的是「两边的半径球相交」，而两个半径 k 的球
    相交等价于 `dist ≤ 2k` —— **生效阈值是半径的两倍**。它不报错，
    只让曲线在比预期早一半的地方塌下去。

    构造：10 节点链，两簇分歧的锚点最近距离正好 5。
    于是 `r*` 必须是 **5**（不是 2 或 3）。
    """
    from core import view as V
    from analysis import divergence as D
    from analysis import focus as F

    nodes = [f"con-{i:04d}" for i in range(1, 11)]
    chain = [(nodes[i], nodes[i + 1], "contains") for i in range(len(nodes) - 1)]

    def mv(vid, edges):
        return V.make_view(view_id=vid, source_ref=f"authored://r/{vid}",
                           source_kind="experiment", nodes=nodes, edges=edges)

    whole = mv("L", chain)
    a = mv("A", [e for e in chain if e not in chain[:2]])
    b = mv("B", [e for e in chain if e not in chain[-2:]])
    d = D.analyse([whole, a, b])

    # 两簇锚点：{1,2,3} 与 {8,9,10}，最近距离 3→8 = 5
    assert len(F.foci(d, radius=0, views=[whole, a, b])) == 2, "radius=0 该给 2 个焦点"
    assert len(F.foci(d, radius=4, views=[whole, a, b])) == 2, "radius=4 还不该并上"
    assert len(F.foci(d, radius=5, views=[whole, a, b])) == 1, "radius=5 必须并上"
    cal = F.calibrate(d, [whole, a, b])
    assert cal["r_star"] == 5, f"r* 应为精确距离 5，实测 {cal['r_star']}（语义差一倍？）"
    assert cal["usable_max"] == 4


def test_calibrate_reports_the_whole_curve():
    """校准必须报**整条曲线**与理由，不能只给一个数 —— 只给一个数就回到了「拍阈值」。"""
    from generators import positions as POS
    from analysis import divergence as D
    from analysis import focus as F
    views, _ = POS.build()
    cal = F.calibrate(D.analyse(views), views)
    assert cal["curve"], "曲线不能为空"
    assert set(cal) >= {"curve", "r_star", "usable_max", "suggested", "note"}
    assert cal["note"], "必须给理由"


def test_beta_assertions_pass():
    """β 分解的全部检查，含**精确有理数穷尽验证**的定理。"""
    from checks import beta
    for title, ok, detail in beta.run_all():
        assert ok, f"{title} 红了：{detail}"


def test_beta_four_types_collapse_to_two_axes():
    """四类互斥标签 → **两个分量 + 方向**。这是借生态学要解开的那个毛病。

    DCE 原先必须决定「这个单元算 refinement 还是 omission」，而那个决定
    随构造移动（strict 召回量到 15/115）。β 分解不问「是哪一种」，
    只问「这一对视图之间，差异里多少是替换、多少是嵌套」。
    """
    from analysis import beta as B
    cases = [
        ({"u1"}, {"u1"}, 0.0, 0.0, "consensus"),
        ({"u1"}, {"u1", "u2"}, None, None, "nestedness"),
        ({"u1", "u2", "u3"}, {"u1"}, None, None, "nestedness"),
        ({"u1", "u2"}, {"u3", "u4"}, None, None, "turnover"),
    ]
    for ua, ub, want_total, want_nest, want_axis in cases:
        p = B.pairwise(ua, ub)
        assert p["axis"] == want_axis, f"{ua}/{ub} 轴错了：{p}"
        if want_total is not None:
            assert p["total"] == want_total and p["nestedness"] == want_nest
    # replacement（子集）与 omission（超集）是**同一个现象的两个方向**
    sub = B.pairwise({"u1", "u2"}, {"u1", "u2", "u3"})
    sup = B.pairwise({"u1", "u2", "u3"}, {"u1", "u2"})
    assert sub["turnover"] == 0.0 and sup["turnover"] == 0.0, "子集关系该是纯嵌套"
    assert sub["nestedness"] == sup["nestedness"], "嵌套量该对称"
    assert sub["direction"] != sup["direction"], "方向该相反"


def test_beta_theorem_is_exhaustive_not_sampled():
    """**定理是穷尽验证的，不是抽样的。** 而且退化情形单列。

    ⚠️ 等价式的右半边改过一次：第一版写「a=0 或 b=c」，穷尽验证报出 40 组反例，
    全是 `a=0 且 min(b,c)=0`（**其中一个视图是空的**）。
    那时 β_嵌套 = 1，而**那是对的** —— 空集是任何集合的子集。
    错的是定理陈述，不是代码。
    """
    from checks import beta
    outs = {t: (ok, d) for t, ok, d in beta.run_all()}
    for key in outs:
        if key.startswith("定理：β_嵌套 ≥ 0"):
            assert outs[key][0], outs[key][1]
            assert "9261" in key, f"定理该在 9261 组上穷尽验证，实测：{key}"
        if key.startswith("退化情形"):
            assert outs[key][0], outs[key][1]


def test_beta_multi_reduces_to_pairwise():
    """多地点版本是本层补的（手册只给了名字与结构，没给公式），
    所以**N=2 时必须逐位等于成对版本** —— 那是「推广没跑偏」的最低要求。"""
    from analysis import beta as B
    for fam in B.FAMILIES:
        for ua, ub in (({"u1", "u2"}, {"u2", "u3"}),
                       ({"u1"}, {"u1", "u2", "u3"}),
                       ({"u1", "u2", "u3"}, {"u4"})):
            p = B.pairwise(ua, ub, family=fam)
            m = B.multi([ua, ub], family=fam)
            for k in ("total", "turnover", "nestedness"):
                assert abs(p[k] - m[k]) < 1e-15, f"{fam}/{k}: {p[k]} vs {m[k]}"


def test_beta_declares_what_was_not_verified():
    """⚠️ **「读了正文」与「只有检索片段」必须分开标注。**

    `betapart` 的手册确认了两个指数族与六个分量名，**但没给公式**。
    所以 Sorensen 族的三式是核过的，**Jaccard 族的变换是本层补的重建**。
    这条测试钉住那处声明 —— 把它删掉就等于宣称全部核过，那是假的。
    """
    import pathlib
    src = pathlib.Path(__file__).resolve().parent.parent / "analysis" / "beta.py"
    text = src.read_text(encoding="utf-8")
    assert "本层补的" in text and "没有对着正文核过" in text, \
        "beta.py 必须声明哪一步是未核正文的重建"
    from analysis import beta as B
    assert B.SORENSEN in B.FAMILIES and B.JACCARD in B.FAMILIES


def test_approximation_assertions_pass():
    """粗糙集那条：正域 / 依赖度 / 约简，以及**验证等价式本身**。"""
    from checks import approximation
    for title, ok, detail in approximation.run_all():
        assert ok, f"{title} 红了：{detail}"


def test_gamma_one_iff_typing_is_a_function_of_signature():
    """**γ = 1 ⟺ 类型判定完全由「出现在哪几个视图」决定。**

    这不是比喻，是正域定义的推论 —— 但推论也要验。这条在几十个配置上
    逐一对照「γ==1」与「没有签名类横跨两个决策类」，必须同真同假。

    它是 §十六 那个问题（「DCE 是否只是 graph frequency bookkeeping？」）
    的**精确定量形式**：1 − γ 就是「类型超出了频率记账」的那部分。
    """
    from metrics import approximation as A
    from checks.approximation import _cfg
    n = 0
    for nv in (2, 3, 4, 5):
        for plant in ({}, {"omissions": 2}, {"contradictions": 2},
                      {"contradictions": 2, "omissions": 2, "refinements": 1}):
            for seed in (11, 13):
                try:
                    views, _t = _cfg(nv, plant, seed)
                except ValueError:
                    continue
                n += 1
                a = A.approximations(views)
                typ = A.typing(views)
                g = len(a["positive"]) / len(a["units"])
                spans = any(len({typ[u] for u in m}) > 1
                            for m in a["classes"].values())
                assert (abs(g - 1.0) < 1e-12) == (not spans), \
                    f"等价式在 {nv}/{plant}/{seed} 上不成立：γ={g}, spans={spans}"
    assert n >= 20, f"只对照了 {n} 个配置，太少"


def test_alpha_and_gamma_are_different_quantities():
    """**α 与 γ 不是一个量**，两者都要报，取舍留在判据层。

    ⚠️ 这一条是核查正文时更正过的：我原先把 α 的形状挂了 γ 的名字。
        α = |下近似| / |上近似|   （紧不紧）
        γ = |正域|   / |全体|     （覆盖多少）
    """
    from metrics import approximation as A
    from checks.approximation import _cfg
    views, _t = _cfg(5, {"contradictions": 2, "omissions": 2, "refinements": 1}, 21)
    g = A.gamma(views)["gamma"]
    a = A.alpha(views)["alpha"]
    assert g is not None and a is not None
    assert abs(g - a) > 1e-9, \
        f"α 与 γ 相等（都是 {g}）—— 那说明我把它们算成了同一个东西"
    # γ 的分母是全体单元，α 是各决策类上下近似之比 —— 分母不同
    assert 0.0 <= g <= 1.0 and 0.0 <= a <= 1.0


def test_reducts_exclude_single_view_subsets():
    """约简**从 k=2 起算**，不查单视图子集 —— 那是有意的。

    一个视图没有「之间」：它的全部单元按定义都是共识，只有一个签名类、
    一个决策类，**γ 恒等于 1**。那是退化，不是有信息的结果。
    若把 k=1 放进候选，「最小约简」永远是一个视图，而那个答案什么都没说。
    """
    from metrics import approximation as A
    from checks.approximation import _cfg
    views, _t = _cfg(5, {"omissions": 2}, 31)
    r = A.reducts(views)
    assert not r["refused"], r
    assert r["reducts"], "至少全体视图本身应当是一个约简"
    assert all(len(x) >= 2 for x in r["reducts"]), \
        f"出现了单视图约简：{r['reducts']}"
    assert "单视图子集被有意排除" in r["note"]
    # 而且约简真的保持 γ
    for red in r["reducts"]:
        sub = [v for v in views if v["id"] in red]
        assert abs(A.gamma(sub)["gamma"] - r["gamma"]) < 1e-12


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
