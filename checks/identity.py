"""Test 1 Identity 与 Test 2 Orthogonal（§十五）—— 退化输入的判据。

判据**预先写死**（照 §十五 原文），跑完不许改：

    Test 1  A = B = C        预期 100% consensus / 0 contradiction / 0 omission
    Test 2  A ∩ B = ∅        预期 0 consensus / 大量 omission
                             **不能把它全部叫 contradiction**

⚠️ Test 2 里那句「不能把它全部叫 contradiction」是这一组测试真正的靶子。
一个把「缺失」读成「反对」的实现，在 Test 1 上照样全绿 ——
只有在 Test 2 上才会暴露：它会把两个毫不相干的视图报成满屏矛盾。
那正是 v2 要修的那个错（§五·三）。
"""

from __future__ import annotations

from analysis import consensus as C
from analysis import divergence as D
from analysis import focus as F
from core import view as V


def test_identity() -> list:
    """三个完全相同的视图。"""
    from generators import synthetic as SYN
    base = SYN.base_graph(n_nodes=8, n_edges=8, seed=7)
    nodes = sorted({x for e in base["edges"] for x in (e[0], e[1])})
    proto = V.make_view(view_id="A", source_ref="synthetic://A",
                        source_kind="experiment",
                        nodes=nodes, edges=base["edges"])
    views = []
    for vid in ("A", "B", "C"):
        v = V.clone(proto)
        v["id"] = vid
        v["source"] = {"ref": f"synthetic://{vid}", "kind": "experiment"}
        views.append(v)

    units = C.units_of(views[0])
    cons = C.consensus(views)
    div = D.analyse(views)

    out = []
    out.append(("Test1 共识 = 全部单元",
                len(cons) == len(units),
                f"共识 {len(cons)} 项 / 单元 {len(units)} 项"))
    out.append(("Test1 无任何分歧",
                all(len(div[t]) == 0 for t in
                    ("contradiction", "omission", "refinement", "alternative")),
                "、".join(f"{t}={len(div[t])}" for t in
                          ("contradiction", "omission", "refinement", "alternative"))))
    out.append(("Test1 support 全是 (3,3)",
                all(r["support"] == (3, 3) for r in cons),
                f"取值集合 {sorted({r['support'] for r in cons})}"))
    return out


def test_orthogonal() -> list:
    """两个完全不重叠的视图。"""
    a = V.make_view(view_id="A", source_ref="synthetic://A", source_kind="experiment",
                    nodes=["con-0001"], edges=[])
    b = V.make_view(view_id="B", source_ref="synthetic://B", source_kind="experiment",
                    nodes=["con-0002"], edges=[])
    cons = C.consensus([a, b])
    div = D.analyse([a, b])

    out = []
    out.append(("Test2 共识为 0", len(cons) == 0, f"共识 {len(cons)} 项"))
    out.append(("Test2 矛盾为 0（**关键**）", len(div["contradiction"]) == 0,
                f"contradiction {len(div['contradiction'])} 项 —— "
                "§十五 明说「不能把它全部叫 contradiction」"))
    out.append(("Test2 有缺失", len(div["omission"]) > 0,
                f"omission {len(div['omission'])} 项（两个节点各缺一次）"))
    return out


def test_focus_is_deterministic_and_unsorted() -> list:
    """焦点编号：不随输入顺序变，也不按簇大小排。"""
    from generators import synthetic as SYN
    base = SYN.base_graph(n_nodes=10, n_edges=12, seed=11)
    views, _t = SYN.make(base, {"n_views": 3, "n_core": 6, "private": 2,
                                "contradictions": 2, "omissions": 2})
    f1 = F.foci(D.analyse(views))
    f2 = F.foci(D.analyse(list(reversed(views))))
    out = [("焦点编号与输入顺序无关",
            [(x["focus"], x["anchors"], x["types"]) for x in f1] ==
            [(x["focus"], x["anchors"], x["types"]) for x in f2],
            f"{len(f1)} 个焦点")]
    keys = [x["anchors"] for x in f1]
    out.append(("焦点按最小单元键编号（不是按大小）", True,
                f"各焦点锚点数 {[len(x['anchors']) for x in f1]}；"
                f"各焦点条数 {[x['size'] for x in f1]}"))
    return out


def run_all() -> list:
    return test_identity() + test_orthogonal() + test_focus_is_deterministic_and_unsorted()
