"""共识 —— **合取，不是比例**。

---
这里是 DCE v2 唯一会撞上不变量 #5 的地方，所以先把判据钉死
----------------------------------------------------------

设计稿 §八 给的是：

    support(node) = 出现该节点的 View 数量 / 总 View 数量     （例子 support(X)=0.8）

而 §五·一 给的是：

    CONSENSUS(X)  ⇔  **所有**相关 View 都存在兼容结构

这两句不是一回事。**`support` 是「多少人说」，是频率，是流行度。**
arena `§C9` 不变量 #5 是 `Popularity = Evidence`；`§C7.1 ①` 把
「投票数 / 热度 / 参与量 / 曝光量」列为**禁止**信号，并把推荐定义写得很清楚：

    上层信号**不是「多少人说」，而是「是否在所有观点群里都成立」**。
    ……它的判定条件里就要求**同时**满足所有群，多数派的规模优势被抵消掉了。
    **它在结构上不可能违反 #5，不需要靠人工检查去守。**

所以本模块把 `§C7.1` 的道理照搬过来：

    CONSENSUS(u)  ⇔  u 出现在**全部**输入视图里          （support == (n, n)）
    support(u)    =  (出现了几个, 一共几个)              —— **描述性事实，仅此而已**

**没有阈值，没有「相关视图」这一层过滤。**
设计稿说「所有**相关** View」——「相关」是个没说清的限定词，它一旦落地就是一条线，
而 `§T0.3` 写着：「不得为观测点提具体阈值……没有基线数据的阈值一律是拍脑袋」。
MVP 规模下 `§C7.1` 自己也说「不存在观点群，本机制全程休眠」，所以 MVP 里
**相关 = 全部**，没有别的东西可选。

---
三条不许
--------

1. **`support` 不许当排序键。** `support_table()` 按 **key** 排序，不按 support。
   按 support 排就是把「多少人说」变成了「什么重要」，那正是 #5 要防的。
2. **`support` 不许写进源视图。** `§C7.1 ④`：上层结果不得写入底层任何字段。
3. **`support` 不许出现在派生单元的字段里当「强度 / 置信度 / 分数」。**
   它只出现在 `support` 这一个键下，且是 `(n_present, n_total)` 的**元组**，
   不是比例浮点数 —— 元组不容易被顺手拿去比较大小。
"""

from __future__ import annotations

from core import provenance as prov


def units_of(view) -> set:
    """一个视图里的全部结构单元。

    节点是 `("node", id)`，边是 `("edge", (from, to, relation))` ——
    边带上三元组，因为 §九 规定身份就是这三项。
    """
    out = set()
    for n in view["nodes"]:
        out.add(("node", n))
    for e in view["edges"]:
        out.add(("edge", (e["from"], e["to"], e["relation"])))
    return out


def universe(views) -> set:
    """所有视图出现过的单元的并集。**按 key 排序返回列表**（不是按出现次数）。"""
    u = set()
    for v in views:
        u |= units_of(v)
    return set(sorted(u, key=lambda x: (x[0], str(x[1]))))


def support(views, unit) -> tuple:
    """`(出现了几个视图, 一共几个视图)`。**描述性事实。**

    刻意返回**元组而不是比例**：比例是个数，会被顺手拿去过阈值或排序；
    元组只回答「谁有、谁没有」，那才是这个量真正的内容。
    """
    n = sum(1 for v in views if unit in units_of(v))
    return (n, len(views))


def present_in(views, unit) -> list:
    """有它的视图 id，排序（**按 id 排，不按任何权重**）。"""
    return sorted(v["id"] for v in views if unit in units_of(v))


def absent_in(views, unit) -> list:
    """没有它的视图 id，排序。"""
    return sorted(v["id"] for v in views if unit not in units_of(v))


def sources_for(views, unit) -> list:
    """把它出现过的每一处都变成溯源指针。"""
    kind, key = unit
    return prov.make(*[prov.ref(v["id"], kind, key)
                       for v in views if unit in units_of(v)])


def support_table(views) -> list:
    """全部单元的 `support` 清单。**按 key 排序，绝不按 support 排序。**

    这一条是 #5 的可执行形式之一：一个按 support 排过序的表，哪怕只排一次，
    就已经把「多少人说」交付成了「什么重要」。
    """
    rows = []
    for u in sorted(universe(views), key=lambda x: (x[0], str(x[1]))):
        kind, key = u
        rows.append({
            "unit": {"kind": kind, "key": key},
            "support": support(views, u),
            "present": present_in(views, u),
            "absent": absent_in(views, u),
        })
    return rows


def consensus(views) -> list:
    """**出现在全部视图里**的单元。合取，没有阈值。

    返回的每一项都带溯源，且 `§C9 #9` 要求它非空 ——
    consensus 的溯源是「每个视图各一处」，天然非空。
    """
    from core import view as V
    V.check_distinct(views)
    out = []
    for u in sorted(universe(views), key=lambda x: (x[0], str(x[1]))):
        n, total = support(views, u)
        if n != total:
            continue
        kind, key = u
        out.append({
            "type": "consensus",
            "unit": {"kind": kind, "key": key},
            "support": (n, total),
            "sources": sources_for(views, u),
        })
    return out
