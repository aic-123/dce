"""公开数据（CLIMATE-FEVER）的检查 —— **第一份自带真实类型化关系的材料**。

⚠️ 数据不在仓库里（3.0MB，外部来源），所以走**三态**：
不在就跳过，而**跳过不等于通过**。

---
这份数据与 Perspectrum 的分别
----------------------------

Perspectrum 的视角簇是数据集**预先聚好的**；CLIMATE-FEVER 的 `votes`
是**五个独立标注者对同一条 evidence 的原始判断**：

    votes = ["SUPPORTS", "NOT_ENOUGH_INFO", null, null, null]

⇒ **视图不需要构造，它就在数据里**（视图 = 标注者槽位）。

而 `supports` / `contradicts` **本来就在** `core/edge.py` 的 `EXCLUSIVE_PAIRS` 里
—— countries 与 Scaffold 都要把关系**拍平**成 `dce_untyped`，这份不用。

---
⚠️ 防「空跑的 0」
---------------

本仓库在 Perspectrum 上栽过一次**大小写**：拿小写去比大写的数据 ⇒ 两边空集 ⇒
报了一个**空跑的 0**。所以本模块的断言里有一条**专门防它**：
**先证明票被匹配上了（supports 与 contradicts 都非零），再报重叠数。**
"""

from __future__ import annotations

import pathlib

DATA = pathlib.Path(r"C:\Users\19253\Desktop\_kgdata\climate-fever.jsonl")


def data_file():
    """数据在不在。不在返回 `None`（**不静默用别的东西顶替**）。"""
    return DATA if DATA.is_file() and DATA.stat().st_size > 1_000_000 else None


def measure() -> dict:
    """跑一遍全部 claim，返回汇总。**只算一次，断言与报告共用。**"""
    from adapters import climatefever as C
    from analysis import divergence as D
    from metrics import approximation as A

    rows = C.load(DATA)
    cl = C.claims(rows)
    gammas, skipped = [], 0
    n_contra_by_div = n_contra_independent = 0
    n_conf_claims = 0
    n_views = n_edges = 0
    votes = {"supports": 0, "contradicts": 0, "NOT_ENOUGH_INFO": 0, "null": 0}

    for cid, text, ev in cl:
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
        n_contra_independent += len(C.contradicting_pairs(ev))
        views = C.to_views(cid, text, ev)
        n_views += len(views)
        n_edges += sum(len(v["edges"]) for v in views)
        if C.contradicting_pairs(ev):
            n_conf_claims += 1
        try:
            g = A.gamma(views)["gamma"]
        except Exception:
            skipped += 1
            continue
        # ⚠️ `gamma()` 在退化情形返回 **None**（视图太少的 claim）。
        # 首版直接 append，于是后面拿 None 去比大小 —— `TypeError`。
        # **这不是可以当作 0 的东西**：None 是"算不出来"，0 是"算出来是 0"。
        if g is None:
            skipped += 1
            continue
        gammas.append(g)
        n_contra_by_div += len(D.analyse(views)["contradiction"])

    total_votes = sum(votes.values())
    dropped = votes["NOT_ENOUGH_INFO"] + votes["null"]
    return {
        "n_claims": len(cl),
        "n_views": n_views,
        "n_edges": n_edges,
        "votes": votes,
        "n_votes": total_votes,
        "dropped_share": (dropped / total_votes) if total_votes else None,
        "analysable": len(gammas),
        "skipped": skipped,
        "gammas": gammas,
        "n_gamma_lt_1": sum(1 for g in gammas if g < 1.0 - 1e-12),
        "n_gamma_eq_1": sum(1 for g in gammas if abs(g - 1.0) < 1e-12),
        "gamma_min": min(gammas) if gammas else None,
        "contradictions_by_divergence": n_contra_by_div,
        "contradictions_independent": n_contra_independent,
        "claims_with_contradiction": n_conf_claims,
    }


_CACHE = None


def _m():
    global _CACHE
    if _CACHE is None:
        _CACHE = measure()
    return _CACHE


def run_all() -> list:
    out = []
    if data_file() is None:
        out.append(("CLIMATE-FEVER（公开数据）", None,
                    f"数据不在 {DATA} —— 走三态跳过。**跳过不等于通过**"))
        return out
    m = _m()
    v = m["votes"]

    # ① **先证明匹配上了** —— 防「空跑的 0」
    out.append(("① 标签匹配上了（supports / contradicts 都非零）",
                v["supports"] > 0 and v["contradicts"] > 0,
                f"supports **{v['supports']}** · contradicts **{v['contradicts']}** · "
                f"NOT_ENOUGH_INFO {v['NOT_ENOUGH_INFO']} · null {v['null']}；"
                f"**丢掉 {m['dropped_share']:.0%} 的票**（不表态不是断言，见适配器 DROP 表）。"
                "⚠️ 先证明匹配上再报重叠 —— 空集上的 0 与真测出来的 0 长得一样"))

    # ② 两条互不相干的数法必须同值
    out.append(("② 两条独立数法给出同一个矛盾数",
                m["contradictions_by_divergence"] == m["contradictions_independent"]
                and m["contradictions_by_divergence"] > 0,
                f"`analysis/divergence.py` 数出 "
                f"**{m['contradictions_by_divergence']}** 条；"
                f"适配器里独立数法数出 "
                f"**{m['contradictions_independent']}** 条 —— **同一个数**"))

    # ③ 非自造材料上 γ<1（第一步 S1b 的又一份材料）
    gmin = m["gamma_min"]
    out.append(("③ 非自造材料上 γ<1（第一步 S1b 的又一份证据）",
                m["n_gamma_lt_1"] > 0,
                f"{m['analysable']} 个可分析 claim 里 **{m['n_gamma_lt_1']} 个 γ<1**"
                f"（γ=1 的 {m['n_gamma_eq_1']} 个，**算不出 γ 的 {m['skipped']} 个**），"
                + (f"γ_min={gmin:.4f}" if gmin is not None else "γ_min 不可用")))

    # ④ 形状：**视图是数据自带的**，边没有被拍平
    out.append(("④ 形状：视图由数据自带，且关系**没有被拍平**",
                m["n_views"] >= m["n_claims"] * 2 and m["n_edges"] > 0,
                f"{m['n_claims']} 个 claim → **{m['n_views']} 个视图**、"
                f"{m['n_edges']} 条边；关系用了 `supports`/`contradicts` **本身**，"
                "不是 `dce_untyped` —— 这是本仓库第一份不用拍平的材料"))
    return out


def report() -> list:
    if data_file() is None:
        return [("CLIMATE-FEVER", "跳过：数据不在")]
    m = _m()
    return [
        ("claim / 视图 / 边",
         f"{m['n_claims']} / {m['n_views']} / {m['n_edges']}"),
        ("⭐ γ<1 的 claim",
         f"**{m['n_gamma_lt_1']}/{m['analysable']}**"
         f"（γ=1 的 {m['n_gamma_eq_1']}，算不出的 {m['skipped']}），"
         + (f"min={m['gamma_min']:.4f}" if m["gamma_min"] is not None else "min 不可用")),
        ("⭐ 互斥有序对",
         f"divergence {m['contradictions_by_divergence']} == "
         f"独立数法 {m['contradictions_independent']}，"
         f"分布在 {m['claims_with_contradiction']} 个 claim 上"),
        ("丢掉的票", f"{m['dropped_share']:.0%}（不表态）"),
        ("数据", str(DATA)),
    ]


if __name__ == "__main__":
    import sys
    print("── 度量 ──")
    for t, val in report():
        print(f"  {t:<22} {val}")
    print("\n── 断言 ──")
    bad = 0
    for t, ok, d in run_all():
        mark = "跳过  " if ok is None else ("过    " if ok else "**红的**")
        print(f"  {mark} {t:<44} {d}")
        bad += 0 if ok in (True, None) else 1
    sys.exit(1 if bad else 0)
