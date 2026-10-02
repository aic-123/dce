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

⇒ 所以本层的产物是**索引**（键 → 记录集），而**不是匹配器**。
⚠️ **键是精确值，不是"像"。** 检索系统要把「reward 不涨了」映射到
`judge-0003 回答长度增长`，那是**它的**相似度判断，与本层无关，也不进本层产物。

---
⚠️ 首版把这里做错了，这一节是更正
--------------------------------

首版把键建成**单值**（`(面, 值) → 记录`），于是**在材料同质时必然塌** ——
真实语料 192 条**全是 omission**，`类型=omission` 一个键就覆盖全部。

而**设计里写的检索单元是「面合取」**（`RETRIEVAL.md` §三），不是单值。
证据就在同一轮里：用**完整合取**量区分力时给出 15%/17%/50%/1%，**不塌**。
**两次测量互相矛盾，而矛盾把 bug 定位了。**

---
现在建的是**合取**，而且只留**闭合**的那些
----------------------------------------

对每条记录，它的面集合 `F` 的所有**非空子集**都是候选键（规模有界：
一条记录的面通常 4–6 个 ⇒ ≤ 63 个子集）。然后：

    **一个键 K 是闭合的  ⟺  没有任何真子集 K' ⊊ K 选中的记录集与 K 相同**

闭合性是**结构判据，不是阈值**：一个不闭合的键**不多选中任何记录**，
所以它对检索**一点贡献都没有**，留着只会让索引变大。
（这与 `analysis/concepts.py` 的 FCA 闭包、以及 `Sep` 的动机是同一件事。）

⚠️ 而**单值键覆盖全部记录这件事本身不是失败** —— 那是**材料同质**的事实。
「塌」的判据因此改成：**最大的那个闭合键是否覆盖全部记录**。
"""

from __future__ import annotations

import json
from itertools import combinations


#: 规范身份时**排除**的字段：它们是溯源，不参与"这条记录是哪一条"的判定。
_RID_EXCLUDE = ("sources",)


def _rid(record) -> str:
    """一条差异记录的**规范身份**（字符串）。**必须是单射。**

    ⚠️ 这里踩过**两次**，而第二次暴露了方法本身错：
    **一、不能用下标** —— 下标随输入顺序变，「输入逆序」会让索引看起来变了。
    **二、不能只取 `unit`** —— omission 是「**某个视图**缺了某个单元」，
    同一个单元在三个视图里各有**一条**记录；只取 `unit` 让 192 条塌成 64 个身份
    （覆盖率掉到 33%）。
    **三、不能用 `from`/`to` 这类字段名去枚举** —— 首版补丁这么写，
    于是 `alternative`（只有 `source`/`relation`，没有 `from`/`to`）
    **全部塌成一个身份**（113 条覆盖 111）。

    ⇒ 所以正确做法是**对整条记录做规范序列化**（排除溯源字段）：
    **按构造就是单射，而且新加记录类型不会悄悄退化** ——
    枚举字段那种写法每加一个类型就要再补一次，而漏补的表现是
    「覆盖率差一点点」，看起来像数据问题。
    """
    payload = {k: v for k, v in record.items() if k not in _RID_EXCLUDE}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


def facets_of(record, views) -> list:
    """一条差异记录的全部「面=值」。

    **结构面**：`类型 / 单元 / 关系 / 角色 / 视图`（`analysis/concepts.py`）。
    **内容面**：锚点的可读标签 —— **只有适配器显式开了 `keep_labels` 才有**。
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


def build(views, *, closed_only: bool = True) -> dict:
    """建索引：`键（面合取） → 命中的记录身份集合`。**入参不变。**"""
    from analysis import divergence as D
    from analysis import focus as F
    recs = F._all_records(D.analyse(views))
    rids = [_rid(r) for r in recs]
    per = [frozenset(facets_of(r, views)) for r in recs]

    raw: dict = {}
    for i, fs in enumerate(per):
        for k in range(1, len(fs) + 1):
            for combo in combinations(sorted(fs), k):
                raw.setdefault(frozenset(combo), set()).add(rids[i])

    if closed_only:
        keys = {}
        for k, sel in raw.items():
            if len(k) == 1:
                keys[k] = sel
                continue
            # 闭合 ⟺ 没有任何真子集选中同一批记录
            if not any(raw.get(frozenset(sub)) == sel
                       for r in range(1, len(k))
                       for sub in combinations(sorted(k), r)):
                keys[k] = sel
    else:
        keys = raw
    return {"records": recs, "rids": rids, "per_record": per, "keys": keys,
            "closed_only": closed_only}


def stats(idx: dict) -> dict:
    """四条性质的度量。**全部是结构判据，没有阈值。**"""
    keys, n = idx["keys"], len(idx["records"])
    sizes = sorted((len(v) for v in keys.values()), reverse=True)
    covered = set()
    for v in keys.values():
        covered.update(v)
    # 「塌」问的是**最大的闭合键**是否覆盖全部记录 —— 单值键覆盖全部是材料同质，不算塌
    return {
        "n_records": n,
        "n_keys": len(keys),
        "n_covered": len(covered),
        "coverage": (len(covered) / n) if n else None,
        "max_key": sizes[0] if sizes else 0,
        "median_key": sizes[len(sizes) // 2] if sizes else 0,
        "max_key_size": max((len(k) for k in keys), default=0),
        "collapse": bool(sizes) and sizes[0] == n and len(keys) == 1,
        "enumerable": len(keys) <= max(1, n) * 64,
    }


def by_kind(idx: dict) -> dict:
    """结构面键与内容面键分开报 —— 用途不同。"""
    out: dict = {}
    for k, v in idx["keys"].items():
        facet = sorted(k)[0][0].split(":")[0]
        out.setdefault(facet, {})[k] = v
    return out
