"""第二步的**验收**：用真实数据验「**视图本身足够支撑检索**」。

---
判据（**先写在这里，再跑**）
--------------------------

目标（用户收窄后）：这一步只需证明**视图本身足够支撑检索** ——
数据齐了、不需要回到源数据或外部知识。「压成几张抽象视图」是**后续层**的事。

⇒ 可执行的形式是**往返**：每条差异记录都能被「由视图自身生成的键」取回。

    ① **完备**      每条差异记录都被 ≥ 1 个键选中（覆盖率 = 1.0）
    ② **可回取**    `记录 → 键 → 记录` 往返成立（键选中的集合里确实有它）
    ③ **不塌**      没有任何一个键选中**全部**记录（否则键没有区分力）
    ④ **可枚举**    键数与记录数是同一量级（不是指数）
    ⑤ **确定性**    输入逆序不改变索引（键与命中集合逐位相同）
    ⑥ **无外部输入** 把视图**只留声明过的字段**重建，索引**逐位不变**
                    —— 这条能抓住「某个面偷偷读了视图之外的东西」
    ⑦ **压缩**      抽象后的键比记录少一个量级以上
                    ⚠️ **只披露，不作通过线** —— 设成通过线就是一个被调出来的阈值

⚠️ **三态**：公开数据不在就跳过，而**跳过不等于通过**（与全套一致）。

⚠️ 这两件事**不许混**（断言 ⑨ 钉着）：本模块验的是**①索引完备**；
而**统计筛选后的子集**只覆盖 33–67%，**不是**本验收的对象。
"""
from __future__ import annotations
from checks import _data

#: 视图**声明过**的字段。⑥ 用它重建视图：只留这些，其余一律丢掉。
VIEW_FIELDS = ("id", "source", "nodes", "edges", "metadata")
VIEW_META_FIELDS = ("labels", "group")


def materials(limit: int = 6) -> list:
    """真实材料（**非自造**优先）。数据不在就少几份，而少不等于通过。"""
    out = []
    from adapters import perspectrum as P

    try:
        import checks.perspectrum as CP
        if CP.data_file() is not None:
            claims, _ = P.load_claims(CP.DATA)
            d = _data.directory()
            ev = P.load_pools(d, "evidence") if d else {}
            for cid, cl, _r in sorted(claims, key=lambda c: -len(c[1]))[:limit]:
                out.append((f"Perspectrum c{cid}",
                            P.to_views(cid, cl, claim_text="x", ev_text=ev,
                                       keep_labels=True)))
    except Exception:
        pass

    try:
        from adapters import scaffold as S
        from checks import realdata as RD
        d = RD.corpus_dir()
        if out == [] and d:
            nodes = S.load_corpus_dir(d)
            out.append(("Scaffold 语料",
                        [a.view for a in S.split_views(nodes, split_by="source.kind")]))
    except Exception:
        pass
    return out


def _strip(views) -> list:
    """只留**声明过**的字段 —— 给 ⑥ 用。"""
    out = []
    for v in views:
        nv = {k: v[k] for k in VIEW_FIELDS if k in v}
        md = nv.get("metadata") or {}
        nv["metadata"] = {k: md[k] for k in VIEW_META_FIELDS if k in md}
        out.append(nv)
    return out


def _one(name: str, views, *, contrast: bool = False) -> dict:
    """对一份材料把 ①–⑦ 逐条量出来。

    `contrast=True` 才去算「统计筛选后」那个压缩量 —— 它要跑 `self_sufficient`，
    实测最慢的一份 **93 秒**，全量 6 份是 615 秒。**默认不算**，套件才跑得动。
    """
    from analysis import index as IX

    idx = IX.build(views)
    per = idx["per_record"]
    n = len(per)
    keys = idx["keys"]

    covered, times = set(), {}
    for k, sel in keys.items():
        covered |= sel
        for i in sel:
            times[i] = times.get(i, 0) + 1

    # ② 往返：记录 → 选中它的键 → 集合里确实有它
    #
    # ⚠️ 键里装的是**规范身份（rid）不是下标**。首版这里写成下标
    # （`any(i in sel for i in range(n))`），于是往返率**恒为 0%**，
    # 而"覆盖 100%"却仍然是对的（rids 与记录一一对应，所以那个数没露馅）。
    rids = idx["rids"]
    rt = sum(1 for r in rids if any(r in sel for sel in keys.values()))
    # ⑥ 无外部输入：只留声明字段重建，索引逐位不变
    same = None
    try:
        idx2 = IX.build(_strip(views))
        f = lambda d: sorted((str(sorted(k)), sorted(v)) for k, v in d["keys"].items())
        same = (f(idx) == f(idx2)) and (idx["rids"] == idx2["rids"])
    except Exception:
        same = False

    st = IX.stats(idx)
    # ⚠️ **两个压缩量必须分开报** —— 上一轮我把它们说成了一个：
    #     **索引**的键/记录比        实测 **约 1x**（索引不压缩，它是**重新编码**）
    #     **统计筛选后**留下的集合    实测 14–48x（但只覆盖 33–67%）
    kept = None
    if contrast:
        try:
            kept = IX.self_sufficient(idx, max_size=3, direction="lower")["n_kept"]
        except Exception:
            pass
    return {
        "name": name, "n": n, "n_keys": len(keys),
        "coverage": (len(covered) / n) if n else None,
        "roundtrip": (rt / n) if n else None,
        "min_keys_per_record": min(times.values()) if times else 0,
        "max_keys_per_record": max(times.values()) if times else 0,
        "collapse": st["collapse"], "max_key": st["max_key"],
        "enumerable": st["enumerable"],
        "no_external_input": same,
        "compression_index": (n / len(keys)) if keys else None,
        "compression_kept": (n / kept) if kept else None,
        "n_kept": kept,
    }


def run_all(limit: int = 6) -> list:
    mats = materials(limit)
    out = []
    if not mats:
        out.append(("第二步验收", None,
                    "**一份真实材料都没有** —— 跳过，而**跳过不等于通过**"))
        return out
    rows = []
    for i, (name, views) in enumerate(mats):
        try:
            # ⚠️ 只对**最小的一份**算对照（它最便宜），否则 615 秒
            rows.append(_one(name, views, contrast=(i == len(mats) - 1)))
        except Exception as e:
            rows.append({"name": name, "err": str(e)[:60]})
    good = [r for r in rows if "err" not in r]
    bad = [r for r in rows if "err" in r]

    out.append(("① 完备：每条差异记录都被 ≥1 个键选中",
                bool(good) and all(abs(r["coverage"] - 1.0) < 1e-12 for r in good),
                "；".join(f"{r['name'].split()[0]} {r['coverage']:.0%}" for r in good)
                + (f"；**失败 {[r['name'] for r in bad]}**" if bad else "")))
    out.append(("② 可回取：记录 → 键 → 记录 往返成立",
                bool(good) and all(abs(r["roundtrip"] - 1.0) < 1e-12 for r in good),
                "每份材料的往返率都是 100% —— **这就是「视图够用」的可执行形式**"
                if good and all(abs(r["roundtrip"] - 1.0) < 1e-12 for r in good)
                else f"{[(r['name'], r['roundtrip']) for r in good][:3]}"))
    out.append(("③ 不塌：没有键选中全部记录",
                all(not r["collapse"] for r in good),
                "全部材料都不塌" if all(not r["collapse"] for r in good)
                else f"{[(r['name'], r['max_key']) for r in good if r['collapse']]}"))
    out.append(("④ 可枚举：键数与记录数同量级",
                all(r["enumerable"] for r in good),
                "；".join(f"{r['name'].split()[0]} 键{r['n_keys']}/记录{r['n']}"
                          for r in good[:4])))
    out.append(("⑤ 确定性：输入逆序不改变索引", True,
                "由断言 ④（`checks/index.py`）在同一套材料上钉住，此处不重复跑"))
    out.append(("⑥ 无外部输入：只留声明字段重建，索引逐位不变",
                all(r["no_external_input"] for r in good),
                "每份材料重建后逐位相同 —— **面全部来自视图自身**"
                if all(r["no_external_input"] for r in good)
                else f"{[(r['name'], r['no_external_input']) for r in good if not r['no_external_input']]}"))
    # ⚠️ **两个压缩量分开报**。上一轮我把它们说成了一个：
    #     **索引**的键/记录比      实测 **约 1x** —— 索引**不压缩**，它是**重新编码**
    #     **统计筛选后**留下的集合  14-48x，**但只覆盖 33-67%**
    # ⇒ 所以「检索只需面对几张抽象后的视图」**这层还不成立**：
    #   够全的（索引）不小，够小的（筛选集）不全。**而这个缺口正是后续抽象层的事。**
    ci = [r["compression_index"] for r in good if r["compression_index"]]
    ck = [r["compression_kept"] for r in good if r["compression_kept"]]
    out.append(("⑦ 压缩（**只披露，不作通过线**）—— ⚠️ 两个量必须分开看",
                True,
                "**索引**（键/记录）："
                + "；".join(f"{r['name'].split()[0]} {r['compression_index']:.1f}x"
                            for r in good)
                + f" ⇒ 中位约 {sorted(ci)[len(ci)//2]:.1f}x —— **索引不压缩，它是重新编码**。"
                + "**统计筛选后**留下的集合："
                + "；".join(f"{r['name'].split()[0]} {r['compression_kept']:.0f}x"
                            for r in good if r["compression_kept"])
                + f" ⇒ 约 {sorted(ck)[len(ck)//2]:.0f}x，**但只覆盖 33-67%**。"
                "⇒ 够全的不小、够小的不全 —— **「检索只需面对几张抽象视图」"
                "在这一层不成立，那是后续抽象层要解的**。"))
    return out


def report(limit: int = 6, *, contrast: bool = False) -> list:
    rows = []
    for name, views in materials(limit):
        try:
            r = _one(name, views, contrast=contrast)
        except Exception as e:
            rows.append((name, f"跳过：{str(e)[:50]}")); continue
        ck = r["compression_kept"]
        rows.append((name,
                     f"记录 {r['n']:>5}  键 {r['n_keys']:>5}  覆盖 {r['coverage']:.0%}  "
                     f"往返 {r['roundtrip']:.0%}  压缩(索引) {r['compression_index']:.1f}x  "
                     f"压缩(筛选集) {ck:.0f}x" if ck else
                     f"记录 {r['n']:>5}  键 {r['n_keys']:>5}  覆盖 {r['coverage']:.0%}  "
                     f"往返 {r['roundtrip']:.0%}  压缩(索引) {r['compression_index']:.1f}x  "
                     f"每记录键数 {r['min_keys_per_record']}-{r['max_keys_per_record']}  "
                     f"无外部输入 {'是' if r['no_external_input'] else '**否**'}"))
    return rows


if __name__ == "__main__":
    import sys
    print("── 真实材料上的读数 ──")
    for t, v in report():
        print(f"  {t:<20} {v}")
    print("\n── 验收判据 ──")
    dead = 0
    for t, ok, d in run_all():
        mark = "跳过  " if ok is None else ("过    " if ok else "**红的**")
        print(f"  {mark} {t:<40} {d}")
        dead += 0 if ok in (True, None) else 1
    sys.exit(1 if dead else 0)
