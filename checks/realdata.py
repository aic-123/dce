"""真实语料检查 —— 有就真跑，没有就**显式跳过**。

---
为什么要单独一个模块
-------------------

前面所有检查跑的都是合成语料。adapter 建好之后，第一件该做的事是
**拿真实数据跑一遍** —— 而合成数据永远测不出「同名不同义」这类错位：
真实语料里 `source.kind` 是中文的「论文/教材/官方文档/其他」，
而 DCE 的 `source.kind` 是英文的「model/human/paper/…」，**交集为空**。
那不是要写翻译表，是**两个字段根本不在一个轴上**（详见 `adapters/scaffold.py`）。

---
⚠️ 跳过不等于通过
----------------

语料库在仓库之外（`rl-scaffold` 的 `nodes/`），所以本模块**可能无可跑**。
`field/` 仓库在这件事上定过一条规矩，这里照搬：

    跳过要**显式报出来**，并与「通过」分开计数。

一个「语料不在就静默通过」的检查，与一条永远通过的检查，在输出上长得一样 ——
而这一整轮我们已经在这上面栽过两次（runner 从不调用度量组、
adapter 空输出通过全部边界检查）。

找语料的顺序：环境变量 `DCE_SCAFFOLD_CORPUS` → 几个候选相对路径。
"""

from __future__ import annotations

import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

CANDIDATES = (
    ROOT.parent / "rl-scaffold" / "nodes",
    ROOT.parent / "_aic_repos" / "rl-scaffold" / "nodes",
    Path.home() / "rl-scaffold" / "nodes",
)


def corpus_dir():
    """找真实语料目录。找不到返回 `None`（**这不是错误**）。"""
    env = os.environ.get("DCE_SCAFFOLD_CORPUS")
    if env:
        p = Path(env)
        return p if p.is_dir() else None
    for c in CANDIDATES:
        if c.is_dir() and any(c.glob("*.md")):
            return c
    return None


def _markdown_only(path: Path) -> bool:
    return path.is_dir() and any(path.glob("*.md"))


def run_real(directory=None) -> dict:
    """跑一遍真实语料。返回结果字典（含 `skipped` 标志）。"""
    from adapters import scaffold as SC
    from analysis import consensus as C
    from analysis import synthesis as S
    from metrics import compression as CMP

    d = Path(directory) if directory else corpus_dir()
    if d is None or not _markdown_only(d):
        return {"skipped": True, "why": "找不到真实 Scaffold 语料目录"}

    nodes = SC.load_corpus_dir(d)
    if not nodes:
        return {"skipped": True, "why": f"{d} 里没有解析出节点"}

    adaps = SC.split_views(nodes, split_by="source.kind")
    views = [a.view for a in adaps]
    if len(views) < 2:
        return {"skipped": False, "nodes": len(nodes), "views": len(views),
                "error": "按 source.kind 切不出 ≥2 个视图"}

    syn = S.build(views)
    unit_sets = [C.units_of(v) for v in views]
    inter = set.intersection(*unit_sets) if unit_sets else set()
    types = {}
    for r in syn["divergence"]:
        types[r["type"]] = types.get(r["type"], 0) + 1
    return {
        "skipped": False,
        "dir": str(d),
        "nodes": len(nodes),
        "views": len(views),
        "view_sizes": [(v["id"], len(v["nodes"]), len(v["edges"])) for v in views],
        "dangling": _dangling(nodes),
        "intersection": len(inter),
        "consensus": len(syn["consensus"]["records"]),
        "types": types,
        "foci": len(syn["foci"]),
        "compression": CMP.compression(views, syn)["all_modes"],
        "can_produce": {v["id"]: list(a.can_produce)
                        for a, v in zip(adaps, views)},
    }


def _dangling(nodes) -> int:
    ids = {n["id"] for n in nodes}
    return sum(1 for n in nodes for r in (n.get("relations") or []) if r not in ids)


def run_all() -> list:
    """能当断言用的三条。**语料不在时显式跳过，不算通过。**"""
    r = run_real()
    if r.get("skipped"):
        return [("真实语料检查", None, f"跳过 —— {r['why']}（**跳过不等于通过**）")]

    out = [
        ("真实语料：36 个节点全部解析、无悬空引用",
         r["nodes"] > 0 and r["dangling"] == 0,
         f"解析 {r['nodes']} 个节点，悬空引用 {r['dangling']} 条"),
        ("真实语料：按 source.kind 切出 ≥2 个视图",
         r["views"] >= 2,
         f"切出 {r['views']} 个视图：{r['view_sizes']}"),
        ("真实语料：Scaffold 视图**不可能**产生矛盾",
         all("contradiction" not in cp for cp in r["can_produce"].values()),
         f"各视图 can_produce：{r['can_produce']}"),
        ("真实语料：flat 压缩比 < 1（合成比输入大）",
         r["compression"]["flat"] < 1.0,
         f"flat {r['compression']['flat']:.2f} / focused "
         f"{r['compression']['focused']:.2f} —— "
         "真实规模下逐条罗列不可用，靠焦点概括才收得回来"),
        ("真实语料：这份语料是**切面**而非立场（交集为 0）",
         r["intersection"] == 0,
         f"全部视图的单元交集 {r['intersection']} → 共识必然 {r['consensus']} 项；"
         f"分歧 {r['types']}。**这是语料的形状问题，不是 DCE 的问题**"),
    ]
    return out


def report() -> list:
    r = run_real()
    if r.get("skipped"):
        return [("真实语料", f"**跳过** —— {r['why']}")]
    return [
        ("语料目录", r["dir"]),
        ("节点 / 视图", f"{r['nodes']} 个节点 → {r['views']} 个视图 {r['view_sizes']}"),
        ("悬空引用", f"{r['dangling']} 条"),
        ("共识 / 分歧 / 焦点",
         f"{r['consensus']} / {r['types']} / {r['foci']} 个焦点"),
        ("压缩比", f"flat {r['compression']['flat']:.2f}、"
                   f"focused {r['compression']['focused']:.2f}、"
                   f"synopsis {r['compression']['synopsis']:.2f}"),
        ("单元交集（切面 vs 立场的判据）", f"{r['intersection']} 个"),
    ]


if __name__ == "__main__":
    import sys
    if "--full" in sys.argv:
        for t, v in report():
            print(f"  {t:<34} {v}")
    bad = 0
    for t, ok, d in run_all():
        mark = "跳过  " if ok is None else ("过    " if ok else "**红的**")
        print(f"  {mark} {t:<40} {d}")
        bad += 0 if ok in (True, None) else 1
    sys.exit(1 if bad else 0)
