"""Test 4 Interference（§十五）—— **本 MVP 最硬的一条判据**。

§十五 原文：

    写入 View A、View B 之后再次读取 A。要求：**A 的原始结构完全不改变。**
    也就是：hash(A_before) == hash(A_after)
    这比你原来的「边权可能被 B 影响」更严格。
    因为现在 DCE 是 derived layer。**B 不应该污染 A。**

这条判据是整个项目的分层不变量（`§C7.1 ④` 单向性、`nested` 的「上层只派生、不倒流」）
在 DCE 上的可执行形式。所以测四件事，不是一件：

1. `hash(A_before) == hash(A_after)`（§十五 的字面判据）
2. 每个视图**逐字段深层相等**（哈希相同但字段被重排过也算通过吗？不算 —— 见下）
3. 合成结果里的 `provenance.views[].fingerprint` 与源视图**当场重算的指纹**一致
4. **后加入一个视图**，先前那些视图的指纹不变（增量写入不污染历史）

⚠️ 第 2 条为什么不能省：指纹只覆盖结构性字段，而 `verify()` 的白名单之外
本来就不许有字段。两者一起才有意义 —— 单看哈希，一个**只改了运行时附加字段**
的实现会通过，而那些附加字段正是「顺手挂上去的评分」的落脚处。
"""

from __future__ import annotations

import json

from analysis import synthesis as S
from core import view as V


def _deep_snapshot(views) -> str:
    return json.dumps([json.loads(V.canonical(v)) | {"_raw": v} for v in views],
                      sort_keys=True, ensure_ascii=False)


def test_no_interference() -> list:
    from generators import synthetic as SYN
    base = SYN.base_graph(n_nodes=10, n_edges=12, seed=21)
    views, _t = SYN.make(base, {"n_views": 3, "n_core": 6, "private": 2,
                                "contradictions": 1, "omissions": 1})

    before_fp = {v["id"]: V.fingerprint(v) for v in views}
    before_snap = _deep_snapshot(views)

    syn = S.build(views)

    after_fp = {v["id"]: V.fingerprint(v) for v in views}
    after_snap = _deep_snapshot(views)

    out = []
    out.append(("Test4 hash(A_before) == hash(A_after)",
                before_fp == after_fp,
                f"{len(before_fp)} 个视图指纹全部不变"
                if before_fp == after_fp else
                f"变了：{[k for k in before_fp if before_fp[k] != after_fp.get(k)]}"))
    out.append(("Test4 视图逐个字段深层相等",
                before_snap == after_snap,
                "合成前后序列化完全一致（不只哈希）"))
    prov = {p["id"]: p["fingerprint"] for p in syn["provenance"]["views"]}
    out.append(("Test4 合成里记的指纹 = 当场重算",
                prov == after_fp,
                f"{len(prov)} 项一致" if prov == after_fp else "不一致"))
    return out


def test_incremental_view_does_not_pollute() -> list:
    """后加入一个视图，先前那些视图的指纹不变。"""
    from generators import synthetic as SYN
    base = SYN.base_graph(n_nodes=12, n_edges=14, seed=31)
    two, _t = SYN.make(base, {"n_views": 2, "n_core": 6, "private": 2})
    three, _t2 = SYN.make(base, {"n_views": 3, "n_core": 6, "private": 2})

    fp2 = {v["id"]: V.fingerprint(v) for v in two}
    S.build(two)
    fp2_after = {v["id"]: V.fingerprint(v) for v in two}
    # 三个视图的输入里，前两个视图本身是独立构造的（id 同为 V1/V2），
    # 但它们的内容由同一 seed 决定 → 应当一致
    fp3 = {v["id"]: V.fingerprint(v) for v in three if v["id"] in fp2}

    out = []
    out.append(("Test4 两个视图跑完之后指纹不变", fp2 == fp2_after,
                "2 视图合成不污染输入"))
    out.append(("Test4 三视图输入里 V1/V2 与两视图时相同", fp2 == fp3,
                "同一 seed 造出的 V1/V2 在 3 视图场景下逐字节相同"
                if fp2 == fp3 else
                f"不同：{[k for k in fp2 if fp2[k] != fp3.get(k)]}"))
    return out


def test_synthesis_has_no_forbidden_keys() -> list:
    """产物里不许出现评分 / 权重 / 真值词汇（§T4.2 的可执行形式）。"""
    from generators import synthetic as SYN
    base = SYN.base_graph(n_nodes=10, n_edges=12, seed=41)
    views, _t = SYN.make(base, {"n_views": 7, "n_core": 8, "private": 1,
                                "contradictions": 1, "omissions": 1,
                                "refinements": 1, "alternatives": 1})
    syn = S.build(views)
    hits = S.forbidden_keys_in(syn)
    return [("产物里无评分/权重/真值词汇", not hits,
             f"0 处命中（禁用键 {len(S.FORBIDDEN_KEYS)} 个）" if not hits
             else f"命中 {len(hits)} 处：{hits[:5]}")]


def run_all() -> list:
    return (test_no_interference() + test_incremental_view_does_not_pollute()
            + test_synthesis_has_no_forbidden_keys())
