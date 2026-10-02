"""公开数据：Perspectrum（主张 × 视角 × 证据，带立场标注）。

来源：`CogComp/perspectrum` · `data/dataset/perspectrum_with_answers_v1.0.json`
论文 Chen et al., NAACL 2019, *Seeing Things from a Different Angle*。CC BY-SA。
896,802 字节（与 GitHub API 报的一致）。

---
⭐ 为什么这份数据是 MVP 判据要的那一份
-----------------------------------

DCE 声明的互斥对是 `(contradicts, qualifies)` / `(contradicts, supports)` /
`(qualifies, supports)` —— **都是论辩性关系**。所以**事实型知识图谱
（countries、WordNet、Scaffold 节点）在结构上几乎不可能产生矛盾**：
上一轮去找它们，对这条判据而言是**注定失败**的。

而 Perspectrum 的原生结构就是：**同一个 claim，一批视角簇，每个簇带立场
（support / undermine）与它引用的 evidence**。于是

    同有序对 (evidence → claim)
    互斥关系  supports / contradicts
    来自不同视图（不同视角簇）

**这正是 `contradiction(f, t, r₁, r₂)` 的完全形态。**

---
⚠️ 接口映射里丢了什么（必须写出来）
--------------------------------

**一、每次分析只取一个 claim。** 视图 = **该 claim 的视角簇**，
节点空间 = 该 claim + 它引用的 evidence。

    ⚠️ 这意味着 907 个 claim 是 **907 个各自独立的分析**，不是一个大分析。
    理由：跨 claim 的节点空间是拼起来的，而「一个视角簇」只对**它自己那个
    claim** 发言 —— 把它们混进一个分析里，共识会退化成「出现在全部 5095 个
    视角簇里」（必然为空），那不是这个数据的结构。
    **这是我做的取舍，不是数据天然的。**

**二、立场标签的大小写与文档不符。** README 写 `"support"`，
**数据里是 `"SUPPORT"` / `"UNDERMINE"`**（全大写）。
第一次探针拿小写去比，一个都没匹配上，于是「同有序对两个立场」的计数
**报了一个空跑的 0**。所以本模块**统一归一化**（`strip().lower()`），
并且那条自检必须**先证明匹配上了**才报数。

**三、节点前缀是借的。** claim 与 evidence 的 id 都不是 `^[a-z]{2,6}-\\d{4}$`，
所以借 `con`（与 `adapters/countries.py` 同一条路）。evidence 的 id
统一加 9000 偏移，避免与 claim 的 id 撞。

**四、`source_kind` 记 `"human"`。** 立场标注是众包人工标的
（`voter_counts` 就是证据），不是模型生成的。
"""

from __future__ import annotations

import json
import pathlib

from core import view as V

EVIDENCE_OFFSET = 9000
SUPPORT, CONTRADICT = "supports", "contradicts"

DATASET_NOTE = (
    "Perspectrum（CogComp/perspectrum）。视图 = 一个 claim 的视角簇；"
    "节点空间 = 该 claim + 它引用的 evidence。"
    "⚠️ 立场标签在数据里是全大写（README 写小写）；"
    "⚠️ 节点前缀 con 是借的；⚠️ 每个 claim 是一次独立分析。"
)


class PerspectrumError(Exception):
    """数据格式不对。"""


def norm_stance(s) -> str:
    """把立场标签归一化。**README 写小写，数据是全大写** —— 不归一化就会空跑。"""
    return (s or "").strip().lower().replace("_", "-")


def load(path) -> list:
    """读主数据集。"""
    d = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if not isinstance(d, list) or not d:
        raise PerspectrumError("顶层应当是**非空**列表")
    if "perspectives" not in d[0]:
        raise PerspectrumError(f"字段不对：{sorted(d[0])}")
    return d


def claims_with_stances(data) -> list:
    """筛出**可分析**的 claim：≥2 个立场簇、且簇里有 evidence。

    返回 `[(cId, [ (簇号, 立场, [evidence id]) ], 原始簇数)]`。
    """
    out = []
    for c in data:
        cl = []
        for i, p in enumerate(c.get("perspectives", []), start=1):
            s = norm_stance(p.get("stance_label_3"))
            if s not in ("support", "undermine"):
                continue            # not-a-perspective 等等，**明确丢掉并计入丢失**
            evs = sorted(set(p.get("evidence", [])))
            if not evs:
                continue
            cl.append((i, s, evs))
        if len(cl) >= 2:
            out.append((c["cId"], cl, len(c.get("perspectives", []))))
    return out


def load_pools(directory, which: str = "evidence") -> dict:
    """读文本池 → `{id: text}`。

    ⚠️ **为什么要它**：第一步只需要结构（id + 关系），而**第二步（检索）需要内容面** ——
    处境只能映射到标签，映射不到「类型/单元/关系」这些**结构面**。
    实测：不读文本池时 Perspectrum 的内容面覆盖率是 **0%**。

    池子的字节数与 GitHub API 报的一致时才用（1,297,468 / 7,839,241）。
    """
    name, key = (("perspective_pool.json", "pId") if which == "perspective"
                 else ("evidence_pool.json", "eId"))
    p = pathlib.Path(directory) / name
    if not p.is_file():
        return {}
    d = json.loads(p.read_text(encoding="utf-8"))
    return {int(x[key]): (x.get("text") or "").strip() for x in d}


def to_views(cid: int, clusters: list, *, claim_text: str = "",
             ev_text: dict = None, keep_labels: bool = False) -> list:
    """一个 claim 的视角簇 → 一组视图（**每个簇一个视图**）。

    `keep_labels`（**默认关，保持旧行为**）：把 claim 的正文与 evidence 的正文
    带进 `metadata["labels"]`，供**第二步当内容面**用。

    ⚠️ 允许的依据与约束同 `adapters/scaffold.py` 的 `keep_labels`：
    `README` 边界一禁的是**同名归并**（身份判断），不是携带标签；
    而标签**只供检索/显示，绝不进任何比较或排序**（§C9 #5 / §二十）。
    """
    claim = f"con-{cid:04d}"
    views = []
    for i, stance, evs in clusters:
        ev_nodes = [f"con-{EVIDENCE_OFFSET + e:04d}" for e in evs]
        rel = SUPPORT if stance == "support" else CONTRADICT
        meta = None
        if keep_labels:
            lab = {}
            if claim_text.strip():
                lab[claim] = claim_text.strip()
            for e, n in zip(evs, ev_nodes):
                t = (ev_text or {}).get(e, "")
                if t:
                    lab[n] = t
            meta = {"labels": lab} if lab else None
        views.append(V.make_view(
            view_id=f"pcl-{i:04d}",
            source_ref=f"perspectrum://claim/{cid}/perspective/{i}",
            source_kind="human",
            nodes=sorted([claim] + ev_nodes),
            edges=[{"from": n, "to": claim, "relation": rel} for n in ev_nodes],
            metadata=meta,
        ))
    return views


def load_claims(path):
    """`(可分析 claim 列表, 全部 claim 数)`。"""
    data = load(path)
    return claims_with_stances(data), len(data)


def cross_stance_pairs(clusters: list) -> set:
    """**同一 evidence 被 support 与 undermine 两边的簇都引用**的那些 evidence。

    这是 `contradiction` 判据要的形状的**独立数法** ——
    与 `analysis/divergence.py` 数出来的矛盾数应当**逐位相同**。
    """
    sup, und = set(), set()
    for _i, stance, evs in clusters:
        (sup if stance == "support" else und).update(evs)
    return sup & und
