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

    # ③ ⚠️ **当前状态：S1b 现实性未达成** —— 钉住，并说明反过来会红
    #
    # ⚠️ 这条**钉住的是一个未达成的判据**，所以它绿着并不代表过线。
    # 它绿着的含义是「现状如实记录在案」。一旦某个真材料 γ<1，
    # 本条会红 —— **那时是好消息，请更新本条与文档。**
    others = [r for r in rows if not r["authored"]]
    out.append(("⚠️ S1b 现实性：**判据未达成** —— 真材料上 γ 全 = 1",
                bool(others) and all(abs(r["gamma"] - 1.0) < 1e-12 for r in others),
                "；".join(f"{r['name']} γ={r['gamma']:.4f}" for r in others) +
                " —— **视图层没多区分出任何东西**。"
                "⚠️ 本条绿着**不代表过线**，只代表现状如实记录；"
                "**一旦某个真材料 γ<1，本条会红 —— 那是好消息，请更新**"))

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
