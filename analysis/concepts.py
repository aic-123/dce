"""形式概念分析：把分歧记录 × 特征做成概念格 —— 借自 FCA，用来做**多特征**的焦点。

---
为什么是它
----------

按**主语一个字段**分组（`focus.subject_foci`）解开了一级概括，但它有个明确的局限：

    「SC-其他 缺了 63 样东西」回答了「**哪儿缺**」，没回答「**缺的是什么**」。

要往下一级，就得**同时**看几个特征，而不是一个。而「同时在多个特征上聚」
正是形式概念分析的本行 —— 它比双聚类更贴，因为它**自带一个判据**：

    一个概念 = 一对（外延 = 记录集，内涵 = 特征集），且是**极大配对**
    整格**无参数** —— 找概念这件事本身不引入阈值
    `Sep(C) = |Ext(C)| − |∪_{K ≺ C} Ext(K)|`   **这个概念比它的直接子概念多覆盖了什么**

`Sep` 正是第二级概括缺的那个量：**这一步有没有新增信息**。
而且 `Sep > 0` 不是阈值，是**结构判据**（`Sep = 0` 意味着这个概念
在它的子概念面前完全冗余）。

出处已核（`PRIOR-ART.md` §五）：`fcaR` 的 lattice metrics vignette，
`fcaR` 的稳定性与分离度公式逐字核过。

---
⚠️ 一处必须说明的：`Sep` 需要「直接子概念」
-----------------------------------------

`Sep(C) = |Ext(C)| − |∪_{K ≺ C} Ext(K)|` 里的 `≺` 是**直接子概念**（覆盖关系）。
本模块按**外延的严格包含**算它：`K ≺ C` ⟺ `Ext(K) ⊊ Ext(C)` 且不存在
中间的 `M` 使 `Ext(K) ⊊ Ext(M) ⊊ Ext(C)`。那是概念格里标准的覆盖关系。

---
⚠️ 概念数会爆，而爆了要**拒绝**不要截断
-------------------------------------

格的规模可以是指数的。本模块在超过上限时**拒绝并说明**，
不悄悄截断 —— 「截断过的格」与「真正的格」在输出上长得一样，
而 `Sep` 依赖覆盖关系，截断会把它算错。
"""

from __future__ import annotations

MAX_CONCEPTS = 20000


class ConceptError(Exception):
    """参数或规模不对。"""


def features(record, views) -> list:
    """一条分歧记录身上的**特征**（属性的字面名，稳定且可读）。

    只取结构性的东西，不取任何数值 —— 取数值会让属性集无限增长，
    而 FCA 需要**有限**的属性集。
    """
    from analysis import focus as F
    t = record["type"]
    out = [f"类型:{t}"]

    # 单元种类 + 关系种类
    if "unit" in record:
        kind, key = record["unit"]["kind"], record["unit"]["key"]
        out.append(f"单元:{kind}")
        if kind == "edge":
            out.append(f"关系:{key[2]}")
    elif t == "contradiction":
        out.append("单元:edge")
        for rel in sorted(record["relations"]):
            out.append(f"关系:{rel}")
    elif t == "alternative":
        out.append("单元:edge")
        out.append(f"关系:{record['relation']}")

    # 锚点的角色：这条分歧贴着的是 from 还是 to
    an = F.anchors(record)
    if t == "contradiction":
        out.append("角色:两端")
    elif t == "alternative":
        out.append("角色:源")
    elif t == "refinement":
        out.append("角色:粒度")
    else:
        out.append("角色:缺失方")

    # 卷入的视图（视图族的主语）
    for v in sorted(F.views_of(record)):
        out.append(f"视图:{v}")
    return sorted(set(out))


def context(records: list, views) -> dict:
    """形式背景：对象 = 分歧记录，属性 = 特征。

    ⚠️ 收的是**记录列表**而不是整个 divergence —— 因为二级概括要能
    **只在某个一级焦点内部**建格。
    """
    attrs = {i: set(features(r, views)) for i, r in enumerate(records)}
    all_attrs = sorted({a for s in attrs.values() for a in s})
    return {"records": records, "attrs": attrs, "all_attrs": all_attrs,
            "n_objects": len(records), "n_attrs": len(all_attrs)}


def _closure(ctx: dict, A: frozenset) -> tuple:
    """`A` 的闭包：先取「拥有 A 全部属性」的对象（外延），
    再取那些对象**共有**的属性（内涵）。返回 `(内涵, 外延)`。"""
    ext = frozenset(i for i, s in ctx["attrs"].items() if A <= s)
    if not ext:
        return frozenset(ctx["all_attrs"]), frozenset()
    int_ = set(ctx["all_attrs"])
    for i in ext:
        int_ &= ctx["attrs"][i]
    return frozenset(int_), ext


def all_concepts(ctx: dict, max_concepts: int = MAX_CONCEPTS) -> dict:
    """枚举**全部**形式概念（按「每次加一个属性再取闭包」的宽度优先）。

    这是完备的：任何闭集都可以从空集出发、逐个加入它自己的属性再取闭包达到。
    超过上限时**拒绝**，不截断。
    """
    start = _closure(ctx, frozenset())
    seen = {start}
    queue = [start]
    while queue:
        int_, ext = queue.pop()
        for a in ctx["all_attrs"]:
            if a in int_:
                continue
            c = _closure(ctx, int_ | {a})
            if c not in seen:
                seen.add(c)
                if len(seen) > max_concepts:
                    raise ConceptError(
                        f"概念数超过上限 {max_concepts}（{ctx['n_objects']} 个对象 × "
                        f"{ctx['n_attrs']} 个属性）。**拒绝算，不截断** —— "
                        "截断过的格与真正的格在输出上长得一样，"
                        "而 Sep 依赖覆盖关系，截断会把它算错。"
                    )
                queue.append(c)
    concepts = sorted(seen, key=lambda c: (-len(c[1]), sorted(c[0])))
    return {"concepts": concepts, "n_concepts": len(concepts)}


def separation(concepts: list) -> list:
    """每个概念的**分离度**：`Sep(C) = |Ext(C)| − |∪_{K ≺ C} Ext(K)|`。

    `Sep = 0` 意味着这个概念在它的直接子概念面前**完全冗余** —— 那不是阈值，
    是结构事实。返回 `[(concept, sep, children)]`。
    """
    by_ext = {c[1]: c for c in concepts}
    out = []
    for int_, ext in concepts:
        # 直接子概念：外延被严格包含、且没有被中间者挡住的那些
        subs = [e for e in by_ext if e < ext]
        children = [e for e in subs
                    if not any(e < m < ext for m in subs if m != e)]
        covered = set()
        for ch in children:
            covered |= set(ch)
        out.append({"intent": int_, "extent": ext,
                    "sep": len(ext) - len(covered),
                    "n_children": len(children)})
    return out


def label(intent: frozenset) -> str:
    """把内涵读成一句话 —— 概念本身就自带「它是关于什么」的说明。"""
    parts = sorted(intent)
    short = "、".join(p for p in parts if not p.startswith("视图:"))
    views = [p.split(":", 1)[1] for p in parts if p.startswith("视图:")]
    s = short or "（无特征）"
    if views:
        s += f" ｜ 视图 {'/'.join(views)}"
    return s


def lattice(records: list, views, max_concepts: int = MAX_CONCEPTS) -> dict:
    """一次算完：形式背景 → 全部概念 → 分离度。"""
    ctx = context(records, views)
    got = all_concepts(ctx, max_concepts=max_concepts)
    seps = separation(got["concepts"])
    return {"context": ctx, "n_concepts": got["n_concepts"], "seps": seps,
            "irredundant": [s for s in seps if s["sep"] > 0],
            "redundant": [s for s in seps if s["sep"] == 0]}


# ── 二级概括：一级焦点**内部**再展开 ────────────────────────────────
#
# ⚠️ 为什么全格**不能**直接当焦点集：立场材料上 20 条记录 → **62 个概念**，
# 比记录还多。那违反 R2（焦点数必须远少于记录数）—— 格是**展开**，不是**概括**。
#
# 所以两级的正确分工是：
#
#     一级  按主语分组（`focus.subject_foci`）      20 → 6   压缩
#     二级  一级焦点**内部**建格，取非冗余概念      7 → 3   展开
#
# 一级负责「往哪儿看」，二级负责「具体是什么」。而二级那个判据
# `Sep > 0` **不是阈值** —— 它是结构事实（这个概念在它的直接子概念面前是否冗余）。


def second_level(divergence: dict, views, max_concepts: int = MAX_CONCEPTS,
                 only_if_compresses: bool = False) -> list:
    """对每个一级（主语）焦点，算它内部的二级概念。

    返回 `[{parent, label, n_records, concepts: [...], expands}]`。

    ⚠️ `only_if_compresses` 与「显示规则」有关，而那条规则**必须是结构性的**：

        二级概念数 < 桶内记录数  →  它**概括**了，值得显示
        二级概念数 ≥ 桶内记录数  →  它只是**展开**（等于把每条记录换个说法），别显示

    实测这条规则在两种材料上各占一边：
        立场材料     20 条 / 16 特征，多数概念外延只有 1 → **展开**（1+2 级共 22 条，0.9x）
        真实语料    192 条，桶 63/61/54/14 → **概括**（1+2 级共 25 条，7.7x）
    **所以二级不是「总是更好」，是「桶大的时候才有用」。**
    """
    from analysis import focus as F
    recs_all = F._all_records(divergence)
    out = []
    for f in F.subject_foci(divergence, "structure"):
        mine = [r for r in recs_all if F.subject_of(r) == f["subject"]]
        entry = {"parent": f["focus"], "label": f["label"],
                 "subject": f["subject"], "n_records": len(mine),
                 "concepts": [], "expands": None}
        if len(mine) >= 2:
            lat = lattice(mine, views, max_concepts=max_concepts)
            kids = [
                {"intent": sorted(s["intent"]), "extent": sorted(s["extent"]),
                 "sep": s["sep"], "n_children": s["n_children"],
                 "label": label(s["intent"])}
                for s in sorted(lat["irredundant"],
                                key=lambda x: (-x["sep"], -len(x["extent"])))
                if len(s["extent"]) < len(mine)      # 去掉「整个焦点」那条平凡概念
            ]
            entry["n_concepts_all"] = lat["n_concepts"]
            entry["expands"] = len(kids) >= len(mine)
            entry["concepts"] = [] if (only_if_compresses and entry["expands"]) \
                else kids
        out.append(entry)
    return out


def second_level_summary(divergence: dict, views) -> dict:
    """二级概括的总账：一级几个、二级共几个、压缩了多少。"""
    from analysis import focus as F
    lv2 = second_level(divergence, views)
    n1 = len(lv2)
    n2 = sum(len(e["concepts"]) for e in lv2)
    n_rec = len(F._all_records(divergence))
    return {"n_records": n_rec, "n_level1": n1, "n_level2": n2,
            "level1_compression": (n_rec / n1) if n1 else None,
            "total_after_level2": n1 + n2,
            "level2_compression": (n_rec / (n1 + n2)) if (n1 + n2) else None,
            "levels": lv2}
