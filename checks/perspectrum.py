"""公开数据（Perspectrum）的检查 —— **MVP 第一步的过线证据就在这里**。

⚠️ 数据不在仓库里（877KB，外部来源），所以走**三态**：
不在就跳过，而**跳过不等于通过**。

---
这份数据证明了什么
----------------

`checks/mvp.py` 里第一步的判据分成两半：

    S1a 表达力   构造材料上 γ<1          ✅ 已达成（立场材料 γ=0.2105）
    S1b 现实性   **非自造**材料上 γ<1     ← 本模块

Perspectrum 上实测：**752 个可分析 claim 里 134 个 γ<1**（min 0.0769，中位 1.0000）。

---
⚠️ 一个**空跑出来的 0**，以及它怎么被抓住的
----------------------------------------

第一版探针报「同一 `(claim, evidence)` 被两个对立立场都引用：**0 例**」。
那是假的：README 写 `"support"`，而**数据里是全大写 `"SUPPORT"`**；
探针拿小写去比，**一个都没匹配上**，两边都是空集，于是 0 是空跑出来的。

所以本模块的断言里有一条**专门防它**：**先证明匹配上了（两个立场的簇数都非零），
再报重叠数**。这与本仓库「跳过不等于通过」是同一条规矩的另一副面孔：
**空集上的 0 与真测出来的 0，长得一模一样。**
"""

from __future__ import annotations
from checks import _data

import pathlib

# ⚠️ 走 `checks/_data.py`；**文件不在时是 `None`**，`data_file()` 再兜一层。
DATA = _data.path("perspectrum.json") or _data.LEGACY / "perspectrum.json"


def data_file():
    """数据在不在。不在返回 `None`（**不静默用别的东西顶替**）。"""
    return DATA if DATA.is_file() and DATA.stat().st_size > 100_000 else None


def measure() -> dict:
    """跑一遍全部 claim，返回汇总。**只算一次，断言与报告共用。**"""
    from adapters import perspectrum as P
    from analysis import divergence as D
    from core import view as V
    from metrics import approximation as A

    claims, total = P.load_claims(DATA)
    gammas, skipped = [], 0
    n_contra_by_div = n_contra_independent = 0
    n_clusters = n_evidence_refs = 0
    for cid, clusters, _raw in claims:
        n_clusters += len(clusters)
        n_evidence_refs += sum(len(e) for _i, _s, e in clusters)
        n_contra_independent += len(P.cross_stance_pairs(clusters))
        views = P.to_views(cid, clusters)
        try:
            gammas.append(A.gamma(views)["gamma"])
        except Exception:
            skipped += 1
            continue
        n_contra_by_div += len(D.analyse(views)["contradiction"])
    return {"total_claims": total, "analysable": len(claims),
            "skipped": skipped, "n_clusters": n_clusters,
            "n_evidence_refs": n_evidence_refs,
            "gammas": gammas,
            "n_gamma_lt_1": sum(1 for g in gammas if g < 1.0 - 1e-12),
            "n_gamma_eq_1": sum(1 for g in gammas if abs(g - 1.0) < 1e-12),
            "gamma_min": min(gammas) if gammas else None,
            "contradictions_by_divergence": n_contra_by_div,
            "contradictions_independent": n_contra_independent,
            "support_clusters": None, "undermine_clusters": None}


def run_all() -> list:
    out = []
    if data_file() is None:
        out.append(("公开数据（Perspectrum）", None,
                    f"不在 {DATA} —— **跳过不等于通过**"))
        return out
    m = measure()

    # ① ⚠️ **先证明匹配上了，再报数** —— 防「空跑出来的 0」
    from adapters import perspectrum as P
    claims, _total = P.load_claims(DATA)
    ns = sum(1 for _c, cl, _r in claims for _i, s, _e in cl if s == "support")
    nu = sum(1 for _c, cl, _r in claims for _i, s, _e in cl if s == "undermine")
    out.append(("⚠️ 先证明标签匹配上了（两个立场都非零）—— 防空跑",
                ns > 0 and nu > 0,
                f"归一化后 support 簇 {ns} 个、undermine 簇 {nu} 个 —— "
                "**第一版探针在这里报了假的 0**：README 写小写，数据是全大写，"
                "拿小写去比一个都匹配不上，两边空集 → 0 是空跑出来的"))

    # ② ⭐ 两条**独立**的路数出的矛盾数逐位相同
    out.append(("⭐ 两条独立的路数出的矛盾数**逐位相同**",
                m["contradictions_by_divergence"] == m["contradictions_independent"]
                and m["contradictions_by_divergence"] > 0,
                f"`analysis/divergence.py` 数出 {m['contradictions_by_divergence']} 条；"
                f"独立数法（同一 evidence 被两个对立立场簇引用）数出 "
                f"{m['contradictions_independent']} 条 —— **同一个数**"))

    # ③ ⭐⭐ **S1b：非自造材料上 γ<1** —— MVP 第一步过线
    out.append(("⭐⭐ S1b 现实性：**非自造材料上 γ<1**（MVP 第一步过线）",
                m["n_gamma_lt_1"] > 0,
                f"{m['analysable']} 个可分析 claim 里 **{m['n_gamma_lt_1']} 个 γ<1**"
                f"（γ=1 的 {m['n_gamma_eq_1']} 个），γ_min={m['gamma_min']:.4f} —— "
                "**视图层在非自造材料上确实区分出了「并集+频次」区分不出的东西**"))

    # ④ 数据形状
    out.append(("数据形状",
                m["analysable"] > 500 and m["contradictions_by_divergence"] > 0,
                f"共 {m['total_claims']} 个 claim，可分析 {m['analysable']} 个；"
                f"{m['n_clusters']} 个视角簇、{m['n_evidence_refs']} 条 evidence 引用"))
    return out


def report() -> list:
    if data_file() is None:
        return [("Perspectrum", f"不在 {DATA}")]
    m = measure()
    return [
        ("来源", "CogComp/perspectrum · data/dataset/perspectrum_with_answers_v1.0.json"),
        ("规模", f"{m['total_claims']} claim（可分析 {m['analysable']}）；"
                 f"{m['n_clusters']} 视角簇；{m['n_evidence_refs']} 条 evidence 引用"),
        ("⭐ γ<1 的 claim", f"**{m['n_gamma_lt_1']}/{m['analysable']}**"
                            f"（γ=1 的 {m['n_gamma_eq_1']}），min={m['gamma_min']:.4f}"),
        ("矛盾数", f"divergence {m['contradictions_by_divergence']} == "
                   f"独立数法 {m['contradictions_independent']}"),
        ("读法", "**MVP 第一步（知识能从视图层区分）在非自造材料上过线。**"),
    ]


if __name__ == "__main__":
    import sys
    print("── 度量 ──")
    for t, v in report():
        print(f"  {t:<16} {v}")
    print("\n── 断言 ──")
    bad = 0
    for t, ok, d in run_all():
        mark = "跳过  " if ok is None else ("过    " if ok else "**红的**")
        print(f"  {mark} {t:<52} {d}")
        bad += 0 if ok in (True, None) else 1
    sys.exit(1 if bad else 0)
