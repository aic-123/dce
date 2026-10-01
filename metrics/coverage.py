"""Coverage —— `reconstructed information / original information`（§十三）。

---
先把三个词定死（不定死就没法复现）
---------------------------------

    original information     = 全部视图的单元**并集**（一个单元被三个视图说，
                               仍然是一份信息）
    reconstructed information = 合成结构**点到过**的单元
                               （共识里的 + 任何一条分歧/精炼记录里的）
    Coverage                  = 前者分之后者

⚠️ **并集而不是求和**：求和会把「同一件事被说了三遍」算成三份信息，
于是覆盖率随着视图数下降 —— 那测的是重复度，不是覆盖。

---
一个必须先说破的预判
------------------

本模块的 Coverage **可能恒等于 1，因而不具区分力**。理由不是实现问题，是结构问题：

    分歧记录是**逐条列出每一个差异**的（omission 逐单元、refinement 逐单元、
    contradiction 逐边、alternative 逐边）。而一个单元只有两种下场：
    要么在所有视图里都有（→ 共识），要么至少缺在一个视图里（→ 某条 omission，
    或者被 refinement 认领）。**没有第三种。**

所以 `Coverage = 1` 是这套设计的**推论**，不是发现。
真出现这种情况，本模块如实报出来，而不是把分母换掉去凑一个好看的数 ——
换分母就是 §T0.3 要防的那种「试到好看为止」。

真正有区分力的是 **Compression**，以及「合成是不是**概括**了而不是**罗列**了」。
后者由 `synopsis` 那一档体现（见下）。
"""

from __future__ import annotations

from analysis import consensus as C


def original_units(views) -> set:
    """全部视图的单元并集 —— 分母。"""
    out = set()
    for v in views:
        out |= C.units_of(v)
    return out


def explained_units(syn) -> set:
    """合成结构点到过的单元 —— 分子。

    四个来源，逐类说清，免得漏算或多算：

    - 共识记录的 `unit`
    - omission / refinement 记录的 `unit`
    - contradiction 记录里两种关系各形成一条边
    - alternative 记录里各视图的后继各形成一条边
    """
    out = set()
    for rec in syn["consensus"]["records"]:
        out.add((rec["unit"]["kind"], rec["unit"]["key"]))
    for rec in syn["divergence"]:
        t = rec["type"]
        if t in ("omission", "refinement"):
            out.add((rec["unit"]["kind"], rec["unit"]["key"]))
        elif t == "contradiction":
            for rel in rec["relations"]:
                out.add(("edge", (rec["from"], rec["to"], rel)))
        elif t == "alternative":
            for _vid, targets in rec["views"].items():
                for x in targets:
                    out.add(("edge", (rec["source"], x, rec["relation"])))
    return out


def coverage(views, syn) -> dict:
    """算覆盖率，并把**没被解释的单元**一并报出来。

    报未解释的那部分，是因为它才是诊断信息：`Coverage = 0.97` 只是个数，
    「哪三个单元没被解释」才是能查的东西。
    """
    orig = original_units(views)
    got = explained_units(syn)
    missing = sorted(orig - got, key=lambda x: (x[0], str(x[1])))
    extra = sorted(got - orig, key=lambda x: (x[0], str(x[1])))
    return {
        "original": len(orig),
        "reconstructed": len(got & orig),
        "value": (len(got & orig) / len(orig)) if orig else None,
        "unexplained": missing,
        "phantom": extra,          # 合成里出现了源视图里没有的单元 —— 那是 bug
    }
