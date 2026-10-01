"""结构化视图（Structured View）—— DCE 的唯一输入单位。

---
它不是什么
----------

**不是「模型」**。设计稿 §三 改掉了「Model = 一张子图」：

    输入 DCE 的东西不一定是模型。可能是 LLM 输出、专家观点、Arena 里的一方立场、
    一篇论文、一个知识库、一个已有 Scaffold、一个实验结果、一个结构化推理结果。

所以统一叫 Structured View，**source.kind 只标注它出自哪一类**，不赋予它任何权重。

---
形状（照抄设计稿 §三）
--------------------

    view:
      id:       唯一标识
      source:   {ref, kind}          kind ∈ SOURCE_KINDS
      nodes:    [node_id, ...]
      edges:    [{from, to, relation}, ...]
      metadata: 可选

⚠️ **设计稿写的是 `edges: [edge_id]`，但 §九 要求 `edge_identity = (from, to, relation)`。**
两者只能有一个：边必须自带那三项，否则身份算不出来。所以这里 edges 是**三元组的列表**，
不是 id 的列表。这一点写在这里，是因为它是与设计稿字面的一处偏离。

---
规范化哈希：Test 4 的唯一依据
----------------------------

`§十五 Test 4（Interference）` 的判据是：

    hash(A_before) == hash(A_after)

所以哈希必须**只由内容决定**：键排序、节点排序、边排序、紧凑分隔符、UTF-8。
同一份视图无论从哪来、字典插入顺序如何，哈希必须相同 —— 否则 Test 4 红得没有意义
（它会在测「Python 字典的顺序」而不是「有没有被污染」）。

**只哈希结构性字段**：`id` / `source` / `nodes` / `edges` / `metadata` 之外的东西
（比如 `_derived`、`_scratch` 这类运行时附加物）**不进哈希**，但也不该存在 ——
`verify()` 会把白名单外的字段直接拦掉。白名单而非黑名单，这条抄自
`nested/pointer.py` 的做法（它的理由是「多出来的那个通常就是要防的东西」）。
"""

from __future__ import annotations

import hashlib
import json

# source.kind 的封闭集合（照抄设计稿 §三）。不认第四种。
SOURCE_KINDS = (
    "model",
    "human",
    "paper",
    "arena",
    "scaffold",
    "experiment",
)

# 视图允许出现的顶层字段。**白名单**：多一个就拦。
VIEW_FIELDS = ("id", "source", "nodes", "edges", "metadata")


class ViewError(Exception):
    """视图形状不对。消息面向调用方，说清违反了什么。"""


def make_view(*, view_id: str, source_ref: str, source_kind: str,
              nodes, edges, metadata=None) -> dict:
    """建一个视图并当场验。返回**新字典**，不改入参。

    ⚠️ 不改入参这一条是 DCE 原则 1 的最内层：调用方手里的东西归调用方。
    同源做法见 `nested/pointer.py:attach()`（"这一条与 `revise()` 不改旧版本同源"）。
    """
    view = {
        "id": view_id,
        "source": {"ref": source_ref, "kind": source_kind},
        "nodes": list(nodes),
        "edges": [_edge(e) for e in edges],
    }
    if metadata is not None:
        view["metadata"] = metadata
    verify(view)
    return view


def _edge(e) -> dict:
    if isinstance(e, dict):
        return {"from": e["from"], "to": e["to"], "relation": e["relation"]}
    if isinstance(e, (tuple, list)) and len(e) == 3:
        return {"from": e[0], "to": e[1], "relation": e[2]}
    raise ViewError(
        f"边必须是 {{from,to,relation}} 或三元组，收到 {e!r}。"
        "§九 规定 edge_identity = (from, to, relation)，三项缺一不可 —— "
        "少了 relation 就分不出「X supports Y」和「X contradicts Y」。"
    )


def verify(view) -> None:
    """形状不对就抛 `ViewError`。五条判据。

    1. 是字典，且顶层字段**只有**白名单里那些 —— 多一个就是「顺手挂了个评分/权重」。
    2. `id` 是非空字符串。
    3. `source` 是字典，有非空的 `ref`，`kind` 在封闭集合里。
    4. `nodes` 是字符串列表，**无重复**。
    5. `edges` 每一项的 `from`/`to` 都在 `nodes` 里，`relation` 是非空字符串。
    """
    if not isinstance(view, dict):
        raise ViewError(f"视图必须是字典，收到 {type(view).__name__}")

    extra = set(view) - set(VIEW_FIELDS)
    if extra:
        raise ViewError(
            f"视图顶层只许有 {list(VIEW_FIELDS)}，多出了 {sorted(extra)}。"
            "多出来的那个通常就是「顺手挂上的评分 / 权重 / 置信度」—— "
            "DCE 的输出是派生结构，不是真值（设计稿 §二：Consensus ≠ Truth）。"
        )
    for f in ("id", "source", "nodes", "edges"):
        if f not in view:
            raise ViewError(f"视图缺 {f}")

    if not isinstance(view["id"], str) or not view["id"].strip():
        raise ViewError(f"view.id 必须是非空字符串，收到 {view['id']!r}")

    src = view["source"]
    if not isinstance(src, dict):
        raise ViewError(f"source 必须是字典，收到 {type(src).__name__}")
    src_extra = set(src) - {"ref", "kind"}
    if src_extra:
        raise ViewError(f"source 只许有 ref / kind，多出了 {sorted(src_extra)}")
    if not isinstance(src.get("ref"), str) or not src["ref"].strip():
        raise ViewError("source.ref 必须是非空字符串 —— 「来源是谁」必须能指到外面")
    if src.get("kind") not in SOURCE_KINDS:
        raise ViewError(
            f"source.kind={src.get('kind')!r} 不在 {list(SOURCE_KINDS)} 里。"
            "它是封闭集合：kind 只标注出自哪一类，**不携带任何权重**。"
        )

    nodes = view["nodes"]
    if not isinstance(nodes, list) or any(not isinstance(n, str) for n in nodes):
        raise ViewError("nodes 必须是字符串列表（Scaffold 节点 id）")
    if len(set(nodes)) != len(nodes):
        dup = sorted({n for n in nodes if nodes.count(n) > 1})
        raise ViewError(f"nodes 有重复：{dup}。同一节点在一个视图里只能出现一次")

    known = set(nodes)
    for e in view["edges"]:
        if not isinstance(e, dict):
            raise ViewError(f"边必须是字典，收到 {type(e).__name__}")
        e_extra = set(e) - {"from", "to", "relation"}
        if e_extra:
            raise ViewError(
                f"边只许有 from / to / relation，多出了 {sorted(e_extra)}。"
                "多出来的那个通常就是「给这条边打了个分」—— §C9 不变量 #7 禁止"
                "证据自带固定 truth score。"
            )
        for f in ("from", "to", "relation"):
            if not isinstance(e.get(f), str) or not e[f].strip():
                raise ViewError(f"边的 {f} 必须是非空字符串，收到 {e.get(f)!r}")
        for f in ("from", "to"):
            if e[f] not in known:
                raise ViewError(
                    f"边引用了不在 nodes 里的节点 {e[f]!r}。"
                    "视图必须是自足的子图 —— 悬空引用会让「谁有这条边」算不准。"
                )


def canonical(view) -> str:
    """规范化 JSON：键排序、节点排序、边排序、紧凑分隔符、不转义非 ASCII。

    排序是为了**让哈希只由内容决定**，不由字典插入顺序决定（见模块 docstring）。
    """
    body = {
        "id": view["id"],
        "source": {"ref": view["source"]["ref"], "kind": view["source"]["kind"]},
        "nodes": sorted(view["nodes"]),
        "edges": sorted(
            (e["from"], e["to"], e["relation"]) for e in view["edges"]
        ),
        "metadata": view.get("metadata"),
    }
    body["edges"] = [list(x) for x in body["edges"]]
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fingerprint(view) -> str:
    """`hash(A_before)` —— Test 4（Interference）就是比这个。"""
    return hashlib.sha256(canonical(view).encode("utf-8")).hexdigest()


def clone(view) -> dict:
    """深拷贝成新对象。**派生层永远不改入参**，需要动就先 clone。"""
    out = json.loads(json.dumps(view, ensure_ascii=False))
    return out


def check_distinct(views) -> None:
    """输入视图的 id 必须**互不相同**。

    ⚠️ 这条是冒烟测撞出来的，不是一开始就有的：两个视图用同一个 id 时，
    溯源会指向同一个 id 两次，`provenance.verify()` 报「同一来源重复出现」——
    **报得很晚，而且报的是溯源的问题，不是输入的问题。**

    真正的问题是：溯源是按 **id** 指人的，id 一撞，「这个派生单元来自哪几个视图」
    就答不上来了，而那是 `§C9 #9` 的全部要求。所以必须在入口拦，
    而不是等溯源去撞。
    """
    seen = {}
    for i, v in enumerate(views):
        vid = v.get("id")
        if vid in seen:
            raise ViewError(
                f"输入视图的 id 重复：{vid!r}（第 {seen[vid] + 1} 个与第 {i + 1} 个）。"
                "溯源按 id 指人，id 一撞就无法回答「这个派生单元来自哪几个视图」——"
                "而那是 §C9 #9 的全部要求。id 必须互不相同。"
            )
        seen[vid] = i
    if len(views) < 2:
        raise ViewError(
            f"至少需要 2 个视图才能谈「之间」，收到 {len(views)} 个。"
            "1 个视图的「共识 / 分歧」是恒等式，没有信息。"
        )
