"""立场材料检查 —— **按判据验材料，不按材料改判据。**

`generators/positions.py` 造了三份立场，`intent` 里写明每一类**打算**出现在哪里。
本模块把实际分类结果与那份设计对照，分三种情形：

    一致        → 过
    不一致      → 改**材料**（`positions.py`），不改判据与算法
    判据本身错  → 才轮到改 `CRITERIA.md` / `core` / `analysis`，而那要单独说明

⚠️ 这个顺序是本模块存在的全部意义。反过来做（拿材料去迁就结果）就是
「试到好看为止」，正是 `§T0.3` 要防的那种。
"""

from __future__ import annotations

from analysis import consensus as C
from analysis import divergence as D
from analysis import synthesis as S
from analysis import focus as F


def _subjects(syn) -> dict:
    out = {"contradiction": set(), "alternative": set(),
           "refinement": set(), "omission": set()}
    for rec in syn["divergence"]:
        t = rec["type"]
        if t == "contradiction":
            out[t].add((rec["from"], rec["to"]))
        elif t == "alternative":
            out[t].add((rec["source"], rec["relation"]))
        elif t == "refinement":
            out[t].add((rec["coarse"], rec["fine"]))
        elif t == "omission":
            out[t].add((rec["missing_in"], rec["unit"]["kind"],
                        str(rec["unit"]["key"])))
    return out


def analyse_positions() -> dict:
    from generators import positions as POS
    views, intent = POS.build()
    syn = S.build(views)
    got = _subjects(syn)
    cons = {(r["unit"]["kind"], r["unit"]["key"])
            for r in syn["consensus"]["records"]}
    return {"views": views, "intent": intent, "syn": syn, "got": got,
            "consensus": cons,
            "n_units": sum(len(C.units_of(v)) for v in views)}


def run_all() -> list:
    r = analyse_positions()
    syn, got, intent = r["syn"], r["got"], r["intent"]
    out = []

    # ① 共识必须由定义算出，且非空（三份立场有共享骨架）
    units = [C.units_of(v) for v in r["views"]]
    inter = set.intersection(*units)
    out.append(("立场：共识 = 三份立场的交集，且非空",
                r["consensus"] == inter and len(inter) > 0,
                f"交集 {len(inter)} 个单元；共识记录 {len(r['consensus'])} 项"))

    # ② 矛盾：同一有序端点对上的互斥种类
    want_c = {(f, t) for (f, t, _a, _b) in intent["contradiction"]}
    out.append(("立场：矛盾按判据出现（同一有序对、互斥种类）",
                want_c <= got["contradiction"],
                f"期望 {sorted(want_c)}；实际 {sorted(got['contradiction'])}"))

    # ③ 替代解释：同一 source 上后继集合互不包含
    want_a = set(intent["alternative"])
    out.append(("立场：替代解释出现（后继集合互不包含）",
                want_a <= got["alternative"],
                f"期望 {sorted(want_a)}；实际 {sorted(got['alternative'])}"))

    # ④ 精炼：P1 ⊊ P3
    want_r = set(intent["refinement"])
    out.append(("立场：精炼出现（P1 是 P3 的真子集）",
                want_r <= got["refinement"],
                f"期望 {sorted(want_r)}；实际 {sorted(got['refinement'])}"))

    # ⑤ 缺失：该报的要报
    missing = []
    for (vid, kind, key) in intent["omission_expected"]:
        if (vid, kind, str(key)) not in got["omission"]:
            missing.append((vid, kind, str(key)))
    out.append(("立场：该报的缺失都报了",
                not missing,
                f"缺 {missing}" if missing else
                f"{len(intent['omission_expected'])} 条全部报出"))

    # ⑥ **判决性的那条**：有互斥对应的，不许被报成缺失
    #
    # 「同一案例被读成支持和反对」那个单元，按判据归**矛盾**。
    # 若它同时出现在缺失里，说明四类的边界破了 —— 而那正是 §五·三 要修的那个错。
    bad = [x for x in intent["omission_must_exclude"]
           if (x[0], x[1], str(x[2])) in got["omission"]]
    out.append(("立场：有互斥对应的单元**不**被报成缺失（§五·三）",
                not bad,
                f"误报 {bad}" if bad else
                f"{len(intent['omission_must_exclude'])} 条全部正确排除"))

    # ⑦ 四类都得出现 —— 否则这份材料没测到判据的边界
    present = {t for t in ("contradiction", "alternative", "refinement", "omission")
               if got[t]}
    out.append(("立场：四类各有自然出现（不是种在专用视图上）",
                len(present) == 4,
                f"出现 {sorted(present)}；各计数 "
                f"{ {t: len(got[t]) for t in sorted(got)} }"))

    # ⑧ §十一 与 §七 的前提冲突 —— **对「按邻近性」这个依据仍然成立**
    #
    # ⚠️ 这条断言改过一次，而改的原因值得记：它原先查的是 `syn["foci"]`，
    # 于是把「**旧依据**失效」与「**产品**失效」绑成了一个事实。
    # 换成按主语分组之后，这条就红了 —— 而红得对：**产品不再失效了。**
    # 现在它显式地只针对**按邻近性**那一族函数，于是两件事各自被钉住：
    #
    #     邻近性依据（距离≤r 或 kNN 分量）在共享节点空间上恒为 1 → 冲突仍在
    #     产品用的依据是**按主语**，不受那条冲突影响
    # ⚠️ 循环变量**不能**叫 `r` —— 上面 `r` 已经是结果字典，
    # 遮蔽之后 `r["views"]` 就变成对整数取下标（`TypeError: 'int' object
    # is not subscriptable`）。这个会话里第二次栽在同一类错上。
    prox = {len(F.foci(D.analyse(r["views"]), radius=rr, views=r["views"]))
            for rr in range(0, 4)}
    n_prox = sorted(prox)
    n_subj = len(syn["foci"])
    out.append(("立场：**邻近性依据**在共享节点空间上塌成 1（§十一 与 §七 的冲突）",
                n_prox == [1],
                f"距离≤r（r=0..3）得 {n_prox} 个焦点 —— "
                "共享节点空间让分歧可算，同时让**邻近性**依据恒等于 1。"
                f"**产品现在用按主语分组，得 {n_subj} 个**，不受这条冲突影响"))

    # ⑨ `focused` 压缩比：**在邻近性依据下是假压缩**
    #
    # 它 = 输入 / (共识 + 1)。只说明「全都是一团」，不是概括出了结构。
    # 按主语分组之后 `focused` 才有实义，所以这条**也改成只针对邻近性依据**。
    from metrics import compression as CMP
    syn_prox = S.build(r["views"], focus_basis="reach")
    k_prox = CMP.compression(r["views"], syn_prox)["all_modes"]
    base = len(syn_prox["consensus"]["records"]) + len(syn_prox["foci"])
    out.append(("立场：`focused` 在**邻近性**依据下是假压缩（= 共识 + 1）",
                abs(k_prox["focused"] - CMP.input_size(r["views"]) / base) < 1e-9,
                f"邻近性依据下 focused {k_prox['focused']:.2f} —— "
                f"那个数只说明「全都是一团」；"
                f"按主语后 focused {CMP.compression(r['views'], syn)['all_modes']['focused']:.2f}"
                "，才是概括出来的"))

    return out


def report() -> list:
    r = analyse_positions()
    syn, got = r["syn"], r["got"]
    counts = {}
    for rec in syn["divergence"]:
        counts[rec["type"]] = counts.get(rec["type"], 0) + 1
    from metrics import compression as CMP
    from metrics import coverage as COV
    cov = COV.coverage(r["views"], syn)
    cmp_ = CMP.compression(r["views"], syn)
    return [
        ("三份立场", f"单元 {r['n_units']} 个（视图大小 "
                     f"{[len(v['nodes']) for v in r['views']]} 节点）"),
        ("共识 / 分歧", f"{len(r['consensus'])} / {counts}"),
        ("焦点", f"{len(syn['foci'])} 个"),
        ("Coverage / Compression",
         f"{cov['value']:.4f} / flat {cmp_['all_modes']['flat']:.2f}、"
         f"focused {cmp_['all_modes']['focused']:.2f}"),
        ("对比：真实语料按体裁切",
         "共识 0、分歧全是 omission、flat 0.33 —— 那是**切面**；"
         "这里是**立场**，四类都自然出现"),
        ("⚠️ 但**邻近性**依据在共享节点空间上塌成 1 个",
         "§十一 的邻近性依据用「共享节点」并查集 = 传递闭包；而 §七 的前提是"
         "「视图已映射到共享节点空间」。**让分歧可算的前提，同时让那个依据失效。**"
         "产品现在改用**按主语分组**（`synthesis.build` 的默认），"
         "所以这条冲突仍在，但不再影响产物。"
         "真实语料那 9 个焦点是**切面**（按体裁切，几近不相交）造出来的，"
         "不是立场造出来的"),
    ]


if __name__ == "__main__":
    import sys
    for t, d in report():
        print(f"  {t:<34} {d}")
    print()
    bad = 0
    for t, ok, d in run_all():
        print(f"  {'过    ' if ok else '**红的**'} {t:<46} {d}")
        bad += 0 if ok else 1
    sys.exit(1 if bad else 0)
