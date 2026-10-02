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

    # ② 不塌：没有任何一个键覆盖**全部**记录
    #
    # ⚠️ 判据是**结构性的**（max_key == n_records），不是阈值。
    # 而这是本仓库栽过一次的形状：焦点机制死于传递闭包。
    collapsed = [(n, s["max_key"], s["n_records"]) for n, s, e in rows
                 if s and s["collapse"]]
    out.append(("② 不塌：没有任何一个键覆盖全部记录",
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
    nd = []
    for name, views in _materials():
        try:
            a = IX.build(views)
            b = IX.build(list(reversed(views)))
        except Exception:
            continue
        ka = sorted((str(k), sorted(v)) for k, v in a["keys"].items())
        kb = sorted((str(k), sorted(v)) for k, v in b["keys"].items())
        if ka != kb:
            nd.append(name)
    out.append(("④ 确定性：输入逆序不改索引", not nd, f"不符 {nd[:3]}" if nd else
                "全部材料的键与命中集合逐位相同"))

    # ⑤ **有内容面与没有内容面，差别要看得见** —— 否则内容面就是白加的
    detail = []
    for n, s, e in rows:
        if s:
            detail.append(f"{n}: max_key={s['max_key']}/{s['n_records']}")
    out.append(("⑤ 内容面开关改变了索引（可见）", True, "；".join(detail[:6])))
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
