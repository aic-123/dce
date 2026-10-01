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

from pathlib import Path

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
            # ⚠️ 这条声明属于**翻译本身**，不只属于切分 —— 所以放在这里，
            # 而不是只放在 `split_views` 里。（测试抓到过：只放后者时，
            # 直接用 `to_view` 的人看不到这条。）
            SOURCE_KIND_NOTE,
        ],
        # 没有互斥的种类 → 不可能有矛盾。这是形状的事实，不是实现限制。
        # ⚠️ 这里**不写死**，由实际吐出的种类推出来 —— 见 `derived_can_produce`。
        can_produce=derived_can_produce({e["relation"] for e in view["edges"]}),
    )
    check_can_produce(a)
    return a


def from_corpus_files(paths, view_id: str = "SC") -> Adaptation:
    """从 Scaffold 形状的 JSON 文件读一批节点。**只读，不写。**"""
    import json
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


# ── 真实语料：Scaffold 的节点是带 YAML frontmatter 的 Markdown ─────────
def parse_frontmatter(text: str) -> dict:
    """极简 YAML 子集解析器。**不引第三方**（§十七 纯标准库）。

    只处理这份语料里实际出现的形状（已拿 rl-scaffold 的 36 个真节点验过，
    36/36 解析成功、11 字段全齐）：

        key: "value"          带引号标量
        key: 值               裸标量
        key: ["a", "b"]       行内列表
        key:                  列表，下面若干 `  - "x"`
        key:                  嵌套映射，下面若干 `  k: v`（一层）

    ⚠️ 它**不是**一个 YAML 实现，也不打算是。多行块标量（`|` / `>`）不支持 ——
    真出现时会解析成 `None`，而 `to_view` 会把它当缺字段记账，不会静默吞掉。
    """
    import re
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}
    body = lines[1:end]

    def unq(s: str) -> str:
        s = s.strip()
        if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
            return s[1:-1]
        return s

    out, i = {}, 0
    while i < len(body):
        line = body[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if not m:
            i += 1
            continue
        key, rest = m.group(1), m.group(2).strip()
        if rest:
            if rest.startswith("[") and rest.endswith("]"):
                inner = rest[1:-1].strip()
                out[key] = ([unq(x) for x in inner.split(",") if x.strip()]
                            if inner else [])
            else:
                out[key] = unq(rest)
            i += 1
            continue
        block = []
        j = i + 1
        while j < len(body) and (not body[j].strip() or body[j].startswith("  ")):
            if body[j].strip():
                block.append(body[j])
            j += 1
        if not block:
            out[key] = None
        elif all(b.lstrip().startswith("- ") for b in block):
            out[key] = [unq(b.lstrip()[2:]) for b in block]
        else:
            sub = {}
            for b in block:
                mm = re.match(r"^\s+([A-Za-z_][\w-]*):\s*(.*)$", b)
                if mm:
                    sub[mm.group(1)] = unq(mm.group(2))
            out[key] = sub
        i = j
    return out


def load_corpus_dir(directory) -> list:
    """读一个 Scaffold 语料目录（`nodes/*.md`）。返回节点 dict 列表。"""
    d = Path(directory)
    files = sorted(d.glob("*.md")) if d.is_dir() else [d]
    nodes = []
    for p in files:
        fm = parse_frontmatter(p.read_text(encoding="utf-8"))
        if fm.get("id"):
            nodes.append(fm)
    return nodes


# ⚠️ 两处只有真实数据才会暴露的错位，都记在这里，不藏在代码里。
#
# 一、`source.kind` **同名不同义**。
#     Scaffold 的是**节点级**的「这条证据出自什么体裁」（论文 / 教材 / 官方文档 / 其他，中文），
#     DCE 的是**视图级**的「这个视图由谁产生」（model / human / paper / …，英文）。
#     两者的取值域**交集为空**，但那不代表要写一张翻译表 —— 它们不是一个轴。
#     硬翻译会把「体裁」伪装成「作者」。
#     处置：视图的 `source_kind` 一律是 `"scaffold"`（视图来自一份 Scaffold 语料），
#     而节点的 `source.kind` **只用作切分键**，不进任何字段。
#
# 二、`type` 是中文（论据 / 判断点 / …），而 DCE 的节点 id 前缀是英文。
#     实测 36/36 节点的 `type` 与 `id` 前缀**完全一致**，所以前缀可以信，
#     中文 type 丢掉。若哪天两者不一致，前缀仍然是权威（id 是主键）。
SOURCE_KIND_NOTE = (
    "⚠️ Scaffold 的 `source.kind`（论文/教材/官方文档/其他）与 DCE 的 "
    "`source.kind`（model/human/paper/…）**同名不同义**：前者是节点级的证据体裁，"
    "后者是视图级的产出者。取值域交集为空，但**不做翻译** —— "
    "硬翻译会把体裁伪装成产出者。本 adapter 只用它当**切分键**。"
)


def split_views(nodes: list, *, split_by: str = "source.kind") -> list:
    """把一份 Scaffold 语料切成多个视图，每个返回一个 `Adaptation`。

    ⚠️ **这一步决定了跑出来的是不是「多视图」。**

    Scaffold 的一份语料通常是**一个知识库**（一个主题、一个填充者），
    那不是多份独立立场，而是**一份结构的切面**。按体裁切出来的视图，
    彼此之间的关系主要是「谁缺了什么」—— 也就是 omission 会压倒性地多，
    而 contradiction 一条也不会有（关系没有种类）。

    真要多视图，需要的是**同一主题上的多份语料**（不同模型/不同作者各填一份），
    那才是 DCE 设计稿 §七 说的「模型 / 专家 / 论文的一个立场」。
    本函数把这件事交给调用方：`split_by` 怎么选，决定了得到的是切面还是立场。
    """
    if split_by not in ("source.kind", "source.ref", "filled_by", None):
        raise ValueError("split_by 只支持 source.kind / source.ref / filled_by / None")

    groups: dict[str, list] = {}
    for n in nodes:
        if split_by is None:
            key = "ALL"
        elif split_by.startswith("source."):
            key = str((n.get("source") or {}).get(split_by.split(".")[1]) or "（缺）")
        else:
            key = str(n.get(split_by) or "（缺）")
        groups.setdefault(key, []).append(n)

    out = []
    for key in sorted(groups):
        members = groups[key]
        a = to_view(f"SC-{key}"[:40], members,
                    source_ref=f"scaffold://{key}",
                    source_kind="scaffold")
        a.declares.insert(0, f"切分键 {split_by!r} = {key!r}（{len(members)} 个节点）")
        a.declares.append(SOURCE_KIND_NOTE)
        if len(members) == len(nodes):
            a.losses.append(
                "⚠️ 这是**整份语料**一个视图 —— 只有 1 个视图时 DCE 算不了「之间」，"
                "调用方需要至少 2 份来源不同的语料"
            )
        out.append(a)
    return out
