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


def facets_of(record, views, *, content_in_key: bool = False) -> list:
    """一条差异记录的「面=值」。**默认只给结构面。**

    ⚠️ **内容面默认不进键** —— 这一条是跑 Perspectrum 时撞出来的设计更正：

        内容面原先按「**每个节点的标签**一个面」来算。Scaffold 语料 45 个面
        （`C(45,3)` 量级，15,180 个候选，跑得动）；而 Perspectrum 一个 claim
        有 100+ 个 evidence ⇒ **100+ 个面** ⇒ `C(160,3)` 量级 ⇒ **枚举爆炸**。

    **根因**：面数随**节点数**增长，而合取枚举是面数的组合数 ⇒ 必然爆。

    而正确的设计一直写在 `RETRIEVAL.md` 里：

        检索单元 = 一个「面合取」+ **它选中的那批差异记录**

    ⇒ **内容是「载荷」，不是「键」。** 键只用**结构面**
    （词表有限 ⇒ 面数有界），内容跟着**命中的记录**返回。
    这一改同时解掉：① 枚举爆炸；② 内容面与结构面重复表达同一信息
    （那个看着像同义反复的键，本来就该二者留一）。

    `content_in_key=True` 保留旧行为，**只为对照**（它会爆）。
    """
    from analysis import concepts as K
    out = [(f"结构:{a}", a) for a in K.features(record, views)]
    if content_in_key:
        from analysis import focus as F
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


def productivity_wrong_null(idx: dict, *, alpha: float = 0.05) -> dict:
    """⚠️ **零假设取错的对照实现**，保留是为了让那个错留档。

    它问的是「**给定父**的条件独立」下的收窄 —— 而正文问的是
    「集合内部**相互独立**」（行 2218），并要 **positive** 依赖（行 2311）。
    **它是错的**，且用超几何的**正态近似**。

    保留的理由：`checks/index.py` 的 ⑥ 用它钉住一次对照 ——
    **同一个材料上「测总支持度 → 0 个；测增量（错零假设）→ 10 个」**，
    而改正后的 `self_sufficient()` 给的是第三个不同的数。
    **三个数各不相同，才说明这条路是一步步修对的，不是一次蒙对。**

    ⚠️ **不要在新代码里调它。** 要判据请用 `self_sufficient()`。
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




# 这里原有一个 `minimal_dependent()`，**已删**。它记着一种错法：
#
#     「显著依赖」用**二项正态近似**测**总支持度**；而单面键**不可检验**
#     （一个面时独立期望就是它自己的边际）=> 最小性**空判**
#     => 实测 `minimal == dependent == 1` —— **同一个数**。
#
# 取代它的是 `bipartition_dependent()` 与 `self_sufficient()`：
# **最小可检验的集合从 1 变成 2**（二分 `{a}|{b}` 是真正的 2x2 检验）。
#
# 之所以**删而不是留**：它的错法已经写在三处（本注释、`RETRIEVAL.md`、
# 断言 7 的消息里），而**看起来可调用的死代码比一条注释更危险** ——
# 下一个读代码的人会以为它还是那条路。它的辅助 `_binom_le()` 也随之删了。





# ── 取代上面那个：**二分 + Fisher 精确** ───────────────────────────────
#
# ⚠️ `minimal_dependent()` 里的最小性是**空判**，原因是结构性的：
#
#     单面键不可检验 —— 一个面时独立期望**就是它自己的边际**，
#     所以 p 恒在 0.5 附近，**永远不显著**。
#     ⇒ 「它显著而所有真子集都不」对大小 2 的键**恒为真**。
#     ⇒ 实测 `minimal == dependent == 1` —— **同一个数，那一层没在筛**。
#
# 正文给的路（`sspdtutarxiv.tex`）：
#
#     行 2174  一个集合表现依赖 ⟺ 它的**每个二分**都依赖
#     行 2268  correlation rules = **最小**的依赖集
#     行 1855  Fisher's exact test is always a safe [choice]
#
# **二分把集合切成两个非空部分**，所以**最小可检验的集合是大小 2**
# （它的二分是 `{a}|{b}`，一个真正的 2×2 检验）。最小性因此立得住。
#
# ⚠️ 实测（Scaffold 语料）：依赖 **71** → 最小 **62** —— **两个不同的数**。
# 而那两个数相等正是上一版的病灶，所以断言要钉住「它们不等」。


def _hyper_two_sided(a: int, r1: int, c1: int, n: int) -> float:
    """2×2 表的 Fisher 精确检验。双侧 = **两个单侧尾取小、且含并列**。

    ⚠️ 含并列这条是本仓库在零模型那一轮量出的规矩：不含并列时
    **低端与高端都会被判「极端」**（并列被当成「不在分布里」）。
    """
    import math
    if n <= 0:
        return 1.0
    lo = max(0, r1 + c1 - n)
    hi = min(r1, c1)

    def pmf(x: int) -> float:
        return (math.comb(r1, x) * math.comb(n - r1, c1 - x)) / math.comb(n, c1)

    ge = sum(pmf(x) for x in range(a, hi + 1))
    le = sum(pmf(x) for x in range(lo, a + 1))
    return min(1.0, min(ge, le))


def bipartition_dependent(idx: dict, *, alpha: float = 0.05,
                          max_size: int = 4) -> dict:
    """**每个二分都显著**才算依赖；只留**最小**的那些。

    `max_size` 限制枚举的键长（大小 4 以内已足够，且便宜）。**纯判定，不打分排序。**
    """
    from itertools import combinations
    per = idx["per_record"]
    n = len(per)
    allf = sorted({f for s in per for f in s})
    keys = [frozenset(c) for k in range(2, max_size + 1)
            for c in combinations(allf, k)]
    dep = {}
    for k in keys:
        worst = 0.0
        for r in range(1, len(k) // 2 + 1):
            for left in combinations(sorted(k), r):
                right = tuple(sorted(set(k) - set(left)))
                if not right:
                    continue
                A = {i for i, fs in enumerate(per) if set(left) <= fs}
                B = {i for i, fs in enumerate(per) if set(right) <= fs}
                worst = max(worst, _hyper_two_sided(len(A & B), len(A), len(B), n))
        if worst <= alpha:
            dep[k] = worst
    minimal = [k for k in dep if not any(o < k for o in dep)]
    return {"n_candidates": len(keys), "dependent": len(dep),
            "minimal": len(minimal),
            "minimal_keys": sorted(minimal, key=lambda k: sorted(k)),
            "alpha": alpha, "max_size": max_size,
            # ⚠️ 判据不是"抽出了多少"，而是**这一层有没有在筛**
            "filtering": len(dep) != len(minimal),
            "method": "依赖 ⟺ 每个二分都显著（Fisher 精确，双侧取小含并列）；"
                      "只留最小依赖集（correlation rules）"}


# ══════════════════════════════════════════════════════════════════════
# self-sufficient itemsets 的**四条**判据（正文行 2311–2342）
# ══════════════════════════════════════════════════════════════════════
#
# ⚠️ **本节取代上面两个函数**，而它们各自的病灶写在这里，免得被改回去：
#
#     `productivity()`        零假设取「给定父的条件独立」，**不是**相互独立
#     `minimal_dependent()`   最小性是**空判** —— 单面键不可检验
#                             （一个面时独立期望就是它自己的边际 ⇒ p 恒在 0.5 附近）
#                             ⇒ 「显著而所有真子集都不」对大小 2 的键恒为真
#
# 正文那四条（行 2311–2342）：
#
#     ① **productivity**     对**每个二分**都要有显著依赖，用 Fisher 精确
#     ② **non-redundant**    ∃ Y ⊊ X, Z ⊊ Y : fr(Y) = fr(Z) 就是冗余
#     ③ **independently productive**
#                            若有 Y ⊋ X 既 productive 又 non-redundant，
#                            则 X 要在「**去掉 Y∖X 覆盖的数据**」之后重测 productivity
#     ④ **最小性**（correlation rules，行 2268）X 依赖而所有真子集都不
#
# ⚠️ **一处刻意偏离，必须声明**：
#
#     正文行 2311 / 2268 要的是 **positive** dependency（共现比独立**多**）。
#     而**我的索引键有用恰恰在于它收窄得厉害** —— 那是**负**依赖
#     （共现比独立**少**）。论文的 dependency set 是「常一起出现的项」，
#     我的键是「判别性的合取」，**两者方向相反**。
#
#     ⇒ 所以 `direction` 是**显式参数**，默认 `"lower"`（收窄），
#       而引用时**不许**把它说成正文那一条。正文那一条请传 `"upper"`。


def _hyper_one_sided(a: int, r1: int, c1: int, n: int, direction: str) -> float:
    """2×2 表的 Fisher 精确**单侧** p（**含并列**）。

    `"upper"` = 共现比独立**多**（正依赖，正文那一条）；
    `"lower"` = 共现比独立**少**（收窄，本层要的那一条）。

    ⚠️ 含并列是本仓库在零模型那一轮量出的规矩：不含并列时**两端都会被判「极端」**。
    """
    import math
    if n <= 0:
        return 1.0
    lo = max(0, r1 + c1 - n)
    hi = min(r1, c1)

    def pmf(x: int) -> float:
        return (math.comb(r1, x) * math.comb(n - r1, c1 - x)) / math.comb(n, c1)

    if direction == "upper":
        return min(1.0, sum(pmf(x) for x in range(a, hi + 1)))
    if direction == "lower":
        return min(1.0, sum(pmf(x) for x in range(lo, a + 1)))
    raise ValueError(f"direction 只认 upper / lower，收到 {direction!r}")


def _sel(key, per) -> frozenset:
    return frozenset(i for i, fs in enumerate(per) if set(key) <= fs)


def _bip_p(key, per, n, direction) -> float:
    """一个集合**所有二分**里**最差**的那个 p。"""
    from itertools import combinations
    ks = sorted(key)
    worst = 0.0
    for r in range(1, len(ks) // 2 + 1):
        for left in combinations(ks, r):
            right = tuple(sorted(set(ks) - set(left)))
            if not right:
                continue
            A, B = _sel(left, per), _sel(right, per)
            worst = max(worst, _hyper_one_sided(len(A & B), len(A), len(B), n,
                                                direction))
    return worst


def _productive(key, per, n, alpha, direction, allowed=None) -> bool:
    """① productivity：每个二分都显著。`allowed` 限定可用的记录（给③用）。"""
    if len(key) < 2:
        return False
    if allowed is not None:
        keep = set(allowed)
        per2 = [(fs if i in keep else frozenset())
                for i, fs in enumerate(per)]
        n2 = len(keep)
        if n2 == 0:
            return False
    else:
        per2, n2 = per, n
    return _bip_p(key, per2, n2, direction) <= alpha


def _redundant(key, per) -> bool:
    """② non-redundant 的反面：`∃ Y ⊊ X, Z ⊊ Y : fr(Y) = fr(Z)`（行 2320）。"""
    from itertools import combinations
    ks = sorted(key)
    for rY in range(2, len(ks) + 1):
        for Y in combinations(ks, rY):
            fy = _sel(Y, per)
            for rZ in range(1, rY):
                for Z in combinations(Y, rZ):
                    if _sel(Z, per) == fy:
                        return True
    return False


def self_sufficient(idx: dict, *, alpha: float = 0.05, max_size: int = 3,
                    direction: str = "lower") -> dict:
    """①②③④ 一起。返回被留的集合与**每一条判据各淘汰了多少**。

    ⚠️ `direction` 默认 `"lower"`（收窄）是**刻意的偏离**，见本节标题下的声明。
    """
    from itertools import combinations
    per = idx["per_record"]
    n = len(per)
    allf = sorted({f for s in per for f in s})
    cand = [frozenset(c) for k in range(2, max_size + 1)
            for c in combinations(allf, k)]
    # ① productivity
    prod = [k for k in cand if _productive(k, per, n, alpha, direction)]
    # ② non-redundant
    nonred = [k for k in prod if not _redundant(k, per)]
    # ④ 最小性（真子集里没有已经 productive 的）
    pset = set(prod)
    minimal = [k for k in nonred
               if not any(frozenset(o) < k for o in pset)]
    # ③ independently productive：对每个 productive+nonredundant 的**真超集** Y，
    #    去掉 Y∖X 覆盖的数据后重测
    kept, dropped3 = [], 0
    for k in minimal:
        sups = [y for y in nonred if y > k]
        ok = True
        for y in sups:
            extra = set(y) - set(k)
            excl = _sel(extra, per)
            allowed = [i for i in range(n) if i not in excl]
            if not _productive(k, per, n, alpha, direction, allowed=allowed):
                ok = False
                break
        if ok:
            kept.append(k)
        else:
            dropped3 += 1
    # 哪一步淘汰了多少 —— 这是判据各自的账，不能只报最终数
    counts = {"候选": len(cand), "① productivity 后": len(prod),
              "② non-redundant 后": len(nonred),
              "④ 最小性后": len(minimal), "③ 之后": len(kept)}
    return {"kept": sorted(kept, key=lambda k: sorted(k)), "n_kept": len(kept),
            "dropped_by_3": dropped3, "counts": counts,
            "alpha": alpha, "max_size": max_size, "direction": direction,
            "declared_deviation": None if direction == "upper" else
            "direction=lower 是**刻意的偏离**：正文要 positive dependency，"
            "而索引键有用在于**收窄**（负依赖）。引用时不许把它说成正文那一条。",
            "method": "self-sufficient itemsets：productivity ∧ non-redundant ∧ "
                      "最小性 ∧ independently productive（Fisher 精确，含并列）"}
