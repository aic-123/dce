"""反例扫描 —— 每条结论都在一整片配置上撞一遍，而不是在一个点上成立。

---
为什么要它
---------

上一轮的全部结论都是在**一个标题配置**上得出的，而我后来量出那套语料库有三个毛病：

    可达率只有 38%（62% 被生成器自己的约束拒掉）
    形状覆盖近乎为零（空视图 0%、无边视图 0%、不相交 2%、相等 0%）
    100% 都是「四类各占专用视图」的干净情形

所以「Coverage 恒等于 1」「划分等于 union+frequency」这些说法，
当时只在一个点上验过。**一个点上的结论和一个扫描过的结论，在报告里长得一样。**

本模块把结论变成**待检验的命题**，在每个配置上判一次，并**报出反例**。

---
断言与度量的分界（沿用本仓库一贯的规矩）
--------------------------------------

    `run_all()`   只放**必须处处成立**的命题。有一条反例就是红的。
    `report()`    放**预期会有反例**的命题：召回率、焦点数、压缩比范围。
                  它们有数字但不该有「过/不过」—— 没有基线数据之前，
                  任何「召回 ≥ 0.9 算过」都是拍出来的线（§T0.3）。
"""

from __future__ import annotations

import time

# ── 配置网格：骨架 × 分量 × 规模 × 植入 × 形状 ──────────────────────
TOPOLOGIES = ("random", "forest", "chain", "star")
KNOBS = (
    {},
    {"empty_views": 1},
    {"node_only_views": 1},
    {"disjoint_views": 1},
    {"equal_views": 1},
)
PLANTS = (
    {},
    {"contradictions": 1, "omissions": 1},
    {"contradictions": 2, "omissions": 3, "refinements": 1, "alternatives": 1},
)


def grid() -> list:
    """确定性的配置网格。目标量级：数百个配置、每个秒级以下。"""
    out = []
    for topo in TOPOLOGIES:
        for k in (1, 3):
            for nv in (2, 3, 5):
                for nc in (4, 8):
                    for plant in PLANTS:
                        for knob in KNOBS:
                            spec = {"n_views": nv, "n_core": nc, "private": 1,
                                    "topology": topo, "n_components": k}
                            spec.update(plant)
                            spec.update(knob)
                            out.append(spec)
    return out


def build(spec: dict, seed: int = 20261020):
    """按 spec 造 `(views, truth)`。骨架参数与视图参数共用一个 spec。"""
    from generators import synthetic as SYN
    topo = spec.get("topology", "random")
    k = spec.get("n_components", 1)
    nc = spec.get("n_core", 6)
    base = SYN.base_graph(n_nodes=max(24, nc * 3), n_edges=max(40, nc * 5),
                          seed=seed, topology=topo, n_components=k)
    return SYN.make(base, spec, seed=seed + 1)


# ── 待检验的命题 ───────────────────────────────────────────────────
def _units(syn, views):
    from analysis import consensus as C
    from analysis import synthesis as S
    cons = {(r["unit"]["kind"], r["unit"]["key"]) for r in syn["consensus"]["records"]}
    got = set()
    for u in C.universe(views):
        if u in cons:
            got.add(u)
    for rec in syn["divergence"]:
        t = rec["type"]
        if t in ("omission", "refinement"):
            got.add((rec["unit"]["kind"], rec["unit"]["key"]))
        elif t == "contradiction":
            for rel in rec["relations"]:
                got.add(("edge", (rec["from"], rec["to"], rel)))
        elif t == "alternative":
            for _v, targets in rec["views"].items():
                for x in targets:
                    got.add(("edge", (rec["source"], x, rec["relation"])))
    return got, cons


def claim_coverage_one_and_no_phantom(views, truth, syn):
    """C1：Coverage ≡ 1，且合成里不出现源视图没有的单元（无幻影）。

    ⚠️ **幻影才是 bug，Coverage=1 是推论。** 上一轮把两件事混在一起报了，
    这里分开：幻影一律算反例；Coverage<1 也算反例，但原因不同（那说明有单元
    既不是共识、又没被任何一条分歧记录点到）。
    """
    from metrics import coverage as COV
    cov = COV.coverage(views, syn)
    if cov["phantom"]:
        return False, f"幻影 {cov['phantom'][:2]}"
    if cov["value"] != 1.0:
        return False, f"Coverage={cov['value']:.4f}，未解释 {cov['unexplained'][:2]}"
    return True, ""


def claim_partition_equals_frequency(views, truth, syn):
    """C2：DCE 的共识/分歧划分 == union+frequency 的划分。

    上一轮最重要的发现。**它应当在每个配置上成立** —— 两者在定义上就是同一个
    （出现次数是否等于视图数）。有反例就说明实现与定义脱开了。
    """
    from checks import ablation as A
    fp = A.frequency_partition(views)
    dp = A.dce_partition(views)
    diff = [u for u in fp if fp[u] != dp.get(u)]
    if diff:
        return False, f"划分不同 {len(diff)} 处，例 {diff[:2]}"
    return True, ""


def claim_records_are_definitionally_valid(views, truth, syn):
    """C3：每条报出来的记录都满足该类的定义。

    与 `checks/reconstruction.py` 里那条同一件事，这里在**每个配置**上跑一遍 ——
    因为定义校验的价值恰恰在于「换一种形状它还成立吗」。
    """
    from checks import reconstruction as R
    problems = R._definition_ok(views, syn)
    if problems:
        return False, f"{len(problems)} 条不符，例 {problems[0][0][:56]}"
    return True, ""


def claim_no_forbidden_keys(views, truth, syn):
    """C4：产物里没有评分 / 权重 / 真值键（§二十）。"""
    from analysis import synthesis as S
    hits = S.forbidden_keys_in(syn)
    return (not hits), (f"命中 {hits[:3]}" if hits else "")


def claim_no_pollution(views, truth, syn):
    """C5：合成不污染源视图（§C9 #9 / §C7.1 ④ 的单向性）。

    ⚠️ 这里在每个配置上重算指纹，而不是只测标题配置 ——
    单向性是**不变量**，不变量在每个配置上都必须成立。
    """
    from core import view as V
    import json
    before = {v["id"]: V.fingerprint(v) for v in views}
    snap = json.dumps(views, sort_keys=True, ensure_ascii=False)
    _ = S_build_again(views)
    after = {v["id"]: V.fingerprint(v) for v in views}
    if before != after:
        bad = [k for k in before if before[k] != after.get(k)]
        return False, f"视图指纹变了：{bad}"
    if json.dumps(views, sort_keys=True, ensure_ascii=False) != snap:
        return False, "视图内容变了（哈希相同但字段变了）"
    return True, ""


def S_build_again(views):
    from analysis import synthesis as S
    return S.build(views)


def claim_compression_modes_ordered(views, truth, syn):
    """C6：focused 不比 flat 差（概括不该比罗列还占地方）。"""
    from metrics import compression as CMP
    k = CMP.compression(views, syn)["all_modes"]
    if not (k["focused"] >= k["flat"]):
        return False, f"focused {k['focused']:.2f} < flat {k['flat']:.2f}"
    return True, ""


ASSERT_CLAIMS = (
    ("C1 Coverage≡1 且无幻影", claim_coverage_one_and_no_phantom),
    ("C2 划分 == union+frequency", claim_partition_equals_frequency),
    ("C3 每条记录过定义校验", claim_records_are_definitionally_valid),
    ("C4 产物无评分/权重/真值", claim_no_forbidden_keys),
    ("C5 合成不污染源视图", claim_no_pollution),
    ("C6 focused ≥ flat", claim_compression_modes_ordered),
)


# ── 度量类命题：预期会有反例，只报分布 ─────────────────────────────
def _reclassified_subjects(truth, t) -> set:
    """这个配置里，**按定义**该算另一类的预埋项，投影到与 truth 同粒度。

    ⚠️ 没有这一步，「召回」会把两种完全不同的东西算成同一个 0：
        预埋的缺失被 refinement 正当地认领了（定义使然）
        预埋的缺失根本没被报出来（算法漏了）
    上一轮我用「precision 走定义校验」绕过了这个混淆，但那是**绕过**，不是测。
    """
    out = set()
    for r in truth.get("reclassified", []):
        if r["planted"] != t:
            continue
        s = r["subject"]
        if t in ("alternative", "contradiction"):
            out.add((s[0], s[1]))                   # 投影到 (source, relation) / (from, to)
        elif t == "omission":
            out.add((s[0], s[1], str(s[2])))
        elif t == "refinement":
            out.add((s[0], s[1], s[2], str(s[3])))
    return out


def measure_planted_recall(views, truth, syn) -> dict:
    """四类预埋的召回，**分三档报**。

        strict       预埋的类型 == 报出来的类型
        accounted    strict，或者「按定义该算另一类」已被记录在案
        unexplained  **既没报对、也不在重分类名单里 —— 这才是真的漏**

    上一轮只有 strict 一档，而它在干净的专用视图构造下永远是 1.000，
    于是「召回满分」这件事**掩盖了类型之间的真实歧义**。
    """
    from checks import reconstruction as R
    got = R._subjects(syn)
    want = R._truth_subjects(truth)
    out = {}
    for t in ("contradiction", "omission", "refinement", "alternative"):
        w, g = want.get(t, set()), got.get(t, set())
        rec = _reclassified_subjects(truth, t) & w
        n = len(w)
        out[t] = {
            "n": n,
            "strict": (len(w & g) / n) if n else None,
            "accounted": (len(w & (g | rec)) / n) if n else None,
            "unexplained": len(w - g - rec),
            "n_reclassified": len(rec),
        }
    return out


def measure_foci(views, truth, syn) -> int:
    return len(syn["foci"])


def measure_shape_features(views, truth, syn) -> dict:
    """这个配置实际表达出了哪些形状 —— 用来核对「旋钮真的生效了吗」。"""
    from analysis import consensus as C
    us = [C.units_of(v) for v in views]
    ns = [set(v["nodes"]) for v in views]
    return {
        "empty_view": any(not u for u in us),
        "node_only_view": any(not v["edges"] for v in views),
        "disjoint": any(not (ns[i] & ns[j]) for i in range(len(ns))
                        for j in range(i + 1, len(ns))),
        "equal_views": any(us[i] == us[j] for i in range(len(us))
                           for j in range(i + 1, len(us))),
    }


def scan(limit: int | None = None) -> dict:
    """跑完整片网格。返回每条命题的统计与反例。"""
    from analysis import synthesis as S
    specs = grid()
    if limit:
        specs = specs[:limit]

    stats = {name: {"n": 0, "ok": 0, "bad": []} for name, _ in ASSERT_CLAIMS}
    recalls = {t: {"n": 0, "strict_full": 0, "acct_full": 0,
                   "min_strict": None, "min_acct": None,
                   "unexplained": 0, "reclassified": 0, "bad": []}
               for t in ("contradiction", "omission", "refinement", "alternative")}
    foci_hist, shapes, skipped = {}, {}, []
    t0 = time.time()

    for spec in specs:
        try:
            views, truth = build(spec)
            syn = S.build(views)
        except ValueError as e:
            skipped.append((spec, str(e).splitlines()[0][:48]))
            continue

        for name, fn in ASSERT_CLAIMS:
            s = stats[name]
            s["n"] += 1
            try:
                ok, why = fn(views, truth, syn)
            except Exception as e:                       # noqa: BLE001
                ok, why = False, f"{type(e).__name__}: {e}"
            if ok:
                s["ok"] += 1
            elif len(s["bad"]) < 4:
                s["bad"].append((_label(spec), why))

        for t, d in measure_planted_recall(views, truth, syn).items():
            if d["strict"] is None:
                continue
            r = recalls[t]
            r["n"] += 1
            r["strict_full"] += 1 if d["strict"] >= 1.0 else 0
            r["acct_full"] += 1 if d["accounted"] >= 1.0 else 0
            r["min_strict"] = (d["strict"] if r["min_strict"] is None
                               else min(r["min_strict"], d["strict"]))
            r["min_acct"] = (d["accounted"] if r["min_acct"] is None
                             else min(r["min_acct"], d["accounted"]))
            r["unexplained"] += d["unexplained"]
            r["reclassified"] += d["n_reclassified"]
            if d["accounted"] < 1.0 and len(r["bad"]) < 4:
                r["bad"].append((_label(spec),
                                 f"strict {d['strict']:.2f} / accounted "
                                 f"{d['accounted']:.2f} / 真漏 {d['unexplained']}"))

        nf = measure_foci(views, truth, syn)
        foci_hist[nf] = foci_hist.get(nf, 0) + 1
        for k, v in measure_shape_features(views, truth, syn).items():
            if v:
                shapes[k] = shapes.get(k, 0) + 1

    return {"stats": stats, "recalls": recalls, "foci": foci_hist,
            "shapes": shapes, "n_specs": len(specs), "n_skipped": len(skipped),
            "skipped": skipped[:6], "seconds": time.time() - t0,
            "n_evaluated": sum(s["n"] for s in stats.values()) // max(1, len(ASSERT_CLAIMS))}


def _label(spec: dict) -> str:
    bits = [spec.get("topology", "?")[:4], f"k{spec.get('n_components', 1)}",
            f"v{spec.get('n_views')}", f"c{spec.get('n_core')}"]
    for k in ("contradictions", "omissions", "refinements", "alternatives",
              "empty_views", "node_only_views", "disjoint_views", "equal_views"):
        if spec.get(k):
            bits.append(f"{k[:4]}{spec[k]}")
    return "/".join(bits)


def report() -> list:
    r = scan()
    rows = [("扫描规模",
             f"{r['n_specs']} 个配置，建出来 {r['n_evaluated']}，"
             f"被拒 {r['n_skipped']}，用时 {r['seconds']:.1f}s")]
    for name, _ in ASSERT_CLAIMS:
        s = r["stats"][name]
        mark = "处处成立" if s["ok"] == s["n"] else f"**反例 {s['n'] - s['ok']} 个**"
        rows.append((f"  {name}", f"{s['ok']}/{s['n']}  {mark}"
                     + (f"  例：{s['bad'][0][0]} → {s['bad'][0][1]}" if s["bad"] else "")))
    rows.append(("四类预埋召回（分三档）", "strict = 类型报对 / "
                 "accounted = 或按定义该算另一类且已记录 / 真漏 = 两者都不是"))
    for t, d in r["recalls"].items():
        ms = "—" if d["min_strict"] is None else f"{d['min_strict']:.2f}"
        ma = "—" if d["min_acct"] is None else f"{d['min_acct']:.2f}"
        rows.append((f"    {t}",
                     f"strict 满分 {d['strict_full']}/{d['n']}（最低 {ms}）｜"
                     f"accounted 满分 {d['acct_full']}/{d['n']}（最低 {ma}）｜"
                     f"重分类 {d['reclassified']} 条｜**真漏 {d['unexplained']} 条**"
                     + (f"  例：{d['bad'][0][0]} → {d['bad'][0][1]}" if d["bad"] else "")))
    rows.append(("焦点数分布（机制真的在工作吗）",
                 "、".join(f"{k}个焦点×{v}" for k, v in sorted(r["foci"].items()))))
    rows.append(("表达出的形状（配置数）",
                 "、".join(f"{k} {v}" for k, v in sorted(r["shapes"].items()))))
    return rows


def run_all() -> list:
    """只放**必须处处成立**的命题。有一条反例就是红的。"""
    r = scan()
    out = []
    for name, _ in ASSERT_CLAIMS:
        s = r["stats"][name]
        detail = f"{s['ok']}/{s['n']} 个配置成立"
        if s["bad"]:
            detail += f"；反例：{s['bad'][0][0]} → {s['bad'][0][1]}"
        out.append((f"扫描 · {name}", s["ok"] == s["n"] and s["n"] > 0, detail))
    return out
