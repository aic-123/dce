"""公开数据库：`countries` 三视图（S1 / S2 / S3）。

---
这是第一份**不是我自己造**的多视图材料
------------------------------------

前面的材料只有两种：合成的（`generators/`）与作者写的（`positions.py`）。
而「合成语料上有效」这句话，本仓库已经吃过一次亏 ——
`recall 1.000` 曾经是**自选语料**的产物。

所以这一份来自公开仓库：

    villmow/datasets_knowledge_embedding
      └── other/countries/{countries_S1,countries_S2,countries_S3}/train.txt

    TSV：`实体 \t 关系 \t 实体`，两种关系 `locatedin` / `neighbor`
    三份的 test/valid 是**同一个 blob**（sha 相同），train **各不相同**
    字节数：31,885 / 30,266 / 28,238（与 GitHub API 报的一致 —— 免费的一致性校验）

⭐ **它的形状正是 DCE 要的**：同一个节点空间上的三个视图，
结构部分重叠、部分不同。

---
⚠️ 接口映射里**丢掉了什么**（必须写出来，不许静默）
------------------------------------------------

**一、关系种类被压平。** 源数据有两种关系（`locatedin` / `neighbor`），
而 DCE 的 `KNOWN_KINDS` 里没有对应物。一律映射成 `dce_untyped`
（那是本层声明的「未类型化」出口，与 `adapters/scaffold.py` 的
`SCAFFOLD_UNTYPED` 是同一条路）。

    **这个映射丢掉了两种关系的区别。** 原文保留在
    `metadata["source_triples"]` 里，一个字都没丢，但**DCE 看不到那个区别**。

⚠️ 后果要说明白：**`contradiction` 这一类在这份材料上必然是 0 条**，
因为矛盾判据要求「同一声明互斥集里的两种关系」（`core/edge.py` 的
`EXCLUSIVE_PAIRS`），而这里所有边都是同一种 `dce_untyped`。
**这不是实现的毛病，是映射的代价。**

**二、节点前缀是借的。** 国家名不是 `^[a-z]{2,6}-\\d{4}$`，而 `cty` 这种自造前缀
被 `core/node.py` 的严格校验**直接拒绝**（前缀必须在 Scaffold 的类型映射里）。
所以按**排序后**的实体名分配 `con-NNNN`（`con` = 概念），
并**把原名放进 `metadata["labels"]`**。

    ⚠️ 于是「一个国家」在这份材料里被当成 Scaffold 的 `con` 节点 ——
    **那是一个借来的类型，不是源数据的类型。**

⚠️ **三、`source_kind` 记 `"paper"` 而不是 `"experiment"`。**
这一栏应当说「这个视图是从哪儿来的」；源数据是公开发表的数据集，
不是本层的实验产物。`SOURCE_KINDS` 里没有「数据集」这一档，
取最接近的 `"paper"`，**并把这一点写在这里而不是让它看起来天然如此**。
"""

from __future__ import annotations

import pathlib

from core import provenance as prov
from core import view as V

#: 三份视图的 id（= 源目录名的后缀）
VIEW_IDS = ("S1", "S2", "S3")

#: 源数据里的两种关系。**本层给不出对应物**，所以一律压成 `dce_untyped`。
SOURCE_RELATIONS = ("locatedin", "neighbor")

#: 源数据里的 `source_kind` 没有对应档；取最接近的，并在此声明。
SOURCE_KIND = "paper"

DATASET_NOTE = (
    "公开数据集 villmow/datasets_knowledge_embedding 的 other/countries/。"
    "三份 train.txt 是同一个节点空间上的三个视图；test/valid 三份相同。"
    "⚠️ 关系种类被压平成 dce_untyped（丢掉了 locatedin / neighbor 的区别）；"
    "⚠️ 节点前缀 con 是**借来的**（源数据是国名，不是 Scaffold 概念）；"
    "⚠️ source_kind 记 paper 是取最接近的一档，源数据是数据集不是论文。"
)


class CountriesError(Exception):
    """源数据格式不对。"""


def parse_tsv(text: str) -> list:
    """`实体 \\t 关系 \\t 实体` → `[(from, to, relation)]`，**按三元组排序去重**。

    ⚠️ 不是所有源数据的行都规整：行数、列数、空行都要当**错误**报出来，
    不许静默丢行 —— 丢了行，分歧数就会**看起来变少**，而那看起来像「更一致」。
    """
    triples, bad = [], []
    for i, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 3 or not all(p.strip() for p in parts):
            bad.append((i, line[:40]))
            continue
        a, r, b = (p.strip() for p in parts)
        if r not in SOURCE_RELATIONS:
            bad.append((i, f"未知关系 {r!r}"))
            continue
        triples.append((a, b, r))
    if bad:
        raise CountriesError(
            f"{len(bad)} 行不符合 `实体\\t关系\\t实体`：{bad[:3]} —— "
            "**丢行会让分歧数看起来变少，而变少看起来像「更一致」**")
    return sorted(set(triples))


def load(path) -> list:
    """读一份 train.txt。"""
    return parse_tsv(pathlib.Path(path).read_text(encoding="utf-8"))


def node_ids(triples_list) -> dict:
    """给全部出现过的实体分配 `con-NNNN`。

    ⚠️ 按**排序后的名字**分配，所以同一批实体在哪一份里都拿到同一个 id ——
    否则三份视图就不是同一个节点空间，整个分析都没有意义。
    """
    names = sorted({x for ts in triples_list for a, b, _r in ts for x in (a, b)})
    return {n: f"con-{i:04d}" for i, n in enumerate(names, start=1)}


def to_view(name: str, triples: list, ids: dict):
    """一份三元组 → 一个 DCE 视图。"""
    edges = [{"from": ids[a], "to": ids[b], "relation": "dce_untyped"}
             for a, b, _r in triples]
    nodes = sorted({x for e in edges for x in (e["from"], e["to"])})
    return V.make_view(
        view_id=name, source_ref=f"countries://{name}", source_kind=SOURCE_KIND,
        nodes=nodes, edges=edges,
        metadata={
            # 原名一个字都没丢 —— DCE 看不到，但人看得到
            "labels": {ids[n]: n for n in ids if ids[n] in set(nodes)},
            "source_triples": [[a, b, r] for a, b, r in triples],
            "dataset": DATASET_NOTE,
            # ⚠️ 三个视图是**同一个立场的三次抽样**，不是三个立场 ——
            # 所以群只有一个（见 analysis/consensus.py 的退化判据）。
            # 这一点由数据形状决定，不是我挑的。
            "group": "countries-geography",
        })


def load_dir(directory) -> tuple:
    """读一个目录下的三份 train.txt → `(views, ids)`。

    三份都用**同一张 id 表**（由三份的并集算出）—— 那是「共享节点空间」的落地。
    """
    d = pathlib.Path(directory)
    missing = [s for s in VIEW_IDS if not (d / f"countries_{s}.txt").exists()]
    if missing:
        raise CountriesError(f"缺文件：{missing}（目录 {d}）")
    all_triples = [load(d / f"countries_{s}.txt") for s in VIEW_IDS]
    ids = node_ids(all_triples)
    views = [to_view(s, ts, ids) for s, ts in zip(VIEW_IDS, all_triples)]
    return views, ids


def describe(views) -> list:
    """一句话概括每份视图。"""
    rows = []
    for v in views:
        rels = {}
        for a, b, r in v["metadata"]["source_triples"]:
            rels[r] = rels.get(r, 0) + 1
        rows.append((v["id"], len(v["nodes"]), len(v["edges"]), rels))
    return rows
