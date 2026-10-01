"""arena → `Structured View`。**只借它的思想：类型化的关系 + 谁说了什么。**

---
借什么、不借什么
---------------

借的**思想**只有两条：

    一、关系是**类型化**的（`supports` / `contradicts` / `qualifies` …）——
        这是 DCE 的 `contradiction` 唯一的立足点
    二、同一份议题上会有**多个来源各自表达了结构** —— 这正是「多视图」的来源

**不借**它的表结构。arena 是**交互层**（`artifact` / `revision` / `relation` /
`event` / `seq`），DCE 是**视图层**。把交互层的字段搬进 `Structured View`，
DCE 就会变成 arena 的一次重新实现，而 §十九 划的那条边界会当场消失。

所以下面这张「丢掉什么」的清单，是**这个 adapter 最重要的部分**，
比它翻译了什么更重要。

---
⚠️ 节点 id 必须映射，而映射是**本层声明的**
----------------------------------------

arena 的实体前缀是 `topic/pos/claim/evid/arg/debate/vote/sub/mech/assume/cex/
carg/chal/ctx`；DCE 的节点 id 必须是 Scaffold 形状（`^[a-z]{2,6}-\\d{4}$`，
前缀取自 Scaffold 的九个类型）。

**这两个前缀集不一样，所以必须有一张映射表。** 这张表是 DCE 侧的接口决定 ——
不采用 arena 的前缀，也不要求 arena 改（那是改它的表结构）。
映射后的 id 按**排过序的输入**分配序号，所以是确定性的、无碰撞的，
并且整张表记在视图的 `metadata` 里（`metadata` 是视图白名单内的字段），
于是**翻译是可追溯的**，而不是一次有损的改名。

---
⚠️ 这里有一条**会改变结论**的取舍
--------------------------------

`can_produce` 包含 `contradiction` —— 因为 arena 的关系**有种类**，
而 `supports ⊥ contradicts ⊥ qualifies` 是声明过互斥的。

但注意：这与 `adapters/scaffold.py` 正好相反 —— **从 Scaffold 出来的视图
不可能产生矛盾，从 arena 出来的可以。** 同一份结构差分算法，输入形状不同，
能回答的问题就不同。这件事必须写在 adapter 的声明里，不能留给读者去猜。
"""

from __future__ import annotations

from core import edge as E
from core import view as V

from . import Adaptation, check_can_produce, derived_can_produce

# arena 的实体前缀 → DCE/Scaffold 的节点前缀。
#
# ⚠️ 这是**本层声明的映射**，不是从上游读来的。`claim` / `arg` 两边同名就直接对上；
# `pos` → `stance`、`evid` → `arg`、`mech`/`assume` → `cond`、`cex` → `case`、
# `chal` → `judge`、`topic`/`sub`/`debate` → `issue`、`ctx` → `con`。
TYPE_MAP = {
    "topic": "issue", "sub": "issue", "debate": "issue",
    "pos": "stance",
    "claim": "claim",
    "evid": "arg", "arg": "arg", "carg": "arg",
    "mech": "cond", "assume": "cond",
    "cex": "case",
    "chal": "judge",
    "ctx": "con",
    # ⚠️ `vote` **不映射** —— 见 DROP。
}

# 交互层的东西，一律丢掉。**这张表是本节的主体。**
DROP = {
    "vote": "投票实体。§C9 #4「Vote = Truth」、#5「Popularity = Evidence」—— "
            "DCE 的输入里不许出现票数，否则共识会退化成「多少人说」",
    "state": "生命周期状态（active/superseded…），交互层概念",
    "status": "同上",
    "origin": "来源标记（human/machine）。保留它会诱导权威排序（§二十），"
              "也会把「谁说的」变成「谁更可信」；DCE 只按**来源分组**，不按来源排序",
    "created_at": "时间戳 → 会变成新旧排序，而新旧不是结构",
    "revision": "修订历史。§C9 #10「覆盖历史状态而不留 revision」防的是**丢失**历史，"
                "但 DCE 不该消费它 —— 它要的是「此刻的结构」，不是修订序列",
    "parent_rev": "同上",
    "event": "事件流，交互层概念",
    "seq": "全局序号，交互层概念",
    "superseded_by": "被推翻的指针。消费它会引入「哪个版本更对」的判断",
    "payload": "事件载荷",
    "actor": "行为者。同上，保留它会把结构差分变成责任归属",
    "author": "作者。⚠️ 唯一例外见 `split_by`：**分组按它，排序绝不按它**",
}


def _map_id(atype: str, seq: int) -> tuple:
    """`(映射后的 id, 用的是哪个前缀, 是否新造前缀)`。"""
    mapped = TYPE_MAP.get(atype)
    if mapped is None:
        return None, None, False
    return f"{mapped}-{seq:04d}", mapped, True


def to_views(artifacts: list, relations: list, *,
             split_by: str = "author") -> list:
    """把 arena 形状的实体与关系切成**一组**视图，每个来源一份。

    `artifacts`：`[{"id","type","author"/"origin",...}]`（多出来的键按 `DROP` 丢）
    `relations`：`[{"kind","from_id","to_id",...}]`

    `split_by`：按哪个字段分组。**默认按作者分组**（「谁说的」是视图的来源），
    但它只用于**分组**，绝不用于排序或加权。
    """
    if split_by not in ("author", "origin"):
        raise ValueError("split_by 只支持 author / origin —— "
                         "按权威或按可信度分组不是 DCE 该做的事")

    # ① 丢掉 vote 实体，并把丢弃逐条记账
    kept, losses, votes = [], [], 0
    for a in sorted(artifacts, key=lambda x: (str(x.get("type")), str(x.get("id")))):
        if a.get("type") == "vote":
            votes += 1
            continue
        kept.append(a)
    if votes:
        losses.append(f"丢掉了 {votes} 个 vote 实体 —— {DROP['vote']}")
    unknown = {a.get("type") for a in kept} - set(TYPE_MAP)
    if unknown:
        losses.append(f"类型不在映射表里、因而整条丢掉的实体类型：{sorted(unknown)}")

    # ② 分配映射后的 id（确定性：按排序后的输入分配序号）
    id_map, counter, by_artifact = {}, {}, {}
    for a in kept:
        atype = a.get("type")
        if atype not in TYPE_MAP:
            continue
        prefix = TYPE_MAP[atype]
        counter[prefix] = counter.get(prefix, 0) + 1
        nid = f"{prefix}-{counter[prefix]:04d}"
        id_map[a["id"]] = nid
        by_artifact[a["id"]] = a

    # ③ 关系：只保留**产品代码真的会创建**的种类
    kept_rel, dropped_kinds = [], {}
    for r in relations:
        k = r.get("kind")
        if k is None or not E.is_product_kind(k):
            dropped_kinds[k] = dropped_kinds.get(k, 0) + 1
            continue
        if r.get("from_id") in id_map and r.get("to_id") in id_map:
            kept_rel.append((id_map[r["from_id"]], id_map[r["to_id"]], k))
    for k, n in sorted(dropped_kinds.items(), key=lambda kv: str(kv[0])):
        why = ("属于 SPEC_ONLY_KINDS —— 规格里有、产品代码从不产生"
               if k in E.SPEC_ONLY_KINDS else "未知种类")
        losses.append(f"丢掉了 {n} 条 kind={k!r} 的关系（{why}）")

    # ④ 按来源切视图。**只用于分组。**
    #
    # ⚠️ 分组里必须存**映射后**的 id。第一版存的是 arena 原 id，而 `kept_rel`
    # 里是映射后的 id，于是 `f in members` 永远不成立 —— **每个视图都是 0 边**。
    # 而五条边界检查全都通过了：它们验方向、验词汇、验词表，
    # **没有一条验「它到底产出东西了吗」。** 那是这次补上的第六条。
    groups: dict[str, list] = {}
    for oid, a in by_artifact.items():
        if oid not in id_map:
            continue
        src = str(a.get(split_by) or a.get("origin") or "unknown")
        groups.setdefault(src, []).append(id_map[oid])

    out = []
    for src in sorted(groups):                    # 按来源名排序，**不是按规模或权威**
        members = set(groups[src])
        edges = sorted({(f, t, k) for (f, t, k) in kept_rel
                        if f in members and t in members})
        # 只保留两端都在本视图里的边；节点收窄到被边碰到的那些（自足子图）
        nodes = sorted({x for e in edges for x in (e[0], e[1])})
        extra = sum(1 for (f, t, _k) in kept_rel
                    if (f in members) != (t in members))
        view = V.make_view(
            view_id=f"A-{src}"[:40],
            source_ref=f"arena://{src}",
            source_kind="arena",
            nodes=nodes, edges=edges,
            metadata={"adapter": "arena", "id_map": {k: v for k, v in id_map.items()
                                                     if k in members},
                      "split_by": split_by},
        )
        my_losses = list(losses)
        if extra:
            my_losses.append(f"跨来源的 {extra} 条关系被丢掉（两端不在同一来源里，"
                             "保留它会把「两个来源的分歧」偷换成「来源内部的结构」）")
        a_obj = Adaptation(
            view=view, losses=my_losses,
            declares=[
                f"节点 id 映射表（arena 前缀 → Scaffold 前缀）共 {len(id_map)} 条，"
                "记在视图 metadata 的 id_map 里 —— 本层声明，不采用 arena 的前缀",
                f"视图按 {split_by!r} 分组；**分组只用于切分，绝不用于排序或加权**",
                "关系种类只保留 arena 产品代码真的会创建的那 10 种",
            ],
            # ⚠️ 用 `view["edges"]`（已规范化的 dict），不是上面那个元组列表 ——
            # 传元组列表会在取 `e["relation"]` 时 TypeError，而那会穿到调用方，
            # 看起来像 adapter 坏了。
            can_produce=derived_can_produce({e["relation"] for e in view["edges"]}),
        )
        check_can_produce(a_obj)
        out.append(a_obj)
    return out


def drop_reasons() -> dict:
    """`DROP` 的只读副本。给文档与检查用。"""
    return dict(DROP)
