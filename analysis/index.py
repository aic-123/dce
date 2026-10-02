"""第二步的产物：**面合取 → 差异记录集合**（纯集合结构，**不含相似**）。

---
判据决定（2026-10-01，由用户裁定）
--------------------------------

    **相似现在不出现。DCE 不做匹配 —— 那是检索系统的事。**

这条裁定把设计里最大的一个风险直接消掉了。理由是：

    DCE 到目前为止**全程是纯集合论的** —— 共识是交、分歧是分类，
    「相似」这个量从头到尾没出现过。
    而「匹配一段处境」必然要引入相似 ⇒ **那是本层第一次引入相似**，
    也就是第一次引入「像不像」这种既可打分又可排行的东西。

⇒ 所以本层的产物是**索引**（键 → 记录集），而**不是匹配器**：

    本层产出       键（一个**面合取**，值是**精确值**） → 命中的差异记录集合
    本层不做       把一段处境**映射**到那些值 —— 那是检索系统的相似度问题
    本层不做       排序、打分、阈值、模糊 —— 一条都没有

⚠️ **键是精确值，不是"像"。** 若检索系统要把「reward 不涨了」映射到
`judge-0003 回答长度增长`，那是**它的**相似度判断，**与本层无关**，也不进本层产物。

---
于是「证明检索能依靠它」就变成四条**可证伪**的性质
------------------------------------------------

    ① **覆盖**    每条差异记录至少落在一个键下（否则检索永远够不到它）
    ② **不塌**    没有任何一个键覆盖「几乎全部」记录（否则键没有区分力）
    ③ **可枚举**  键数是记录数的量级，不是指数
    ④ **确定性**  同一输入给同一索引；输入逆序不改结果

⚠️ 这四条**全都不需要相似**，所以它们可以在本层被证明。
而它们也是 ①/③ 两条在 `RETRIEVAL.md` §四 里早就写下的证伪判据。
"""

from __future__ import annotations


def facets_of(record, views) -> list:
    """一条差异记录的全部「面=值」。

    **结构面**：`类型 / 单元 / 关系 / 角色 / 视图`（已实现，见 `analysis/concepts.py`）。
    **内容面**：锚点的可读标签（`view["metadata"]["labels"]`），
    它**只有适配器显式开了 `keep_labels` 才有** —— 没有它，处境映射不到任何东西。
    """
    from analysis import concepts as K
    from analysis import focus as F
    out = [(f"结构:{a}", a) for a in K.features(record, views)]
    lab = {}
    for v in views:
        lab.update((v.get("metadata") or {}).get("labels", {}))
    for a in F.anchors(record):
        if a in lab:
            out.append(("内容:标签", lab[a]))
    return sorted(set(out))


def build(views) -> dict:
    """建索引：`键 → 命中的记录下标`。**入参不变。**

    ⚠️ 键是 `frozenset(面=值)`，所以要能哈希；记录以**下标**入索引，
    拿出来仍要回到 `records` 里取（避免复制产生"看起来一样的两份"）。
    """
    from analysis import divergence as D
    from analysis import focus as F
    recs = F._all_records(D.analyse(views))
    keys: dict = {}
    per_record = []
    for i, r in enumerate(recs):
        fs = facets_of(r, views)
        per_record.append(frozenset(fs))
        for f in fs:
            keys.setdefault(f, []).append(i)
    return {"records": recs, "per_record": per_record, "keys": keys}


def stats(idx: dict, total_records: int = None) -> dict:
    """四条性质的度量。`collapse` 用**结构判据**：最大键是否覆盖了全部记录。"""
    keys, n = idx["keys"], len(idx["records"])
    sizes = sorted((len(v) for v in keys.values()), reverse=True)
    covered = set()
    for v in keys.values():
        covered.update(v)
    return {
        "n_records": n,
        "n_keys": len(keys),
        "n_covered": len(covered),
        "coverage": (len(covered) / n) if n else None,
        "max_key": sizes[0] if sizes else 0,
        "median_key": sizes[len(sizes) // 2] if sizes else 0,
        # 结构判据，不是阈值：**一个键就覆盖了全部记录** ⟺ 它没有区分力
        "collapse": bool(sizes) and sizes[0] == n,
        # 「可枚举」的判据同样是结构性的：**键数 ≤ 记录数**（每条记录贡献的键有限）
        "enumerable": len(keys) <= max(1, n) * 8,
    }


def by_kind(idx: dict) -> dict:
    """结构面键与内容面键分开报 —— 它们的用途不同。"""
    out = {"结构": {}, "内容": {}}
    for k, v in idx["keys"].items():
        facet = k[0].split(":")[0]
        out.setdefault(facet, {})[k] = v
    return out
