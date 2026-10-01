"""粗糙集：正域 / 依赖度 / 约简 —— 借自 Pawlak 1982。

---
映射：对象 = 结构单元，条件属性 = 视图，决策属性 = 差异类型
--------------------------------------------------------

    不可分辨类    **出现在完全相同的那几个视图里**的单元归为一类
                 （它们的「成员签名」一样）
    下近似        签名相同的那一类**全部**属于同一个差异类型
    正域 POS      全部下近似的并 —— 签名就足以确定类型的那些单元
    依赖度 γ      γ = |POS| / |U|
    约简          保持 γ 不变的**最小视图子集**

---
⚠️ 这一层给出的是一条**精确判据**，正面回答 §十六 那个问题
--------------------------------------------------------

§十六 的基线 C 问的是：**「DCE 是否只是 graph frequency bookkeeping？」**
之前本仓库只能定性回答（「划分与 union+frequency 完全相同，但类型不同」）。

在粗糙集映射下，那句话有一个**精确的形式**：

    γ = 1  ⟺  每个不可分辨类都落在单个决策类里
          ⟺  **类型判定完全由「单元出现在哪几个视图」决定**
          ⟺  **类型没有携带成员关系之外的任何信息**

    γ < 1  则 1 − γ 正好量出「类型里有多少不是成员关系蕴含的」

推导很短：正域 = 全体 ⟺ 每个签名类都被某个决策类包含 ⟺ 类型是签名的函数。
所以 **γ 不是又一个「像不像」的指标，它是对那句话的等价改写。**

---
⚠️ α 与 γ 是两个不同的量，本模块**两个都给**，不替你选
----------------------------------------------------

`PRIOR-ART.md` 里核到（并更正过）这件事：粗糙集里有两个都叫「质量」的东西：

    近似精度 α = |下近似| / |上近似|        紧不紧
    依赖度   γ = |正域| / |全体|            覆盖多少

第一版调研里我把两者混成了一个式子。对 DCE 它们含义不同，
**选哪一个是有后果的**，所以本模块把两个都算出来、都报，
把取舍留在判据层 —— 那正是「先写判据」那条规矩的用处。

（经典 RST 无参数；`RoughSets` 手册原文：
`RST does not require additional parameters to analyze the data`。
本模块只用经典那一半 —— 模糊扩展会把一整排参数请回来。）
"""

from __future__ import annotations

# 类型的优先顺序，与 `analysis/divergence.analyse` 的认领顺序一致。
PRECEDENCE = ("refinement", "contradiction", "alternative", "omission")


class RoughError(Exception):
    """参数不对。"""


def signatures(units: list, views: list) -> dict:
    """每个单元的「成员签名」= 它出现在哪几个视图里（视图 id 的有序元组）。

    ⚠️ **集合而不是计数**。这正是与「出现次数」的区别所在：
    两个单元都出现在 2 个视图里，但如果是**不同的那 2 个**，
    它们的签名不同、不可分辨类也不同。基线 C 只看计数，看不见这个区别 ——
    而 γ 要量的恰恰是「类型里有多少在计数之外」。
    """
    out = {}
    for u in units:
        sig = tuple(sorted(v["id"] for v in views if u in _units_of(v)))
        out[u] = sig
    return out


def _units_of(view) -> set:
    from analysis import consensus as C
    return C.units_of(view)


def typing(views: list) -> dict:
    """每个单元的**差异类型**（决策属性）。按 `PRECEDENCE` 认领，取第一个命中的。"""
    from analysis import divergence as D
    div = D.analyse(views)
    out = {}
    for t in PRECEDENCE:
        for rec in div.get(t, []):
            if t in ("omission", "refinement"):
                u = (rec["unit"]["kind"], rec["unit"]["key"])
                out.setdefault(u, t)
            elif t == "contradiction":
                for rel in rec["relations"]:
                    out.setdefault(("edge", (rec["from"], rec["to"], rel)), t)
            elif t == "alternative":
                for _vid, targets in rec["views"].items():
                    for x in targets:
                        out.setdefault(("edge", (rec["source"], x,
                                                 rec["relation"])), t)
    from analysis import consensus as C
    for v in views:
        for u in C.units_of(v):
            out.setdefault(u, "consensus")
    return out


def _partition(sig: dict, units: list) -> dict:
    """按签名分组成不可分辨类。"""
    groups: dict[tuple, list] = {}
    for u in units:
        groups.setdefault(sig[u], []).append(u)
    return groups


def approximations(views: list, units: list | None = None) -> dict:
    """算不可分辨类、下/上近似、正域。返回一个字典。

    ⚠️ 上近似的定义是「与某个类**可能**同属一个决策类」——
    在等价关系下，一个决策类 X 的上近似就是「与 X 有交的那些签名类」的并。
    """
    from analysis import consensus as C
    if units is None:
        units = sorted(C.universe(views), key=lambda x: (x[0], str(x[1])))
    sig = signatures(units, views)
    typ = typing(views)

    classes = _partition(sig, units)
    decisions: dict[str, list] = {}
    for u in units:
        decisions.setdefault(typ[u], []).append(u)

    lower: dict[str, set] = {}
    upper: dict[str, set] = {}
    for d, members in decisions.items():
        ms = set(members)
        lower[d] = {u for u in ms
                    if set(classes[sig[u]]) <= ms}
        upper[d] = {u for u in units
                    if set(classes[sig[u]]) & ms}

    pos = set().union(*lower.values()) if lower else set()
    return {"units": units, "signatures": sig, "classes": classes,
            "decisions": decisions, "lower": lower, "upper": upper,
            "positive": pos}


def gamma(views: list, units: list | None = None) -> dict:
    """**依赖度** γ = |正域| / |全体|。见模块 docstring 里那条等价式。"""
    a = approximations(views, units)
    n = len(a["units"])
    return {"gamma": (len(a["positive"]) / n) if n else None,
            "n_units": n, "n_positive": len(a["positive"]),
            "n_classes": len(a["classes"])}


def alpha(views: list, units: list | None = None) -> dict:
    """**近似精度** α = 各决策类 |下近似|/|上近似| 的均值。**与 γ 不是一个量。**"""
    a = approximations(views, units)
    per = {}
    for d in a["decisions"]:
        lo, up = len(a["lower"][d]), len(a["upper"][d])
        per[d] = (lo / up) if up else None
    vals = [v for v in per.values() if v is not None]
    return {"alpha": (sum(vals) / len(vals)) if vals else None, "per_class": per}


def reducts(views: list, max_subsets: int = 4096) -> dict:
    """保持 γ 不变的**最小**视图子集。

    ⚠️ 经典 RST 的约简是 NPC 的，但本仓库的视图数是个位数，所以可枚举。
    超过 `max_subsets` 个组合就**拒绝算并说明**，而不是悄悄截断 ——
    截断过的「最小子集」不是最小子集。

    ⚠️ **从 k=2 起算，不查单视图子集 —— 那是有意的。**
    一个视图没有「之间」：它的全部单元按定义都是共识，于是只有一个签名类、
    一个决策类，**γ 恒等于 1**。那不是有信息的结果，是退化。
    若把 k=1 放进候选，「最小约简」永远是一个视图，而那个答案什么都没说。
    （第一版就是这么写的，跑出来撞的是 `analyse` 的「至少 2 个视图」守卫 ——
    守卫拦对了，但它拦的是一个**语义上就不该问的问题**。）
    """
    from itertools import combinations
    n = len(views)
    if n < 2:
        return {"refused": True, "reason": f"只有 {n} 个视图，谈不上约简",
                "gamma": None, "reducts": []}

    full = gamma(views)["gamma"]
    # 从 2 起算；单视图子集被有意排除（见 docstring）
    total = sum(_n_choose_k(n, k) for k in range(2, n + 1))
    if total > max_subsets:
        return {"refused": True, "reason":
                f"{n} 个视图共 {total} 个（≥2 元的）子集，超过上限 {max_subsets} —— "
                "截断过的「最小子集」不是最小子集，所以拒绝算",
                "gamma": full, "reducts": []}
    found = []
    for k in range(2, n + 1):
        if found:
            break                      # 已经找到更小的，就不看更大的
        for idx in combinations(range(n), k):
            g = gamma([views[i] for i in idx])["gamma"]
            if g is not None and full is not None and abs(g - full) < 1e-12:
                found.append(tuple(views[i]["id"] for i in idx))
    return {"refused": False, "gamma": full, "reducts": found,
            "n_reducts": len(found), "n_views": n,
            "min_size": (len(found[0]) if found else None),
            "note": "单视图子集被有意排除：它的 γ 恒等于 1，是退化而非有信息"}


def _n_choose_k(n: int, k: int) -> int:
    from math import comb
    return comb(n, k)
