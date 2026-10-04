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


# ── 统计版闭合判据：**测增量，不测总支持度** ──────────────────────────
#
# ⚠️ 这一节是对闭合判据的修正，依据是**成熟领域**：
# **statistically sound pattern discovery / self-sufficient itemsets**（Webb）。
# （⚠️ 只拿到检索片段，**未核对正文**。见 `RETRIEVAL.md` 末尾。）
#
# 原先的「闭合」判据问的是「**有没有**收窄」，成熟做法问的是
# 「收窄**是否超出随机**」。差别不是修辞：
#
#     实测两次（同质的 Scaffold 语料、异质的 Perspectrum）都是
#     **面数≥2 的键 0 个显著**，而零分布紧得几乎没有余地 ——
#     因为**总支持度几乎由边际决定**，测它近乎空转。
#
# ⇒ 该测的是**从子集到超集那一步的收窄幅度**：
#
#     对键 K（面数≥2）取它**支持度最大的真子集** K'（最宽松的父），
#     令 f = K 减 K'，m = f 的总体支持度，s' = K' 的支持度，n = 记录数。
#     独立零假设下的期望 E = s' · m / n；观测 s = K 的支持度。
#     **s 显著小于 E ⟺ 这个面带来了超出随机的收窄。**
#
# ⚠️ 统计量用**超几何的正态近似**（均值 E、方差按超几何公式）。
# **这是近似，不是精确尾概率** —— 记在这里以免它被当成精确值引用。
# ⚠️ 多重检验校正用 **Holm**，否则一批键里总有几个「显著」。


def _norm_sf(z: float) -> float:
    """标准正态上尾 P(Z >= z)。只用标准库。"""
    import math
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def productivity(idx: dict, *, alpha: float = 0.05) -> dict:
    """每个面数≥2 的键的**收窄显著性**，Holm 校正。

    ⚠️ 这里的 p 是**判据**，不是排序键 —— 返回的 `rows` 按 p 升序只为
    Holm 的逐步过程，**不构成给用户看的排行**。
    """
    from itertools import combinations
    n = len(idx["records"])
    keys = idx["keys"]
    marg = {}
    for k, sel in keys.items():
        if len(k) == 1:
            marg[next(iter(k))] = len(sel)
    rows = []
    for k, sel in keys.items():
        if len(k) < 2:
            continue
        s = len(sel)
        best = None
        for r in range(len(k) - 1, 0, -1):
            for sub in combinations(sorted(k), r):
                ss = keys.get(frozenset(sub))
                if ss is not None and (best is None or len(ss) > best[1]):
                    best = (frozenset(sub), len(ss))
            if best is not None:
                break
        if best is None:
            continue
        parent, sp = best
        added = next(iter(set(k) - set(parent)))
        m = marg.get(added, 0)
        if sp == 0 or m == 0 or n <= 1:
            continue
        e = sp * m / n
        var = sp * (m / n) * (1 - m / n) * (n - sp) / (n - 1)
        if var <= 0:
            continue
        z = (s - e) / (var ** 0.5)
        rows.append({"key": sorted(k), "observed": s, "expected": e,
                     "narrowing": e - s, "z": z,
                     "p": _norm_sf(-z),          # 单侧：收窄才算
                     "parent": sorted(parent), "added": added})
    rows.sort(key=lambda r: r["p"])
    mt = len(rows)
    stopped = False
    for i, r in enumerate(rows):
        r["p_holm"] = min(1.0, r["p"] * (mt - i))
        if stopped or r["p_holm"] > alpha:
            r["significant"] = False
            stopped = True
        else:
            r["significant"] = True
    return {"tested": mt, "significant": sum(1 for r in rows if r["significant"]),
            "rows": rows, "alpha": alpha,
            "method": "超几何正态近似 + Holm（**近似，非精确尾概率**）"}


# ── 按正文重写：**最小依赖集**（correlation rules） ────────────────────
#
# ⚠️ 上面那个 `productivity()` 是**按错误的那一节**做的，这一节是对它的更正。
# 依据是正文（`arxiv.org/src/1709.03904` → `sspdtutarxiv.tex`）：
#
#     行 2268  Correlation rules are defined as **minimal** sets X, where X
#              expresses mutual dependence … **but all Y ⊊ X express mutual
#              independence**.        （Brin/Motwani/Silverstein）
#     行 2218  候选集的零假设是**所有属性之间的相互独立**
#     行 2174  一个集合表现依赖 ⟺ 它的**每个二分**都依赖
#     行 2237  对相互独立的零假设用**二项检验**
#
# ⇒ 三处与 `productivity()` 不同：
#
#     **零假设**   相互独立（不是"给定父的条件独立"）
#     **方向**     相互独立下期望支持度 = n·Π(m_i/n)（边际之**积**），
#                  **观测显著更低**才是依赖 —— 与"收窄"同向，但基准不同
#     **取舍**     只留**最小**的：它显著，而**所有真子集都不显著**
#
# ⚠️ 统计量：正文点名的是**二项检验**（行 2237）。这里用**二项的正态近似**
# （带连续性校正）—— n 最大约 1500、键数上千，精确尾在纯标准库下太慢。
# **这是近似，不是正文点名的那三种精确检验之一**，记在这里以免被当精确值引用。


def _binom_le(k: int, n: int, p: float) -> float:
    """`P(X <= k)`，`X ~ Binomial(n, p)` 的**正态近似**（带连续性校正）。"""
    import math
    if n <= 0:
        return 1.0
    mu = n * p
    var = n * p * (1.0 - p)
    if var <= 0:
        return 1.0 if k >= mu else 0.0
    z = (k + 0.5 - mu) / math.sqrt(var)
    return 0.5 * math.erfc(-z / math.sqrt(2.0))


def minimal_dependent(idx: dict, *, alpha: float = 0.05) -> dict:
    """**最小依赖集**：键显著依赖，而它的**所有真子集都不**。

    零假设是键内部**相互独立**。返回 `{tested, dependent, minimal, rows, ...}`。
    ⚠️ `p` 是判据不是排序键；`rows` 按 p 升序只为 Holm 的逐步过程。
    """
    from itertools import combinations
    n = len(idx["records"])
    keys = idx["keys"]
    marg = {}
    for k, sel in keys.items():
        if len(k) == 1:
            marg[next(iter(k))] = len(sel)
    if n == 0:
        return {"tested": 0, "dependent": 0, "minimal": 0, "rows": [],
                "alpha": alpha, "method": "二项正态近似 + Holm（**近似**）"}
    ps = {}
    for k, sel in keys.items():
        if len(k) < 2:
            continue
        prod = 1.0
        ok = True
        for f in k:
            m = marg.get(f)
            if not m:
                ok = False
                break
            prod *= m / n
        if not ok or prod <= 0:
            continue
        ps[k] = _binom_le(len(sel), n, prod)
    # Holm：先对全部被检键校正（正文行 2540 的逐步法）
    ordered = sorted(ps.items(), key=lambda kv: kv[1])
    mt = len(ordered)
    holm, stopped = {}, False
    for i, (k, p) in enumerate(ordered):
        ph = min(1.0, p * (mt - i))
        holm[k] = ph
        if stopped or ph > alpha:
            stopped = True
    # 最小性：显著依赖，而**所有真子集都不显著**
    rows, minimal = [], []
    for k, _p in ordered:
        if holm[k] > alpha:
            continue
        subs_sig = [s for r in range(1, len(k))
                    for s in combinations(sorted(k), r)
                    if holm.get(frozenset(s), 1.0) <= alpha]
        rows.append({"key": sorted(k), "p": ps[k], "p_holm": holm[k],
                     "dependent_subsets": len(subs_sig),
                     "minimal": not subs_sig})
        if not subs_sig:
            minimal.append(k)
    return {"tested": mt, "dependent": len(rows), "minimal": len(minimal),
            "rows": rows, "minimal_keys": sorted(minimal, key=lambda k: sorted(k)),
            "alpha": alpha,
            "method": "零假设=相互独立；二项正态近似 + Holm；只留最小依赖集"
                      "（**近似，非正文点名的精确检验**）"}
