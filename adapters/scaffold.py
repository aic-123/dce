"""Scaffold → `Structured View`。**只借它的思想：一个共享的结构空间。**

---
先更正设计稿 §十八 的四处事实错误
--------------------------------

设计稿 §十八 声明 Scaffold 提供六项：`Node / Edge / Situation / Cue / Source /
Evidence Status`。逐条核对真实仓库（`SPEC.md` / `schema/node.schema.yaml` /
`validate.py`）：

| 设计稿声明 | 实际 |
|---|---|
| Node | **有**。11 个字段 `id type title aliases cues scope source evidence_status relations filled_by notes`，`SPEC.md:38` 明文「不得增删、不得改名」 |
| Edge | **没有**。`relations` 是 `list[str]` 的节点 id，**无种类、无方向元数据**；方向只有正文约定且明文不校验（`README.md:46-47`「方向对不对，它查不了，也不打算查」） |
| Situation | **没有**。`cues` 是情境索引（`list[str]`），是「调用的真正入口」，但**没有 Situation 实体** |
| Source | 有**字段**，但没有实体；且**一篇节点只有一个 source 槽位**（不是多来源） |
| Evidence Status | 有。`evidence_status` 的取值域是封闭的，其中 `已验证` 只能在 hook 里写 |
| Cue | 有。就是 `cues` |

所以这个 adapter 翻译的是**一篇节点的集合**，不是「Scaffold 的图」。

---
⚠️ 这个 adapter 有一处**结构性**损失，不能不说
--------------------------------------------

**Scaffold 的关系没有种类，所以从 Scaffold 出来的视图不可能产生 `contradiction`。**

矛盾的定义是「同一对端点上，两个视图给出**被声明为互斥**的两种 relation」。
没有种类就没有互斥可言 —— 这不是实现不到位，是数据形状的事实。

所以本 adapter：

1. 把不带种类的 `relations` 映射到 `SCAFFOLD_UNTYPED`（`"dce_untyped"`），
   **一个本层声明的占位种类**，不是从上游借来的词。
   ⚠️ 上一版这里复用 `related_to`，理由是「不新造词」—— 但 `related_to`
   属于 `SPEC_ONLY_KINDS`（arena 产品代码从不产生它），复用它等于把
   「本层声明的占位符」伪装成「上游给的一个种类」。
2. `can_produce` 里**不含** `contradiction`，并且这个声称过 `check_can_produce`。
3. 丢掉 `evidence_status` —— 它是真值判断（`§C9 #3`「AI 生成内容直接成为 verified」、
   `#7`「Evidence 自带固定 truth score」），**不是 DCE 该消费的东西**。
"""

from __future__ import annotations

from core import edge as E
from core import node as N
from core import view as V

from . import Adaptation, check_can_produce, derived_can_produce

# 只借「共享结构空间」这个思想：节点有 id、有类型前缀、有指向别的节点的引用。
# 不借它的 11 字段（那是 Scaffold 的合规问题，不是 DCE 的问题）。
EXPECTED_FIELDS = ("id", "relations")

# 明确**丢掉**的字段及理由。丢掉的东西要能逐条说清，否则就是假装读到了。
DROP = {
    "title": "正文，DCE 只处理结构不处理内容（§七：不做 semantic alignment）",
    "aliases": "同上，别名归并是 alignment 层的事",
    "cues": "情境索引，属于激活层，不属于结构差分",
    "scope": "适用范围。⚠️ Scaffold 里它是「必须同时写清不适用」，与 DCE 的同名概念不同义",
    "source": "取出来当视图的 source.ref，不进节点",
    "evidence_status": "**真值判断**，§C9 #3 / #7 禁止 DCE 消费",
    "filled_by": "填充者身份，会诱导权威排序（§二十）",
    "notes": "自由文本",
}


def to_view(view_id: str, nodes: list, *, source_ref: str = "scaffold://unknown",
            source_kind: str = "scaffold") -> Adaptation:
    """把一组 Scaffold 形状的节点翻成一个 `Structured View`。

    `nodes` 是最小的、只表达「共享结构空间」这个思想的数据：
    每项至少要有 `id` 与 `relations`。其余字段按 `DROP` 丢掉并逐条记账。
    """
    ids, edges, dropped_seen = [], [], set()
    for n in nodes:
        if not isinstance(n, dict) or "id" not in n:
            raise ValueError(f"Scaffold 节点必须是带 id 的字典，收到 {n!r}")
        nid = n["id"]
        N.check_id(nid)                       # 形状与前缀照抄 Scaffold
        ids.append(nid)
        for other in (n.get("relations") or []):
            N.check_id(other)
            # ⚠️ 无种类 → 本层声明的占位种类，**方向是 Scaffold 的正文约定**，
            # 而那个约定明文不校验。所以这里的方向只是「照抄引用关系」，
            # 不声称它是语义方向。
            edges.append((nid, other, E.SCAFFOLD_UNTYPED))
        for k in n:
            if k not in EXPECTED_FIELDS and k not in DROP:
                dropped_seen.add(f"未预期的字段 {k!r}（也丢掉了）")

    # 边要自足：Scaffold 的 relations 可以指向本次没给的节点，
    # 而视图必须是个自足子图（悬空引用会让「谁有这条边」算不出来）。
    have = set(ids)
    dangling = sorted({x for e in edges for x in (e[0], e[1])} - have)
    edges = [e for e in edges if e[0] in have and e[1] in have]

    view = V.make_view(view_id=view_id, source_ref=source_ref,
                       # ⚠️ 回退值是 `"scaffold"` 而不是 `"other"` ——
                       # `SOURCE_KINDS` 是封闭集合，里面没有 `other`。
                       # 第一版把回退值写成 `"other"`，于是**每条**走回退的路径都抛，
                       # 而那看起来像 adapter 坏了，其实是白名单里没这个词。
                       source_kind=source_kind if source_kind in V.SOURCE_KINDS
                       else "scaffold",
                       nodes=sorted(have), edges=sorted(set(edges)))

    losses = [f"{k}：{why}" for k, why in DROP.items()
              if any(k in n for n in nodes)]
    if dangling:
        losses.append(f"指向本次未给出的节点、因而被丢掉的引用 {len(dangling)} 条："
                      f"{dangling[:5]}（视图必须是自足子图）")
    if E.SCAFFOLD_UNTYPED in {e["relation"] for e in view["edges"]}:
        losses.append(
            "**关系没有种类** —— Scaffold 的 relations 是 list[str]，"
            "所以这些边全部落在本层声明的占位种类 "
            f"{E.SCAFFOLD_UNTYPED!r} 上。后果：**这份视图不可能产生 contradiction**"
            "（矛盾的判据要求两种被声明为互斥的关系种类）"
        )
    losses.extend(sorted(dropped_seen))

    a = Adaptation(
        view=view,
        losses=losses,
        declares=[
            f"占位关系种类 {E.SCAFFOLD_UNTYPED!r} —— 上游没有种类，这是本层加的",
            "方向照抄 Scaffold 的 relations 引用，**不声称它是语义方向**"
            "（Scaffold 自己的方向约定明文不校验）",
            "节点 id 的形状与前缀映射照抄 Scaffold（`schema/node.schema.yaml`）",
        ],
        # 没有互斥的种类 → 不可能有矛盾。这是形状的事实，不是实现限制。
        # ⚠️ 这里**不写死**，由实际吐出的种类推出来 —— 见 `derived_can_produce`。
        can_produce=derived_can_produce({e["relation"] for e in view["edges"]}),
    )
    check_can_produce(a)
    return a


def from_corpus_files(paths, view_id: str = "SC") -> Adaptation:
    """从 Scaffold 形状的 JSON 文件读一批节点。**只读，不写。**

    这是给 rl-scaffold 那类「Scaffold 的一次实际应用」用的入口：
    它有一批真节点（36 节点 / 112 处境句）。读取是安全的，
    因为这个 adapter **从不回写**（`§C7.1 ④` 单向性）。
    """
    import json
    from pathlib import Path
    nodes, refs = [], []
    for p in paths:
        p = Path(p)
        data = json.loads(p.read_text(encoding="utf-8"))
        items = data if isinstance(data, list) else data.get("nodes", [data])
        for it in items:
            if isinstance(it, dict) and "id" in it:
                nodes.append(it)
        refs.append(str(p))
    a = to_view(view_id, nodes,
                source_ref="scaffold://" + ",".join(Path(r).name for r in refs)[:120],
                source_kind="scaffold")
    a.declares.append(f"来源文件 {len(refs)} 个")
    return a
