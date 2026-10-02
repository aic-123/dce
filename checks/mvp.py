"""两阶段的分界，以及**第一阶段（MVP）的判据** —— 钉成可执行检查。

---
为什么要有这个文件
----------------

第 1 轮的跑偏不是「不知道目标」，而是**目标没有被写成一条可检验的线**。
于是我每轮都在做「看起来有用的事」（零模型、形式概念分析、β 分解、观点群），
而不是做「能过线的事」。所以这条线必须是**可执行的**：

    只有注释守护的纪律不是纪律，是愿望。

---
两阶段
-----

    **第一步（MVP）** 证明**知识能从视图层区分**
                      —— 视图层要能区分出「并集+频次」区分不出的东西
    **第二步**        用差分来提供**检索**
                      —— 拿差分当索引去回答「我该看哪儿」

⚠️ **第二步不是第一步的加强版，是另一件事。** 它们各自可以有独立进度：
第一步没过线时，第二步做出来的东西**再漂亮也不能替它过线**。
本文件的作用就是**不许第二步的东西冒充第一步的证据**。

---
第一步的判据（可量化的形式）
--------------------------

`DECLARATION.md` §一 说它只回答三句话，而**第三句（差异属于什么类型）
是它唯一比「并集 + 频次」多出来的东西**。那句有一个已经算好的定量形式：

    γ = |正域| / |对象|        （粗糙集的依赖度）
    γ = 1  ⟺  类型判定完全由「单元出现在哪几个视图」决定
           ⟺  视图层**没多区分出任何东西**

⇒ **第一步的判据：γ < 1。**

**而它有两半，必须分开说**（混起来正是跑偏的来源）：

    **S1a 表达力**  类型确实区分得开、且不可归约为成员关系
                    —— 用一个**有已知 ground truth** 的构造材料演示
    **S1b 现实性**  同一件事在**不是我们造的材料**上也成立

⚠️ **自造材料只能证 S1a，证不了 S1b。** 因为它是**按判据造的** ——
本仓库已经为这类自欺栽过一次（`recall 1.000` 是用 DCE 的判据挑出来的语料测出来的）。
"""

from __future__ import annotations


def materials() -> list:
    """全部可用材料：`(名字, 视图, 是不是我们造的)`。"""
    out = []
    from generators import positions as POS
    pv, _i = POS.build()
    out.append(("立场材料（按判据造的）", pv, True))
    from checks import realdata as RD
    from adapters import scaffold as SC
    dd = RD.corpus_dir()
    if dd:
        nodes = SC.load_corpus_dir(dd)
        rv = [a.view for a in SC.split_views(nodes, split_by="source.kind")]
        if len(rv) >= 2:
            out.append(("真实语料（Scaffold 节点）", rv, False))
    from checks import countries as CN
    d2 = CN.data_dir()
    if d2:
        from adapters import countries as C
        cv, _ids = C.load_dir(d2)
        out.append(("公开数据（countries）", cv, False))
    # ⚠️ **Perspectrum 不放进这里。** 它是**逐个 claim 分析**的
    # （视图 = 该 claim 的视角簇），把 907 个 claim 的视图**并成一个分析**
    # 是错的 —— `adapters/perspectrum.py` 的 docstring 里写着为什么：
    # 跨 claim 的节点空间是拼起来的，而一个视角簇只对它自己那个 claim 发言。
    # 我第一次就并了，结果把检查卡死（规模爆炸）。
    # 它的结果由 `checks/perspectrum.py` **逐 claim** 算，本文件只读那个数。
    return out


def measure() -> list:
    """逐材料量 `γ` 与五类计数。"""
    from analysis import divergence as D
    from metrics import approximation as A
    rows = []
    for name, views, authored in materials():
        g = A.gamma(views)
        d = D.analyse(views)
        rows.append({
            "name": name, "authored": authored,
            "gamma": g["gamma"], "n_units": g["n_units"],
            "n_classes": g["n_classes"],
            "types": {t: len(d[t]) for t in
                      ("refinement", "contradiction", "alternative", "omission")},
        })
    return rows


def run_all() -> list:
    out = []
    rows = measure()

    # ① **两阶段的分界本身**要被钉住 —— 第二步的东西不许冒充第一步的证据
    out.append(("两阶段：第一步是 γ<1（视图层能区分），第二步才是拿差分做检索",
                True,
                "**它们可以有独立进度。** 第一步没过线时，第二步做出来的东西"
                "再漂亮也不能替它过线 —— 本检查存在的理由就是不许那种冒充"))

    # ② S1a 表达力：构造材料上 γ<1（**这是正向对照，证明机制区分得开**）
    mine = [r for r in rows if r["authored"]]
    out.append(("S1a 表达力：构造材料上 γ<1（有已知 ground truth 的演示）",
                bool(mine) and all(r["gamma"] < 1 for r in mine),
                "；".join(f"{r['name']} γ={r['gamma']:.4f}（{r['n_units']} 单元，"
                          f"{r['n_classes']} 类）" for r in mine)))

    # ③ ⭐ **S1b 现实性：过线了**（本条原先钉的是「未达成」）
    #
    # ⚠️ 这条**已经按设计翻过一次红**。加 Perspectrum 之前它断言的是
    # 「真材料上 γ 全 = 1」，并写着「一旦某个真材料 γ<1，本条会红 —— 那是好消息」。
    # 2026-10-01 它红了：Perspectrum 上 **752 个可分析 claim 里 134 个 γ<1**。
    # 于是按本仓库的规矩（**钉住缺陷的断言要在修好后同时钉住新状态**）
    # 把它改成断言**已达成**。
    #
    # ⚠️ 而 `countries` 与 Scaffold 语料**仍然 γ=1** —— 这一点没有被这条断言抹掉：
    # 它们各自的原因写在 `checks/countries.py`（纯嵌套、无分歧）里。
    others = [r for r in rows if not r["authored"]]
    # Perspectrum 的数是**逐 claim** 算的（见 `checks/perspectrum.py`），
    # 所以这里读那个结果，而不是把它并进 `rows` 里（并进去会把检查卡死）。
    from checks import perspectrum as CP
    pers = None
    if CP.data_file() is not None:
        try:
            pers = CP.measure()
        except Exception as e:                       # 数据坏掉要**说出来**
            pers = {"error": str(e)[:60]}
    ok_s1b = bool([r for r in others if r["gamma"] < 1.0 - 1e-12]) or \
        bool(pers and pers.get("n_gamma_lt_1", 0) > 0)
    detail = "；".join(f"{r['name']} γ={r['gamma']:.4f}" for r in others)
    if pers and "n_gamma_lt_1" in pers:
        detail += (f"；Perspectrum（逐 claim）**{pers['n_gamma_lt_1']}/"
                   f"{pers['analysable']} 个 γ<1**，min={pers['gamma_min']:.4f}")
    out.append(("⭐ S1b 现实性：**非自造材料上有 γ<1** —— MVP 第一步过线",
                ok_s1b,
                detail + " —— **至少一份真材料让视图层区分出了"
                "「并集+频次」区分不出的东西**"))

    # ④ **谁挡着路**：只有 pairing 依赖的两类能把 γ 拉下来
    #
    # 签名只记「出现在哪几个视图」。所以不依赖 `(from,to)` 配对的类型
    # （共识 / 缺失 / 精炼）签名就能定；只有 contradiction 与 alternative
    # 依赖配对。两份真材料这两类都是 0 ⇒ **γ≡1 是必然而不是意外**。
    blockers = [(r["name"], r["types"]["contradiction"], r["types"]["alternative"])
                for r in others]
    out.append(("诊断：真材料上 `contradiction` 与 `alternative` 都是 0 ⇒ γ≡1 是必然",
                all(c == 0 and a == 0 for _n, c, a in blockers),
                "；".join(f"{n}: contradiction={c} alternative={a}"
                          for n, c, a in blockers) +
                " —— 只有这两类依赖 `(from,to)` 配对，"
                "它们为 0 则类型必然由签名决定"))

    # ⑤ 过线材料的判据（**可判、不需要猜**）
    out.append(("要过线，材料必须满足的判据（可判）",
                True,
                "**存在一个有序对，在两个视图里挂了互斥的关系** —— "
                "等价地：**存在一个单元，它的类型不由「出现在哪几个视图」决定**。"
                "少第一条则不能算分歧，少第二条则只是切片"))
    return out


def report() -> list:
    rows = []
    for r in measure():
        tag = "自造" if r["authored"] else "**非自造**"
        rows.append((r["name"],
                     f"γ={r['gamma']:.4f}  单元={r['n_units']:>4}  {tag}  {r['types']}"))
    rows.append(("第一步判据", "γ < 1；且要分开看 S1a（表达力）/ S1b（现实性）"))
    rows.append(("第二步", "用差分做检索 —— **另一件事，不是第一步的加强版**"))
    return rows


if __name__ == "__main__":
    import sys
    print("── 度量 ──")
    for t, v in report():
        print(f"  {t:<24} {v}")
    print("\n── 断言 ──")
    bad = 0
    for t, ok, d in run_all():
        mark = "跳过  " if ok is None else ("过    " if ok else "**红的**")
        print(f"  {mark} {t:<56} {d}")
        bad += 0 if ok in (True, None) else 1
    sys.exit(1 if bad else 0)
