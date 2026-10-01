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


def build(views, radius: int = 0, focus_basis: str = "subject",
          consensus_rule: str = "singleton") -> dict:
    """从一组视图算出合成结构。**只读入参。**

    `consensus_rule` 选共识的**观点群**来源（见 `analysis/consensus.py`）：

        "singleton"  **每视图自成一群 → 退化成合取**（默认）
        "declared"   材料自己声明的（`metadata["group"]`）
        "refinement" 精炼闭包导出的
        "auto"       按优先级：声明 > 精炼 > 每视图一群

    ⚠️ **默认是 `"singleton"`，不是 `"auto"`** —— 这一条是**量出来的**：
    改成 `auto` 之后，`checks/corpus.py` 的 C2/C3 从 600/600 掉到 **456/600**，
    因为合成语料本来就**植入**精炼关系，于是共识被静默换成了分群版。
    而「DCE 的划分 == 并集+频率的划分」那三条不变量是**合取**的性质 ——
    **默认不许改行为**。要分群共识就显式要，而用了哪条规则记进溯源。

    `focus_basis` 选焦点的**依据**：

        "subject"  **按记录的主语分组**（默认）。不碰图结构，所以在
                   共享节点空间上不会塌成一团。见 `analysis/focus.py`。
        "reach"    按结构距离（旧依据）。`radius=0` 时是「共享节点」，
                   在共享节点空间上**恒为 1 个焦点** —— 保留是为了可复现旧结果。

    ⚠️ 默认值是 `"subject"` 而不是 `"reach"`，因为**产品不该用一个
    在预期输入上退化的依据**。改这个默认值之前，先看 `checks/focus.py`
    里三种依据的对照。
    """
    V.check_distinct(views)

    # ⚠️ 共识的**观点群**：`auto` 走优先级 —— 材料声明的 > 精炼导出的 > 每视图一群。
    # 用了哪条规则、分了几个群、救回几条单元，**都要记进溯源** ——
    # 换了分法产物就应当看得出换了（与 `focus_radius` 同一条规矩）。
    cons_groups, cons_rule = C.groups_for(views, consensus_rule)
    cons_diag = C.consensus_diagnostic(views, cons_groups)

    cons = C.consensus(views, cons_groups)
    div = D.analyse(views)
    if focus_basis == "subject":
        fx = F.subject_foci(div, "structure")
        # 二级：一级焦点**内部**的形式概念（多特征 + `Sep` 判据）。
        # ⚠️ 只带**会概括**的那些桶（`only_if_compresses`）—— 判据是
        # 「二级概念数 < 桶内记录数」，**结构性的，不是阈值**：
        # 立场材料上二级只是展开（0.9x），真实语料上它概括（7.7x）。
        from . import concepts as K
        lv2 = K.second_level(div, views, only_if_compresses=True)
    elif focus_basis == "reach":
        fx = F.foci(div, radius=radius, views=views)
        lv2 = []
    else:
        raise ValueError(f"未知的焦点依据 {focus_basis!r}，只认 subject / reach")

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
        # 二级只在**会概括**的桶上出现。空列表 = 这份材料上二级没意义
        # （那本身是结论，不是缺省）。
        "second_level": lv2,
        "provenance": {
            "views": [
                {"id": v["id"], "source": dict(v["source"]),
                 "fingerprint": V.fingerprint(v)}
                for v in sorted(views, key=lambda x: x["id"])
            ],
            "generated_by": "dce.analysis.synthesis",
            "n_views": len(views),
            # 半径是**显式记录**的：换了值，产物就应当看得出换了值
            "focus_radius": radius,
            "focus_basis": focus_basis,
            # 共识用了哪个群、怎么来的、救回几条 —— 同上
            "consensus_rule": cons_rule,
            "consensus_groups": [sorted(g) for g in cons_groups],
            "consensus_rescued": cons_diag["n_rescued"],
        },
        # 诊断（**这份材料的群结构能不能改变任何判定**）—— 它是一句可执行的判断
        "consensus_diagnostic": cons_diag,
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
