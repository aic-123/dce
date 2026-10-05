"""公开数据：CLIMATE-FEVER（气候主张 × 证据片段 × **五个独立标注者**）。

来源：`tdiggelm/climate-fever-dataset` · `dataset/climate-fever.jsonl`
3,152,039 字节 / 1,535 个 claim / 7,675 条 evidence。
论文 Diggelmann et al., 2020, *CLIMATE-FEVER: A Dataset for Verification of
Real-World Climate Claims*。CC BY-SA 4.0。

---
⭐ 为什么这份数据比 Perspectrum 还合
----------------------------------

Perspectrum 的视角簇是**数据集预先聚好的**；而这份数据的 `votes`
是**五个独立标注者各自对同一条 evidence 的原始判断**：

    votes = ["SUPPORTS", "NOT_ENOUGH_INFO", null, null, null]

⇒ **视图不需要我构造 —— 它就在数据里。** 视图 = 标注者槽位，
边 = 该标注者主张的关系。于是 DCE 的判据（**存在一个有序对，
在两个视图里挂了互斥的关系**）在这份数据上是可以**直接数出来**的：

    实测：**871 对** (claim, evidence) 上，一个标注者说 supports、
          另一个说 contradicts；分布在 **543 / 1535** 个 claim 上（35%）。
    而 `supports` / `contradicts` **本来就在** `core/edge.py` 的 `EXCLUSIVE_PAIRS` 里。

⚠️ **这是本仓库第一份自带真实类型化关系的材料** —— countries 与 Scaffold
都要把关系**拍平**成 `dce_untyped`（那是声明的损失）；这份不用。

---
⚠️ 接口映射里丢了什么（必须写出来）
--------------------------------

**一、分析单元 = 一个 claim。** 视图 = 五个标注者槽位，
   节点空间 = 该 claim + 它的 5 条 evidence。

    ⚠️ **槽位不是人。** 槽位 0 在这个 claim 与在另一个 claim 上**不是同一个人**，
       所以「标注者 0」**不能跨 claim 聚合**。跨 claim 求共识会得到一个
       无意义的「所有人都同意」。
       ⇒ 所以 1535 个 claim 是 **1535 次各自独立的分析**，不是一个大分析。
       **这是我做的取舍，不是数据天然的。**

**二、`NOT_ENOUGH_INFO` 与 `null` 被丢掉。** 它们是**不表态**，不是断言：

    实测投票分布：SUPPORTS 6,485 · REFUTES 3,776 · NOT_ENOUGH_INFO 8,225 · null 19,889

    ⚠️ 也就是说 **72% 的票被丢掉了**（28,114 / 38,375）。
       保留它们就得给「不表态」一种关系，而那会**凭空造出一种边**
       （§C9 #9：不许造无法追溯的结构）。⇒ **丢掉，但把数写在这里。**

**三、节点前缀是借的。** claim 与 evidence 的 id 都不合
   `^[a-z]{2,6}-\\d{4}$`，所以借 `claim` 与 `con`
   （与 `adapters/countries.py` / `adapters/perspectrum.py` 同一条路）。
   evidence 用 `EVIDENCE_OFFSET + claim_id*10 + 序号`，保证不撞。

**四、`source_kind` 记 `"human"`。** 这些是**众包人工标注**，
   不是模型或论文生成的 —— 与 Perspectrum 同一条理由。

**五、`evidence_id` 只留作标签。** 它是
   `"Extinction risk from global warming:170"` 这种带冒号的长串，
   进不了节点空间；`keep_labels=True` 时它进 `metadata["labels"]`。
"""

from __future__ import annotations

import json
import pathlib

from core import view as V

#: evidence 节点的 id 偏移。乘 10 再序号，因为一个 claim 恰好 5 条 evidence。
EVIDENCE_OFFSET = 40000

SUPPORT, CONTRADICT = "supports", "contradicts"
NOT_ENOUGH = "NOT_ENOUGH_INFO"

SOURCE_KIND = "human"

#: 丢掉的两种票，以及**为什么**（不是"没用的字段"）。
DROP = {
    "NOT_ENOUGH_INFO": "**不表态**不是断言。保留它就得给「不表态」一种关系，"
                       "而那会凭空造出一种边（§C9 #9）。",
    "null": "同上 —— 该标注者没投这一票。",
}

DATASET_NOTE = (
    "CLIMATE-FEVER（tdiggelm/climate-fever-dataset）。"
    "视图 = 五个**标注者槽位**（数据自带 votes）；节点空间 = 一个 claim + 它的 5 条 evidence。"
    "⚠️ 槽位不是人，不能跨 claim 聚合，所以每个 claim 是一次独立分析；"
    "⚠️ NOT_ENOUGH_INFO 与 null（72% 的票）被丢掉；"
    "⚠️ 节点前缀 claim/con 是借的。"
)


class ClimateFeverError(Exception):
    pass


def norm_vote(v) -> str:
    """把一票归一化成 `supports` / `contradicts` / `None`（不表态）。

    ⚠️ 本仓库在 Perspectrum 上栽过一次**大小写**：拿小写去比大写的数据，
    两边都是空集，于是报了一个**空跑的 0**。所以这里显式归一化，
    而且调用方的自检**必须先证明票被匹配上了**才报数。
    """
    if v is None:
        return None
    s = str(v).strip().upper()
    if s == "SUPPORTS":
        return SUPPORT
    if s == "REFUTES":
        return CONTRADICT
    return None                      # NOT_ENOUGH_INFO 与一切未知值


def load(path) -> list:
    """读 jsonl，返回原始行。**不改入参、不落盘。**"""
    p = pathlib.Path(path)
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    if not rows:
        raise ClimateFeverError(f"{p} 里没有条目 —— 空输入不是通过")
    return rows


def claims(rows) -> list:
    """`[(claim_id, claim_text, evidences)]`，按 claim_id 排。"""
    out = []
    for r in rows:
        cid = r.get("claim_id")
        ev = r.get("evidences") or []
        if cid is None or not ev:
            continue
        out.append((int(cid), r.get("claim", ""), ev))
    return sorted(out, key=lambda t: t[0])


def claim_node(cid: int) -> str:
    return f"claim-{cid:04d}"


def evidence_node(cid: int, j: int) -> str:
    return f"con-{EVIDENCE_OFFSET + cid * 10 + j:04d}"


#: 一个 claim 有几个标注者槽位（数据里恒为 5，但**不写死** —— 数据说了算）。
def n_slots(evidences) -> int:
    return max((len(e.get("votes") or []) for e in evidences), default=0)


def to_views(cid: int, claim_text: str, evidences, *,
             keep_labels: bool = False) -> list:
    """**视图 = 标注者槽位。** 返回 `n_slots` 个 view。

    每个视图只装该标注者**真的投了立场**的那些边。
    ⚠️ 某个标注者可能一条都没投 ⇒ 那个视图会是空的，而**空视图在这里是事实**
    （他确实什么都没说），不是错误。调用方要能容忍它。
    """
    cnode = claim_node(cid)
    nodes = {cnode: {"id": cnode}}
    labels = {}
    slots = n_slots(evidences)
    per_slot = [[] for _ in range(slots)]

    for j, e in enumerate(evidences):
        enode = evidence_node(cid, j)
        nodes[enode] = {"id": enode}
        if keep_labels:
            labels[enode] = str(e.get("evidence_id") or e.get("article") or "")[:120]
        votes = e.get("votes") or []
        for k in range(min(slots, len(votes))):
            rel = norm_vote(votes[k])
            if rel is None:
                continue             # 见 DROP 表
            per_slot[k].append({"from": cnode, "to": enode, "relation": rel})

    if keep_labels:
        labels[cnode] = str(claim_text or "")[:120]

    views = []
    for k, edges in enumerate(per_slot):
        md = {"slot": k, "group": f"claim-{cid:04d}"}
        if keep_labels:
            md["labels"] = dict(labels)
        # ⚠️ **视图的节点 = 它自己引用到的节点，不是并集。**
        #
        # 首版这里写成 `nodes=sorted(nodes)`（那个并集），于是**5 个视图的节点集合
        # 完全相同** ⇒ 「哪个单元出现在哪几个视图」**恒为常数** ⇒ 成员关系不携带
        # 任何信息 ⇒ **γ 恒等于 1**，而实测明明有 871 处矛盾。
        #
        # 那次 γ=1 看起来像**数据的性质**，其实是**我的映射**造出来的。
        # 本仓库既有约定（见 `adapters/perspectrum.py`）：视图只声明它引用到的节点。
        # ⇒ 一个标注者没提某条 evidence，那是**这个视图漏了它**（omission），
        #   而不是「它也在，只是没表态」。
        vnodes = sorted({cnode} | {e["to"] for e in edges}) if edges else []
        views.append(V.make_view(
            view_id=f"cf{cid:04d}-a{k}",
            source_ref=f"climate-fever:claim:{cid}:annotator:{k}",
            source_kind=SOURCE_KIND,
            nodes=vnodes,
            edges=edges,
            metadata=md,
        ))
    return views


def contradicting_pairs(evidences) -> set:
    """**互斥的有序对**：同一 (claim, evidence) 上，一个视图说 supports、
    另一个说 contradicts。

    ⚠️ 这是**独立于 `analysis/divergence.py` 的第二条数法** ——
    两条路给出同一个数才算数（本仓库的规矩）。
    """
    out = set()
    for j, e in enumerate(evidences):
        rels = {}
        for k, v in enumerate(e.get("votes") or []):
            r = norm_vote(v)
            if r is not None:
                rels.setdefault(r, []).append(k)
        if SUPPORT in rels and CONTRADICT in rels:
            out.add((j, tuple(rels[SUPPORT]), tuple(rels[CONTRADICT])))
    return out


def describe(rows=None, path=None) -> dict:
    """一句话的账：多少 claim / evidence / 票，以及**丢了多少**。"""
    if rows is None:
        rows = load(path)
    cl = claims(rows)
    n_ev = 0
    votes = {"supports": 0, "contradicts": 0, "NOT_ENOUGH_INFO": 0, "null": 0}
    n_conf = 0
    n_pair = 0
    for cid, _t, ev in cl:
        n_ev += len(ev)
        for e in ev:
            for v in (e.get("votes") or []):
                if v is None:
                    votes["null"] += 1
                elif str(v).strip().upper() == "SUPPORTS":
                    votes["supports"] += 1
                elif str(v).strip().upper() == "REFUTES":
                    votes["contradicts"] += 1
                else:
                    votes["NOT_ENOUGH_INFO"] += 1
        cp = contradicting_pairs(ev)
        if cp:
            n_conf += 1
            n_pair += len(cp)
    total = sum(votes.values())
    dropped = votes["NOT_ENOUGH_INFO"] + votes["null"]
    return {
        "n_claims": len(cl), "n_evidence": n_ev, "votes": votes,
        "n_votes": total,
        "dropped": dropped,
        "dropped_share": (dropped / total) if total else None,
        "claims_with_contradiction": n_conf,
        "contradicting_pairs": n_pair,
        "note": DATASET_NOTE,
    }
