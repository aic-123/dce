"""合成 —— `Consensus Structure + Divergence Structure + Provenance`（§十二）。

---
它是什么，以及它**不是**什么
---------------------------

它是**派生结构**（derived structure），不是 ground truth（设计稿 §二）。
所以它：

- **不改任何源视图**（§C7.1 ④ 单向性）——`build()` 只读入参，产出新对象
- **每一处都带溯源**（§C9 #9），且 `verify_synthesis()` 会拿源视图逐个核对
- **不含任何评分、权重、置信度、真值判定**（§C9 #1 / #4 / #7）

---
`provenance` 段里放什么
--------------------

放**输入视图的清单 + 每个视图的指纹**。理由有两个：

1. 指纹是 `§十五 Test 4（Interference）` 的唯一依据。把它记在合成结果里，
   「这份合成是从哪个版本的哪几个视图算出来的」就是**自证**的，
   不用回头去重新哈希源视图。
2. `§C9 #10`（覆盖历史状态而不留 revision）要求派生结构可版本化。
   视图指纹是版本的一半 —— 另一半是 DCE 自己的代码版本，那由 git 记。
"""

from __future__ import annotations

from core import provenance as prov
from core import view as V

from . import consensus as C
from . import divergence as D
from . import focus as F


def build(views) -> dict:
    """从一组视图算出合成结构。**只读入参。**"""
    V.check_distinct(views)

    cons = C.consensus(views)
    div = D.analyse(views)
    fx = F.foci(div)

    # 把焦点号附加到每条分歧记录上（新字典，不改原记录）
    focus_of = {}
    for f in fx:
        for u in f["units"]:
            focus_of.setdefault(str(u), f["focus"])
    flat = []
    for t in ("refinement", "contradiction", "alternative", "omission"):
        for r in div.get(t, []):
            rec = dict(r)
            rec["focus"] = _focus_for(rec, fx)
            flat.append(rec)

    nodes, edges = [], []
    for u in cons:
        kind, key = u["unit"]["kind"], u["unit"]["key"]
        if kind == "node":
            nodes.append(key)
        else:
            edges.append(tuple(key))

    return {
        "consensus": {
            "nodes": sorted(nodes),
            "edges": [list(e) for e in sorted(edges)],
            "records": cons,
        },
        "divergence": flat,
        "foci": fx,
        "provenance": {
            "views": [
                {"id": v["id"], "source": dict(v["source"]),
                 "fingerprint": V.fingerprint(v)}
                for v in sorted(views, key=lambda x: x["id"])
            ],
            "generated_by": "dce.analysis.synthesis",
            "n_views": len(views),
        },
    }


def _focus_for(record, fx) -> str | None:
    """这条记录落在哪个焦点里。找不到返回 `None`（那会让 `verify_synthesis` 报出来）。

    按**单元键**匹配，不按对象身份 —— 因为 `build()` 里给记录加 `focus` 字段时
    用的是新字典，身份已经不同了。
    """
    keys = set()
    if "unit" in record:
        keys.add(str((record["unit"]["kind"], record["unit"]["key"])))
    elif record["type"] == "contradiction":
        for rel in record["relations"]:
            keys.add(str(("edge", (record["from"], record["to"], rel))))
    else:
        for _vid, targets in record["views"].items():
            for x in targets:
                keys.add(str(("edge", (record["source"], x, record["relation"]))))
    for f in fx:
        if keys & {str(u) for u in f["units"]}:
            return f["focus"]
    return None


def verify_synthesis(syn, views) -> None:
    """把合成结构拿去和源视图对账。**这是 §C9 #9 的可执行形式。**

    四件事：

    1. 每个共识单元、每条分歧记录、每个焦点，`sources` 都非空
    2. 每条 `sources` 都指向真实存在的视图里真实存在的单元
    3. 共识里的每个单元**确实**出现在全部视图里（不是算错了）
    4. 每条分歧记录都指向了某个焦点（`focus` 不为 `None`）

    ⚠️ 第 3 条是「结论与源对账」，不是「结构检查」。少了它，
    一个把任意单元都标成共识的实现也能通过前两条。
    """
    for rec in syn["consensus"]["records"]:
        prov.verify_against(rec["sources"], views)
        kind, key = rec["unit"]["kind"], rec["unit"]["key"]
        unit = (kind, key)
        for v in views:
            if unit not in C.units_of(v):
                raise prov.ProvenanceError(
                    f"共识单元 {unit!r} 并不在视图 {v['id']!r} 里 —— "
                    "共识的定义是「出现在全部视图里」，这条不满足"
                )

    for rec in syn["divergence"]:
        prov.verify_against(rec["sources"], views)
        if rec.get("focus") is None:
            raise prov.ProvenanceError(
                f"分歧记录没有落进任何焦点：{rec.get('type')} / "
                f"{rec.get('unit') or (rec.get('from'), rec.get('to'))}"
            )

    for f in syn["foci"]:
        if not f["sources"]:
            raise prov.ProvenanceError(f"焦点 {f['focus']} 没有溯源")
        prov.verify_against(f["sources"], views)

    ids = [v["id"] for v in syn["provenance"]["views"]]
    if len(set(ids)) != len(ids):
        raise prov.ProvenanceError("provenance.views 里有重复的视图 id")


# ── 禁令的可执行形式（§T4.2 要求 B 类声明必须落成一条否证检查）──────────
#
# arena `§T4.2` 给的形式是：
#
#     声明：选了 X，它不违反 #4（Vote = Truth）
#     检查：<一条命令 / 一个断言> 证明产物里不存在 <该不变量禁止的东西>
#     例：  grep -rn 'total_score|verdict|truth_value' <输出结构定义> → 无命中
#
# 这里是同一个形状：合成结构里**不许出现**这些键。
FORBIDDEN_KEYS = (
    "score", "scores", "weight", "weights", "confidence", "truth",
    "truth_value", "verdict", "rank", "ranking", "importance",
    "priority", "probability", "certainty",
)


def forbidden_keys_in(obj, *, path: str = "$") -> list:
    """递归找出产物里出现的禁用键。空列表 = 干净。

    守的是 §C9 的 #1（不自动判定谁正确）/#4（Vote ≠ Truth）/#7（证据不带固定 truth score），
    以及 §C7.1 ④（上层不得把相关性判断固化成真值判断）。
    """
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in FORBIDDEN_KEYS:
                hits.append(f"{path}.{k}")
            hits.extend(forbidden_keys_in(v, path=f"{path}.{k}"))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            hits.extend(forbidden_keys_in(v, path=f"{path}[{i}]"))
    return hits
