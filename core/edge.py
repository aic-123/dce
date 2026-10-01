"""边身份与关系词表 —— DCE 里最容易出错的一块。

---
§九：边身份是三元的，不是二元的
------------------------------

设计稿 §九 写得很清楚：

    A --supports--> B     和     B --supports--> A     **不是同一个结构**

所以：

    edge_identity = (from, to, relation)

只比两个端点会丢掉方向与关系种类 —— 而「互斥」恰恰是靠 relation 才谈得上。
本模块的 `key()` 就返回这个三元组，任何地方都不许退化成二元组。

---
关系词表：**照抄，不自造**
------------------------

词表不是本模块发明的，是 arena 的 `§C3.2` 与 `§C4`：

    §C3.2 第一版支持的六种：contains  derived_from  supports  contradicts  refines  related_to
    §C4   关系映射：supports / contradicts / qualifies（Evidence→Claim）
                   assumes（Claim→Assumption）  explains（Claim→Mechanism）
                   challenged_by（Claim→Counterargument）
    debate.py: CAUSAL_END_KINDS = ("causal_premise", "causal_conclusion")

---
⚠️ 一个真实的接口缺口：Scaffold 给不出 relation
-----------------------------------------------

DCE §九 要求边带 relation，但 **Scaffold 的 `relations` 是 `list[str]`、不带种类**
（`schema/node.schema.yaml:74-77`，我读过）。带种类的边**只有 arena 有**（它的
`relation.kind`）。

所以：

    想让 DCE 跑起来，typed edge 的词表必须由 **adapter 声明**，不能指望 Scaffold 给。
    Scaffold → Structured View 的 adapter 只有一个选择：把不带种类的引用
    映射成一个**显式声明的**默认种类（本模块给 `SCAFFOLD_UNTYPED`），
    并接受「这样出来的视图没有互斥可言」。

这不是本模块的缺陷，是数据形状的事实。写在这里，免得后来的人以为关系种类是白捡的。

---
互斥集是**声明**，不是学习来的
----------------------------

§五·二 的例子是同一对端点上一个说 `supports`、一个说 `contradicts`。所以：

    contradiction(f, t)  ⇔  ∃ 两个视图在 (f,t) 上给出**被声明为互斥**的两种 relation

互斥关系**必须被声明**。MVP 不做 semantic alignment（§七），所以不做同义词归并 ——
`supports` 与 `support` 在 MVP 眼里是两个不同的种类，这会被当成「两种关系」而不是矛盾。
"""

from __future__ import annotations

# §C3.2 的六种。
C3_KINDS = ("contains", "derived_from", "supports", "contradicts", "refines", "related_to")

# §C4 的四种关系映射（去重后）。
C4_KINDS = ("supports", "contradicts", "qualifies", "assumes", "explains", "challenged_by")

# debate.py 的因果两端。
CAUSAL_KINDS = ("causal_premise", "causal_conclusion")

# 词表的并集 —— **封闭集合**，不认表外的种类。
# 表外出现时报错而不是放过：放过会让「关系种类」这个维度慢慢退化成自由文本。
KNOWN_KINDS = tuple(sorted(set(C3_KINDS) | set(C4_KINDS) | set(CAUSAL_KINDS)))

# Scaffold 的 `relations` 不带种类，adapter 只能映射到这一个声明出来的占位种类。
# 它是**声明的**，不是默认的：用它的 adapter 必须在自己的声明里写明这一点。
SCAFFOLD_UNTYPED = "related_to"     # 复用 §C3.2 里已有的 related_to，不新造词

# ── 互斥集：声明 ──────────────────────────────────────────────────────
#
# 依据是 §C4 那张表把 `supports / contradicts / qualifies` 放在**同一个单元格**里
# （Evidence → Claim），也就是「同一对端点上的三种备选」。既然是备选，两两互斥。
#
# ⚠️ 这是一个**声明**，属于 §T4.1 的 B 类（判据，可能触碰不变量），
#    所以它必须在 CHECKS 里自证不违反不变量，而不是当默认值悄悄生效。
#    `EXCLUSIVE_PAIRS` 由 `test_exclusive_pairs_are_exactly_these` 钉住 ——
#    想多声明一对，必须改那一行，改的时候会被看见。
EXCLUSIVE_PAIRS = (
    ("contradicts", "qualifies"),
    ("contradicts", "supports"),
    ("qualifies", "supports"),
)

# 精炼关系：§五·四 的「一个视图包含另一个、但更详细」。
# §C3.2 里对应 `refines`。它不是分歧，是粒度差异 —— 单独一类，不混进 divergence。
REFINES = "refines"


class EdgeError(Exception):
    """边不对。消息面向调用方。"""


def key(edge) -> tuple:
    """边身份 `(from, to, relation)`。**方向与种类都进身份。**

    §九 的反例：`A supports B` 与 `B supports A` 在这里是两个不同的键。
    """
    if isinstance(edge, dict):
        return (edge["from"], edge["to"], edge["relation"])
    if isinstance(edge, (tuple, list)) and len(edge) == 3:
        return (edge[0], edge[1], edge[2])
    raise EdgeError(f"边必须是三元组或 {{from,to,relation}}，收到 {edge!r}")


def endpoints(edge) -> tuple:
    """无向端点对。**只给「找相邻」这类用途**，不许拿来当身份。"""
    f, t, _ = key(edge)
    return (f, t) if f <= t else (t, f)


def check_kind(relation: str) -> None:
    """种类必须在封闭词表里。表外报错，不放过。"""
    if relation not in KNOWN_KINDS:
        raise EdgeError(
            f"关系种类 {relation!r} 不在已知词表里。\n"
            f"已知的是 {list(KNOWN_KINDS)}（来源：arena §C3.2 ∪ §C4）。\n"
            "表外种类要进来，得先把它加进词表 —— 不放过，是因为放过之后"
            "「关系种类」会慢慢退化成自由文本，而互斥判断依赖它。"
        )


def exclusive(r1: str, r2: str) -> bool:
    """这两种关系是否被声明为互斥。对称。同一种关系不互斥。"""
    if r1 == r2:
        return False
    return ((r1, r2) in EXCLUSIVE_PAIRS) or ((r2, r1) in EXCLUSIVE_PAIRS)


def is_refines(relation: str) -> bool:
    return relation == REFINES
