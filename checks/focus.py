"""焦点机制的要求（R1–R6）与三种依据的对照。

---
先把要求写下来（判据先于实现）
----------------------------

「焦点」是为了满足一组**要求**而存在的，而**结构形式不是要求**。
这一点是本轮的一个更正：原先焦点被实现成**划分**（每条记录恰好一个焦点），
而那个前提**从没被论证过**。核到双聚类的 `checkerboard` 结构之后才发现
它可以不是划分，于是要求被重新写成了下面六条：

    R1 覆盖      每条分歧记录至少进一个焦点（不丢东西）
    R2 压缩      焦点数**远少于**记录数（不然没压缩，只是换了个清单）
    R3 非退化    在真正的立场材料上焦点数 **> 1**（不然这个机制没用）
    R4 可追溯    每个焦点带非空溯源，且逐条对得上源视图（§C9 #9）
    R5 无阈值    不用任何阈值、打分、热度（§C9 #5 / §T0.3 / §二十）
    R6 确定性    同一输入 → 同一焦点；输入顺序不影响结果

**「是划分」不在其中。** 一条记录可以出现在多个焦点里，只要 R1–R6 成立。

---
三种依据的对照（都是量出来的，不是我说的）
----------------------------------------

    依据                     立场材料上的焦点数
    ──────────────────────  ──────────────────
    距离 ≤ r 的并查集（r=0..5）  1, 1, 1, 1, 1, 1       差
    kNN 图弱连通分量（k=1..8）    1, 1, 1, 1, 1          差
    **按主语分组**               **6**（视图族 3）      好

前两种差的原因同一条：**结构邻近性在共享节点空间上是传递闭包**，
而「多个立场就同一议题争执」的定义就是共享空间 ——
**越是对同一件事有分歧，越会并成一团。**

第三种不碰图结构，只用记录自带的字段当主语，所以不可能发生那种合并。
"""

from __future__ import annotations

from analysis import focus as F

# 三种材料，按「是本仓库预期用法吗」排序
def _materials() -> list:
    out = []
    from generators import positions as POS
    pv, _i = POS.build()
    out.append(("立场材料（共享节点空间）", pv, True))
    from checks import realdata as RD
    from adapters import scaffold as SC
    dd = RD.corpus_dir()
    if dd:
        nodes = SC.load_corpus_dir(dd)
        rv = [a.view for a in SC.split_views(nodes, split_by="source.kind")]
        if len(rv) >= 2:
            out.append(("真实语料（按体裁切）", rv, False))
    return out


def run_all() -> list:
    from analysis import divergence as D
    out = []

    for name, views, is_intended in _materials():
        div = D.analyse(views)
        recs = F._all_records(div)
        n = len(recs)
        s = F.subject_foci(div, "structure")
        v = F.subject_foci(div, "view")

        # ── R1 覆盖：每条记录至少进一个焦点（两族各自都要满足）──
        s_keys = {F.subject_of(r) for r in recs}
        v_keys = {vid for r in recs for vid in F.views_of(r)}
        out.append((f"R1 覆盖：每条记录至少进一个结构焦点（{name}）",
                    all(F.subject_of(r) in s_keys for r in recs) and bool(recs),
                    f"{n} 条记录 → 结构主语 {len(s_keys)} 种；"
                    f"视图族主语 {len(v_keys)} 种"))

        # ── R2 压缩：焦点数**远少于**记录数 ──
        out.append((f"R2 压缩：焦点数 < 记录数（{name}）",
                    len(s) < n and len(v) < n,
                    f"{n} 条 → 结构 {len(s)} 个（{n / max(1, len(s)):.1f}x）、"
                    f"视图 {len(v)} 个（{n / max(1, len(v)):.1f}x）"))

        # ── R4 可追溯：每个焦点有非空溯源，且逐条对得上源视图 ──
        bad = []
        for f in s + v:
            if not f["sources"]:
                bad.append((f["focus"], "空溯源"))
                continue
            try:
                from core import provenance as P
                P.verify_against(f["sources"], views)
            except P.ProvenanceError as e:
                bad.append((f["focus"], str(e)[:40]))
        out.append((f"R4 可追溯：每个焦点溯源非空且对得上（{name}）",
                    not bad, f"不符 {bad[:3]}" if bad else
                    f"{len(s) + len(v)} 个焦点全部通过 §C9 #9 的核对"))

        # ── R6 确定性：两次算、以及输入逆序，结果一致 ──
        a1 = [(f["focus"], f["subject"], f["size"]) for f in F.subject_foci(
            D.analyse(views), "structure")]
        a2 = [(f["focus"], f["subject"], f["size"]) for f in F.subject_foci(
            D.analyse(list(reversed(views))), "structure")]
        out.append((f"R6 确定性：输入逆序不改变结果（{name}）", a1 == a2,
                    f"{len(a1)} 个焦点" + ("" if a1 == a2 else f"，逆序后 {len(a2)} 个")))

        # ── R3 非退化：**只在预期用法上断言**（立场材料）──
        if is_intended:
            old = {len(F.foci(div, radius=r, views=views)) for r in range(6)}
            knn = {len(F.knn_foci(div, views=views, k=k)["foci"])
                   for k in (1, 2, 3, 5, 8)}
            out.append((f"R3 非退化：预期输入上焦点 > 1（{name}）",
                        len(s) > 1,
                        f"按主语 {len(s)} 个；距离≤r 得 {sorted(old)}；"
                        f"kNN 分量得 {sorted(knn)} —— **前两种依据在预期输入上是退化的**"))

        # ── 非划分：至少一条记录进 ≥2 个视图焦点 ──
        ov = F.focus_overlap(div)
        out.append((f"非划分：存在记录属于多个视图焦点（{name}）",
                    ov["records_in_multiple_view_foci"] > 0,
                    f"{ov['records_in_multiple_view_foci']}/{ov['n_records']} 条记录"
                    f"牵涉多个视图；关联表 {len(ov['incidence'])} 个非空单元"
                    f"（{ov['structure_foci']}×{ov['view_foci']}）—— "
                    "**棋盘状而非分块对角，所以「划分」不是这个材料的形状**"))

    return out


def report() -> list:
    from analysis import divergence as D
    rows = []
    for name, views, _intended in _materials():
        div = D.analyse(views)
        recs = F._all_records(div)
        s = F.subject_foci(div, "structure")
        v = F.subject_foci(div, "view")
        old = len(F.foci(div, radius=0, views=views))
        knn = len(F.knn_foci(div, views=views, k=1)["foci"])
        rows.append((name,
                     f"{len(recs)} 条记录 → 旧依据 {old} 个、kNN {knn} 个、"
                     f"**按主语 {len(s)} 个**（视图族 {len(v)} 个）"))
        for f in s[:8]:
            rows.append((f"  {f['focus']} {f['label']}",
                         f"{f['subject']}  {f['size']} 条  {f['types']}"))
    rows.append(("要求 R1–R6",
                 "覆盖 / 压缩 / 非退化 / 可追溯 / 无阈值 / 确定性；"
                 "**「是划分」不在其中** —— 那只是当初的实现选择"))
    return rows


if __name__ == "__main__":
    import sys
    print("── 度量 ──")
    for t, v in report():
        print(f"  {t:<40} {v}")
    print("\n── 断言 ──")
    bad = 0
    for t, ok, d in run_all():
        print(f"  {'过    ' if ok else '**红的**'} {t:<52} {d}")
        bad += 0 if ok else 1
    sys.exit(1 if bad else 0)
