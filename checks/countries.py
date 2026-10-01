"""公开数据（countries 三视图）的检查。

⚠️ **数据不在仓库里**（30KB × 3，且是外部来源），所以本模块走**三态**：
数据不在就报「跳过」，而**跳过不是通过** —— 这与 `checks/realdata.py` 同一条规矩。

---
这一份为什么重要
--------------

前面的材料只有两种：合成的、作者写的。而「合成语料上有效」这句话本仓库吃过亏
（`recall 1.000` 曾是**自选语料**的产物）。这是第一份**不是我自己造**的多视图材料。

---
⚠️ 一个被这份数据**证伪**的假设，留在这里
--------------------------------------

我原以为：`refinement` 在优先顺序里排第一（`CRITERIA.md` §三），
而它的判据只是「单元集严格包含」，所以它会把**实质性的分歧**（比如
「同一个国家被归到不同大洲」）也当成「粒度更粗」吞掉。

**这份数据把这个怀疑证伪了。** 实测：

    S3 ⊊ S2 ⊊ S1（严格嵌套链），差集**全是 locatedin**
    「同一个实体在不同视图里 locatedin 到不同地方」的例子：**0 例**

也就是说这里**根本没有实质性分歧可吞**，把它判成 refinement 是**对的**。
假设没被证实，而**记下一个被证伪的假设比记下一个被证实的更有用** ——
它下次能省掉同一条弯路。
"""

from __future__ import annotations

import pathlib

DATA_DIR = pathlib.Path(r"C:\Users\19253\Desktop\_kgdata")


def data_dir():
    """数据在不在。不在就返回 `None`（**不是**静默用别的东西顶替）。"""
    d = DATA_DIR
    if not d.is_dir():
        return None
    if not all((d / f"countries_{s}.txt").exists() for s in ("S1", "S2", "S3")):
        return None
    return d


def run_all() -> list:
    out = []
    d = data_dir()
    if d is None:
        out.append(("公开数据（countries）", None,
                    f"数据不在 {DATA_DIR} —— **跳过不等于通过**"))
        return out

    from adapters import countries as C
    from analysis import consensus as CS
    from analysis import divergence as D
    from metrics import approximation as A

    views, ids = C.load_dir(d)

    # ① 三份视图共用**同一张 id 表** —— 否则它们不是同一个节点空间
    sets = [set(v["nodes"]) for v in views]
    out.append(("三份视图共用同一个节点空间（同一张 id 表）",
                sets[0] == sets[1] == sets[2] and len(ids) == len(sets[0]),
                f"{len(ids)} 个实体，三份视图的节点集完全相同"))

    # ② 源数据里的两种关系被压平成 dce_untyped —— **这是声明的损失**
    kinds = {e["relation"] for v in views for e in v["edges"]}
    src_rels = {r for v in views for _a, _b, r in v["metadata"]["source_triples"]}
    out.append(("关系种类被压平成 dce_untyped（**损失是声明的**）",
                kinds == {"dce_untyped"} and len(src_rels) == 2,
                f"源数据 {sorted(src_rels)} → 视图里只有 {sorted(kinds)}；"
                "原文保留在 metadata.source_triples 里"))

    # ③ 三份是一条**严格嵌套链**，且差集**全是 locatedin**
    u = {v["id"]: CS.units_of(v) for v in views}
    tr = {v["id"]: {tuple(x) for x in v["metadata"]["source_triples"]} for v in views}
    nested = u["S3"] < u["S2"] < u["S1"]
    diffs = (tr["S1"] - tr["S2"]) | (tr["S2"] - tr["S3"])
    only_loc = {r for _a, _b, r in diffs} == {"locatedin"}
    out.append(("三份是严格嵌套链，差集全是 locatedin",
                nested and only_loc,
                f"|S1|={len(u['S1'])} ⊋ |S2|={len(u['S2'])} ⊋ |S3|={len(u['S3'])}；"
                f"差集 {len(diffs)} 条全是 locatedin"))

    # ④ ⭐ **「同一实体、不同归属」0 例** —— 所以这份数据没有实质分歧
    #
    # 这是证伪上面那个假设的那一条。
    by = {}
    for a, b, r in tr["S2"]:
        if r == "locatedin":
            by.setdefault(a, set()).add(b)
    clash = [(a, b) for a, b, r in (tr["S1"] - tr["S2"])
             if r == "locatedin" and a in by]
    out.append(("⭐ 没有「同一实体、不同归属」—— 这份数据**没有实质分歧**",
                not clash,
                f"{len(clash)} 例 —— **那个「refinement 会吞掉分歧」的怀疑被证伪了**："
                "这里根本没有分歧可吞"))

    # ⑤ DCE 的读数与「纯嵌套、无分歧」这个事实**一致**
    div = D.analyse(views)
    g = A.gamma(views)
    cons = len(CS.consensus(views))
    out.append(("DCE 的读数与「纯嵌套、无分歧」一致",
                len(div["refinement"]) > 0
                and not div["contradiction"] and not div["alternative"]
                and not div["omission"] and abs(g["gamma"] - 1.0) < 1e-12,
                f"refinement={len(div['refinement'])}，其余三类全 0，"
                f"共识={cons}，γ={g['gamma']:.4f} —— "
                "**优先顺序把它判成 refinement 是对的**"))

    # ⑥ 群结构：三份是**同一个立场的三次抽样** → 一个群 → 退化
    diag = CS.consensus_diagnostic(views)
    out.append(("群结构退化（三份是同一立场的三次抽样，不是一个立场三次声明）",
                diag["degenerate"] and diag["n_groups"] == 1,
                f"群 {diag['groups']} —— {diag['reading']}"))

    return out


def report() -> list:
    d = data_dir()
    if d is None:
        return [("公开数据", f"不在 {DATA_DIR}")]
    from adapters import countries as C
    views, ids = C.load_dir(d)
    rows = [("来源", "villmow/datasets_knowledge_embedding · other/countries/")]
    rows.append(("规模", f"{len(ids)} 个实体；三份视图共用同一张 id 表"))
    for vid, n, m, rels in C.describe(views):
        rows.append((f"  {vid}", f"节点 {n}  边 {m}  源关系 {rels}"))
    rows.append(("形状", "S3 ⊊ S2 ⊊ S1 —— **严格嵌套链**，差集全是 locatedin"))
    rows.append(("读法", "纯嵌套、无实质分歧 → refinement 独大，其余三类 0，γ=1.0000"))
    return rows


if __name__ == "__main__":
    import sys
    print("── 度量 ──")
    for t, v in report():
        print(f"  {t:<14} {v}")
    print("\n── 断言 ──")
    bad = 0
    for t, ok, dd in run_all():
        mark = "跳过  " if ok is None else ("过    " if ok else "**红的**")
        print(f"  {mark} {t:<52} {dd}")
        bad += 0 if ok in (True, None) else 1
    sys.exit(1 if bad else 0)
