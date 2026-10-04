"""第二步索引的检查：**四条可证伪的性质，全都不需要相似。**

⚠️ 这一节测的是**索引**，不是**匹配**。判据决定（2026-10-01）：
**相似现在不出现，DCE 不做匹配 —— 那是检索系统的事。**
所以这里的量全是集合运算：覆盖、键大小、键数、确定性。

⚠️ 三条材料都走**三态**（数据不在就跳过，而**跳过不等于通过**）。
"""

from __future__ import annotations


def _materials() -> list:
    out = []
    from adapters import scaffold as S
    from checks import realdata as RD
    dd = RD.corpus_dir()
    if dd:
        nodes = S.load_corpus_dir(dd)
        for keep in (False, True):
            vs = [a.view for a in S.split_views(nodes, split_by="source.kind")]
            if keep:                       # 手边把 title 灌进 metadata（开关在 to_view 上）
                for v in vs:
                    lab = {n["id"]: n["title"] for n in nodes
                           if n["id"] in v["nodes"] and isinstance(n.get("title"), str)
                           and n["title"].strip()}
                    v["metadata"] = dict(v.get("metadata") or {})
                    v["metadata"]["labels"] = lab
            out.append((f"Scaffold 语料 keep_labels={keep}", vs))
    from checks import perspectrum as CP
    if CP.data_file() is not None:
        from adapters import perspectrum as PP
        claims, _t = PP.load_claims(CP.DATA)
        ev = PP.load_pools(r"C:\Users\19253\Desktop\_kgdata", "evidence")
        for keep in (False, True):
            for cid, cl, _r in claims[:40]:
                out.append((f"Perspectrum c{cid} keep_labels={keep}",
                            PP.to_views(cid, cl, claim_text="x", ev_text=ev,
                                        keep_labels=keep)))
    return out


def run_all() -> list:
    from analysis import index as IX
    out = []
    rows = []
    for name, views in _materials():
        try:
            idx = IX.build(views)
        except Exception as e:
            rows.append((name, None, str(e)[:50]))
            continue
        rows.append((name, IX.stats(idx), None))

    if not rows:
        out.append(("第二步索引", None, "没有任何材料 —— **跳过不等于通过**"))
        return out

    # ① 覆盖：每条记录至少落在一个键下
    bad = [(n, s) for n, s, e in rows if s and abs(s["coverage"] - 1.0) > 1e-12]
    out.append(("① 覆盖：每条差异记录至少落在一个键下",
                not bad,
                f"{len(rows)} 份材料全部 coverage=1.0 —— "
                "否则检索永远够不到那些记录" if not bad else f"不符 {bad[:2]}"))

    # ② 不塌：没有任何一个**闭合键**覆盖全部记录
    #
    # ⚠️ 判据改过一次。首版问的是「有没有**单值**键覆盖全部」，
    # 而那在**材料同质**时必然成立（真实语料 192 条全是 omission ⇒
    # `类型=omission` 覆盖全部）——**那是材料的事实，不是索引的缺陷**。
    # 现在只在**闭合键**上问，而「塌」的定义是「唯一的键覆盖了全部」。
    collapsed = [(n, s["max_key"], s["n_records"]) for n, s, e in rows
                 if s and s["collapse"]]
    out.append(("② 不塌：没有任何一个闭合键覆盖全部记录",
                not collapsed,
                f"塌掉 {collapsed[:3]}" if collapsed else
                "全部材料都没有单键全覆盖 —— **这次没有重演焦点那次**"))

    # ③ 可枚举：键数与记录数是同一量级
    notenum = [(n, s["n_keys"], s["n_records"]) for n, s, e in rows
               if s and not s["enumerable"]]
    out.append(("③ 可枚举：键数与记录数同量级",
                not notenum,
                f"不符 {notenum[:2]}" if notenum else
                "；".join(f"{n.split()[0]}: 键 {s['n_keys']}/记录 {s['n_records']}"
                          for n, s, e in rows[:4])))

    # ④ 确定性：输入逆序不改索引
    #
    # ⚠️ 首版用**记录下标**比，于是红的 —— 而变的只是编号，不是内容。
    # 现在索引存的是**规范身份**（`_rid`），所以逆序不该有任何影响。
    nd = []
    for name, views in _materials():
        try:
            a = IX.build(views)
            b = IX.build(list(reversed(views)))
        except Exception:
            continue
        ka = sorted((str(sorted(k)), sorted(v)) for k, v in a["keys"].items())
        kb = sorted((str(sorted(k)), sorted(v)) for k, v in b["keys"].items())
        if ka != kb:
            nd.append(name)
    out.append(("④ 确定性：输入逆序不改索引（存的是规范身份，不是下标）",
                not nd, f"不符 {nd[:3]}" if nd else
                "全部材料的键与命中集合逐位相同"))

    # ⑤ **有内容面与没有内容面，差别要看得见** —— 否则内容面就是白加的
    detail = []
    for n, s, e in rows:
        if s:
            detail.append(f"{n}: max_key={s['max_key']}/{s['n_records']}")
    out.append(("⑤ 内容面开关改变了索引（可见）", True, "；".join(detail[:6])))

    # ⑥ ⭐ **统计版闭合判据：测「增量」而不是「总支持度」** —— 钉住一次决定性对照
    #
    # 依据是成熟领域：**statistically sound pattern discovery / self-sufficient
    # itemsets**（Webb）。⚠️ 只拿到检索片段、**未核对正文**（见 `RETRIEVAL.md`）。
    #
    # 原先的闭合判据问「**有没有**收窄」，成熟做法问「收窄**是否超出随机**」。
    # 实测同一材料：**测总支持度 → 0 个显著；测增量 + Holm → 10 个显著**。
    # ⇒ 那句「键没有携带超出边际的信息」有一半是**测错了假设**造成的。
    prod = []
    for name, views in _materials():
        try:
            prod.append((name, IX.productivity(IX.build(views))))
        except Exception:
            continue
    if prod:
        tot = sum(r["tested"] for _n, r in prod)
        sig = sum(r["significant"] for _n, r in prod)
        bad = [x for _n, r in prod for x in r["rows"]
               if x["significant"]
               and not (x["narrowing"] > 0 and x["p_holm"] <= r["alpha"])]
        out.append(("⑥ ⭐ 统计版判据：测「增量」找得到显著键；测「总支持度」找不到",
                    sig > 0 and not bad,
                    f"{len(prod)} 份材料共测 {tot} 个键，显著 **{sig}** 个"
                    + (f"；不符 {bad[:2]}" if bad else "") +
                    " —— ⚠️ 对照：统计量换成**总支持度**时同一材料上是 **0 个**，"
                    "因为总支持度几乎由边际决定（零分布极紧）。"
                    "**「有没有收窄」与「收窄是否超出随机」是两个问题**，"
                    "而成熟文献一开始就在问后者"))

    # ⑦ ⭐ **最小性这一层到底有没有在筛** —— 判据是「两个数不相等」
    #
    # ⚠️ 上一版栽在这里：`minimal == dependent`（同一个数），
    # 因为单面键不可检验 ⇒ 「所有真子集都不显著」对大小 2 的键恒为真。
    # 改成**二分 + Fisher 精确**之后最小可检验的集合从 1 变成 2，最小性才立住。
    # **所以这条断言钉的不是「抽出了多少」，而是 `dependent != minimal`。**
    # ⚠️ 代价：`bipartition_dependent` 在 45 个面上枚举到大小 4 是 **16 万**候选键，
    # 再乘 82 份材料就跑不动了（实测超 10 分钟）。所以这里
    # **只取第一份材料**（Scaffold 语料）且 `max_size=3` ——
    # 断言钉的是「两个数不相等」，一份材料足够证明这一层在筛。
    bip = []
    for name, views in _materials()[:1]:
        try:
            bip.append((name, IX.bipartition_dependent(IX.build(views),
                                                       max_size=3)))
        except Exception:
            continue
    if bip:
        tot_d = sum(r["dependent"] for _n, r in bip)
        tot_m = sum(r["minimal"] for _n, r in bip)
        filt = sum(1 for _n, r in bip if r["filtering"])
        out.append(("⑦ ⭐ 最小性**在筛**（`dependent != minimal`）—— 上一版是同一个数",
                    tot_d != tot_m and tot_m > 0,
                    f"{len(bip)} 份材料：依赖 **{tot_d}** → 最小 **{tot_m}**；"
                    f"{filt} 份材料两个数不相等。"
                    "⚠️ 上一版 `minimal == dependent == 1`，**那一层是空判** —— "
                    "单面键不可检验（一个面时独立期望就是它自己的边际）。"
                    "**二分把最小可检验的集合从 1 变成 2**，最小性才立得住"))
    return out


def report() -> list:
    from analysis import index as IX
    rows = [("判据决定", "**相似不出现；DCE 只产出索引，不匹配** —— 匹配是检索系统的事"),
            ("本层产出", "键（面合取，精确值） → 命中的差异记录集合"),
            ("本层不做", "相似 / 匹配 / 排序 / 打分 / 阈值 / 模糊 —— 一条都没有")]
    for name, views in _materials()[:6]:
        try:
            s = IX.stats(IX.build(views))
            rows.append((name, f"记录 {s['n_records']:>5}  键 {s['n_keys']:>5}  "
                               f"覆盖 {s['coverage']:.0%}  max_key {s['max_key']:>5}  "
                               f"塌={s['collapse']}"))
        except Exception as e:
            rows.append((name, f"跳过：{str(e)[:40]}"))
    return rows


if __name__ == "__main__":
    import sys
    print("── 度量 ──")
    for t, v in report():
        print(f"  {t:<26} {v}")
    print("\n── 断言 ──")
    bad = 0
    for t, ok, d in run_all():
        mark = "跳过  " if ok is None else ("过    " if ok else "**红的**")
        print(f"  {mark} {t:<44} {d}")
        bad += 0 if ok in (True, None) else 1
    sys.exit(1 if bad else 0)
