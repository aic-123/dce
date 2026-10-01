"""Compression —— `total input structure / synthesis structure`（§十三）。

---
三种口径，都报出来，因为「合成结构」可以指三样不同的东西
------------------------------------------------------

设计稿只说 `total input structure / synthesis structure`，没说后者怎么数。
**这不是可以含糊过去的地方** —— 换一种数法，压缩比能差三倍。所以三档都给：

    flat      合成结构 = 共识单元 + **每条分歧记录各算一条**
              口径最保守：DCE 逐条罗列差异，罗列出来的每一条都是结构

    focused   合成结构 = 共识单元 + **每个焦点各算一条**
              口径中等：把同一处的一堆差异概括成「这里有个焦点」

    synopsis  合成结构 = 共识单元 + **每个焦点各算一条 + 焦点类型直方图**
              口径最激进：焦点内部不再逐条列，只报它由哪几类差异构成

分母恒为 `Σ_v |units(v)|`（**求和，不是并集**）—— 因为压缩比问的是
「把这几份视图原样摊开要多少结构，概括成一份要多少」，
摊开的那一份当然按重复次数算。

⚠️ 与 Coverage 的取舍正好相反：Coverage 用并集，Compression 用求和。
两处不同**是有意的**，理由写在各自模块里。混用会让两个指标都失真。

---
目标不是「压缩越高越好」
----------------------

§十三：「目标不是单纯 Coverage 越高越好，而是寻找 **高 Coverage + 高 Compression**
的区域」。所以这不是一个要最大化的数，是一个要**画出来的区域**：
拿生成器的旋钮（视图数、共同结构比例、植入差异数）当横轴，看 `(Coverage, Compression)`
往哪走。本模块只负责把点算出来。
"""

from __future__ import annotations

from analysis import consensus as C


def input_size(views) -> int:
    """`Σ_v |units(v)|` —— 求和，不是并集。理由见模块 docstring。"""
    return sum(len(C.units_of(v)) for v in views)


def synthesis_size(syn, mode: str = "flat") -> int:
    """合成结构的规模。`mode ∈ {flat, focused, synopsis}`。"""
    if mode not in ("flat", "focused", "synopsis"):
        raise ValueError(f"未知口径 {mode!r}，只认 flat / focused / synopsis")
    base = len(syn["consensus"]["records"])
    if mode == "flat":
        return base + len(syn["divergence"])
    if mode == "focused":
        return base + len(syn["foci"])
    # synopsis：焦点各算一条，加上「出现过哪几类差异」这一张直方图
    kinds = set()
    for f in syn["foci"]:
        kinds |= set(f["types"])
    return base + len(syn["foci"]) + len(kinds)


def compression(views, syn, mode: str = "flat") -> dict:
    """算压缩比。三档口径都在 `all_modes` 里，免得读者以为只有一个数。"""
    inp = input_size(views)
    out = synthesis_size(syn, mode)
    return {
        "mode": mode,
        "input": inp,
        "synthesis": out,
        "value": (inp / out) if out else None,
        "all_modes": {m: (inp / synthesis_size(syn, m))
                      for m in ("flat", "focused", "synopsis")},
    }
