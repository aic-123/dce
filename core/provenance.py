"""溯源 —— 每个派生单元都必须能回答「你来自哪里」。

---
它守的是哪条不变量
------------------

`§C9 #9`：**禁止自动产生无法追溯的结构。**

这条不是「最好写一下来源」，是可以被机器检查的：

    任何派生单元（consensus / contradiction / alternative / omission / refinement / focus）
    的 `sources` 必须**非空**，且每一项都指向**真实存在的视图**里的**真实存在的单元**。

⚠️ **「有一个 sources 列表」不够。** 一个只写着
`{"sources": ["view_a"]}` 的派生单元看起来可追溯，其实指不到任何具体结构。
所以 `verify_against()` 会逐个核对：视图在不在、那个单元在不在。
核对不了的溯源等于没有溯源，只是长得像。

---
`§C7.1 ④` 单向性：溯源是**只读的指针**，不是回写的通道
-----------------------------------------------------

派生单元的 `sources` 指向源视图；**源视图里不许出现任何指向派生单元的东西**。
`§C7.1 ④` 说得很硬：

    底层 → 上层   派生，允许
    上层 → 底层   禁止写成事实

所以本模块只**生成指向下层的指针**，从不给源视图加字段。
Test 4（Interference）就是这条的可执行形式：写入派生结构之后，
`hash(A_before) == hash(A_after)`。

---
与 nested 的关系
---------------

`nested/pointer.py` 的 `target_of()` 有一句值得照搬的判断：

    刻意**不返回 selector 全文** —— 比较两个 selector 是否等价需要
    「同一版本的偏移」这种前提，而那是本层判断不了的事。

同理，本模块的 source ref **只到 `(view_id, kind, key)` 这一档**，
不携带源单元的正文、不携带它的任何评估结果。要内容去源视图取。
"""

from __future__ import annotations

# 可被溯源的单元种类。封闭集合 —— 派生单元只有这几种。
UNIT_KINDS = ("node", "edge", "focus")

# 派生单元的类型（= 产出它们的分析类型）。用于核对 sources 指向的 kind 是否说得通。
DERIVED_TYPES = (
    "consensus",
    "contradiction",
    "alternative",
    "omission",
    "refinement",
)


class ProvenanceError(Exception):
    """溯源不对。消息面向调用方。"""


def ref(view_id: str, kind: str, key) -> dict:
    """一个源引用：`(view_id, kind, key)`。

    `key`：node 用 id 字符串；edge 用 `(from, to, relation)` 三元组（§九）。
    """
    if kind not in UNIT_KINDS:
        raise ProvenanceError(f"单元种类 {kind!r} 不在 {list(UNIT_KINDS)} 里")
    if not isinstance(view_id, str) or not view_id.strip():
        raise ProvenanceError("view_id 必须是非空字符串")
    if kind == "edge":
        if not (isinstance(key, (tuple, list)) and len(key) == 3):
            raise ProvenanceError(
                f"edge 的 key 必须是 (from, to, relation) 三元组，收到 {key!r} —— "
                "§九 规定边身份是三元组，只写两个端点会丢掉方向与种类"
            )
        key = tuple(key)
    else:
        if not isinstance(key, str) or not key.strip():
            raise ProvenanceError(f"{kind} 的 key 必须是非空字符串，收到 {key!r}")
    return {"view": view_id, "kind": kind, "key": key}


def make(*refs) -> list:
    """建一组溯源。**至少一条** —— 空溯源是 §C9 #9 禁止的那种结构。"""
    out = [ref(r["view"], r["kind"], r["key"]) if isinstance(r, dict) else r
           for r in refs]
    verify(out)
    return out


def _sig(r) -> tuple:
    key = tuple(r["key"]) if isinstance(r["key"], (tuple, list)) else r["key"]
    return (r["view"], r["kind"], str(key))


def merge(*source_lists) -> list:
    """把多组溯源**并**起来，按签名去重。

    ⚠️ 与 `make()` 的区别是有意的，也是踩出来的：

        `make()`   建**一条**记录的溯源。同一个来源出现两次 → 报错（那是写重了）
        `merge()`  把**多条**记录的溯源并起来。同一个来源出现两次 → **正常**

    一条 omission 和一条 contradiction 完全可以引用同一处（同一个视图的同一条边）——
    它们说的是不同的事，只是都指着那里。

    第一版 `focus.foci()` 用 `make()` 去并多条记录的溯源，于是只要两条分歧碰到
    同一个来源就炸。**报得很晚，而且报的是溯源的问题，不是聚合的问题。**
    """
    seen = {}
    for lst in source_lists:
        for r in lst:
            rr = ref(r["view"], r["kind"], r["key"])
            seen[_sig(rr)] = rr
    out = [seen[k] for k in sorted(seen)]
    verify(out)
    return out


def verify(sources) -> None:
    if not isinstance(sources, (list, tuple)):
        raise ProvenanceError(f"sources 必须是列表，收到 {type(sources).__name__}")
    if not sources:
        raise ProvenanceError(
            "sources 是空的。§C9 #9 禁止自动产生无法追溯的结构 —— "
            "一个说不出自己从哪来的派生单元，不许进输出"
        )
    seen = set()
    for r in sources:
        if not isinstance(r, dict):
            raise ProvenanceError(f"source 项必须是字典，收到 {type(r).__name__}")
        extra = set(r) - {"view", "kind", "key"}
        if extra:
            raise ProvenanceError(
                f"source 项只许有 view / kind / key，多出了 {sorted(extra)}。"
                "多出来的那个通常是源单元的正文或评估结果 —— "
                "本层只存指针，要内容去源视图取"
            )
        for f in ("view", "kind", "key"):
            if f not in r:
                raise ProvenanceError(f"source 项缺 {f}")
        if r["kind"] not in UNIT_KINDS:
            raise ProvenanceError(f"source.kind={r['kind']!r} 不在 {list(UNIT_KINDS)} 里")
        if r["kind"] == "edge" and not (
                isinstance(r["key"], (tuple, list)) and len(r["key"]) == 3):
            raise ProvenanceError(f"edge 的 key 必须是三元组，收到 {r['key']!r}")
        sig = (r["view"], r["kind"],
               tuple(r["key"]) if isinstance(r["key"], (tuple, list)) else r["key"])
        if sig in seen:
            raise ProvenanceError(f"同一来源重复出现：{sig}")
        seen.add(sig)


def verify_against(sources, views) -> None:
    """逐个核对：视图在不在、那个单元在不在。

    ⚠️ 这是「溯源」与「看起来像溯源」的分界。只查 `sources` 非空的话，
    `{"sources": ["view_a"]}` 也能过 —— 而它指不到任何具体结构。
    """
    verify(sources)
    by_id = {v["id"]: v for v in views}
    for r in sources:
        vid = r["view"]
        if vid not in by_id:
            raise ProvenanceError(
                f"溯源指向不存在的视图 {vid!r}。现有视图：{sorted(by_id)}"
            )
        v = by_id[vid]
        if r["kind"] == "node":
            if r["key"] not in v["nodes"]:
                raise ProvenanceError(
                    f"溯源指向 {vid!r} 里不存在的节点 {r['key']!r}"
                )
        elif r["kind"] == "edge":
            keys = {(e["from"], e["to"], e["relation"]) for e in v["edges"]}
            if tuple(r["key"]) not in keys:
                raise ProvenanceError(
                    f"溯源指向 {vid!r} 里不存在的边 {tuple(r['key'])!r}"
                )
        elif r["kind"] == "focus":
            raise ProvenanceError(
                "focus 是派生单元，**不能**作为溯源的来源 —— "
                "溯源必须指到底层视图，指到另一层派生单元就成了自引用"
            )


def views_of(sources) -> list:
    """出现过的视图 id，排序去重。给「这个派生单元涉及哪几个视图」用。"""
    return sorted({r["view"] for r in sources})
