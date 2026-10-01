"""Test 3 Controlled Divergence（§十五）—— **四类必须能分别恢复**。

§十五 原文：

    人工植入：10 contradictions / 20 omissions / 10 refinements / 5 alternatives
    DCE 必须能够分别恢复它们。这个测试非常关键。

---
恢复率怎么算：按**主语**，不按单元
--------------------------------

这是本模块最要紧的一条设计，不这么算 precision 会因为定义问题而不是错误变差：

    hit           预埋的 (主语, 类型) 被报出来了
    type_confuse  主语对，但报成了别的类型       ← 真错误
    miss          主语根本没被报出来
    spurious      报出来的主语没被预埋            ← 需要人看，可能是定义使然

**为什么 spurious 不能直接算成错**：若 B 精炼了 A，则 B 多出来的那些单元
相对视图 C 而言**真的是 omission**（C 确实没有它们）。同一条记录
「相对 A 是 refinement、相对 C 是 omission」——那是两个主语，不是类型冲突。
把它算成错，等于要求 DCE 去猜我脑子里想的是哪个主语。

所以本模块把四者**分开报**，不合成一个 F1。一个把 type_confuse 和 spurious
抹平的数字，会让「算法错了」和「定义如此」看起来一样。

---
四类的「主语」定义
----------------

    consensus      单元本身
    contradiction   (from, to)
    omission        (视图 id, 单元)
    refinement      (粗视图 id, 细视图 id, 单元)
    alternative     (source, relation)

---
共识是**定义**，不是预埋
----------------------

共识的 ground truth 就是「全部视图单元集的交集」——那正是 DCE 的判据）。
所以这一项不是「恢复率」，是**恒等式核对**：算出来不一致就是 bug，不是精度问题。
"""

from __future__ import annotations

from analysis import consensus as C
from analysis import synthesis as S


def _subjects(syn) -> dict:
    """DCE 报出来的东西，按 (类型 → 主语集合) 归拢。"""
    out = {"consensus": set(), "contradiction": set(),
           "omission": set(), "refinement": set(), "alternative": set()}
    for rec in syn["consensus"]["records"]:
        u = (rec["unit"]["kind"], rec["unit"]["key"])
        out["consensus"].add(str(u))
    for rec in syn["divergence"]:
        t = rec["type"]
        if t == "contradiction":
            out[t].add((rec["from"], rec["to"]))
        elif t == "omission":
            out[t].add((rec["missing_in"],
                        rec["unit"]["kind"], str(rec["unit"]["key"])))
        elif t == "refinement":
            out[t].add((rec["coarse"], rec["fine"],
                        rec["unit"]["kind"], str(rec["unit"]["key"])))
        elif t == "alternative":
            out[t].add((rec["source"], rec["relation"]))
    return out


def _truth_subjects(truth) -> dict:
    out = {"consensus": set(), "contradiction": set(),
           "omission": set(), "refinement": set(), "alternative": set()}
    for u in truth["consensus"]:
        out["consensus"].add(str(u))
    for (a, b, r1, r2) in truth["contradiction"]:
        out["contradiction"].add((a, b))
    for (vi, kind, key) in truth["omission"]:
        out["omission"].add((vi, kind, str(key)))
    for (coarse, fine, kind, key) in truth["refinement"]:
        out["refinement"].add((coarse, fine, kind, str(key)))
    for item in truth["alternative"]:
        out["alternative"].add((item[0], item[1]))
    return out


def measure(spec: dict, seed: int = 20261003) -> dict:
    """跑一次植入 → 恢复的完整测量。"""
    from generators import synthetic as SYN
    base = SYN.base_graph(n_nodes=max(30, spec.get("n_core", 20) * 2),
                          n_edges=max(60, spec.get("n_core", 20) * 3), seed=seed)
    views, truth = SYN.make(base, spec, seed=seed + 1)
    syn = S.build(views)
    got = _subjects(syn)
    want = _truth_subjects(truth)

    res = {}
    for t in ("consensus", "contradiction", "omission", "refinement", "alternative"):
        w, g = want[t], got[t]
        other = set().union(*[v for k, v in got.items() if k != t]) if len(got) > 1 else set()
        hit = len(w & g)
        confuse = len((w - g) & other)
        miss = len(w - g - other)
        res[t] = {
            "planted": len(w), "reported": len(g), "hit": hit,
            "type_confuse": confuse, "miss": miss,
            "recall": (hit / len(w)) if w else None,
            "spurious": len(g - w),
        }
    return {"result": res, "views": len(views),
            "n_units": sum(len(C.units_of(v)) for v in views),
            "syn": syn, "truth": truth, "views_objs": views}


# ── 报出来的表（不进退出码：这是度量，不是判据）─────────────────────

HEADLINE = {"n_views": 16, "n_core": 40, "private": 3,
            "contradictions": 10, "omissions": 20,
            "refinements": 5, "alternatives": 5}


def report() -> list:
    """§十五 Test 3 的标题配置 + 几个旋钮档位。"""
    rows = []
    head = measure(HEADLINE)
    rows.append(("Test3 植入量（§十五 目标 10/20/10/5）",
                 "、".join(f"{t}={head['result'][t]['planted']}"
                           for t in ("contradiction", "omission",
                                     "refinement", "alternative"))))
    for t in ("consensus", "contradiction", "omission", "refinement", "alternative"):
        r = head["result"][t]
        rc = "—" if r["recall"] is None else f"{r['recall']:.3f}"
        rows.append((f"  {t}", f"植 {r['planted']:>3} / 报 {r['reported']:>3} / "
                               f"命中 {r['hit']:>3} / 类型串 {r['type_confuse']:>3} / "
                               f"漏 {r['miss']:>3} / 多报 {r['spurious']:>3} / 召回 {rc}"))
    rows.append(("视图数 / 单元总数",
                 f"{head['views']} / {head['n_units']}"))
    return rows


def _definition_ok(views, syn) -> list:
    """**逐条拿定义核对报出来的记录。** 返回 [(问题描述, 记录摘要)]。

    ⚠️ 这一条与下面的「恢复率」是两件不同的事，不能互相替代：

        precision  ← 定义校验。抓的是**算法报错了**（报了定义上不成立的记录）
        recall     ← 预埋对照。抓的是**算法漏了**（我埋的东西没被报出来）

    为什么不能拿「多报数」当 precision：私有边**按定义就是 omission**
    （它在别的视图里确实没有）。那不是错，是结构上必然的。
    第一版把这种也记成 spurious，于是多报 98 看起来像 precision 崩了 ——
    其实那 98 条条条成立。**用一个数代替定义校验，就会把「定义如此」
    和「算法错了」抹平成同一个数字。**
    """
    from analysis import consensus as C
    from analysis import divergence as D
    from core import edge as E

    problems = []
    by_id = {v["id"]: v for v in views}
    unit_of = {v["id"]: C.units_of(v) for v in views}

    for rec in syn["consensus"]["records"]:
        u = (rec["unit"]["kind"], rec["unit"]["key"])
        bad = [vid for vid in unit_of if u not in unit_of[vid]]
        if bad:
            problems.append((f"共识单元 {u!r} 不在 {bad} 里", rec))

    ref_covered = {v["id"]: D.refinement_covered(v, views) for v in views}
    contra_pairs = {(c["from"], c["to"]) for c in D.contradiction(views)}

    for rec in syn["divergence"]:
        t = rec["type"]
        if t == "contradiction":
            f, tt = rec["from"], rec["to"]
            rels = set(rec["relations"])
            if not any(E.exclusive(a, b) for a in rels for b in rels if a != b):
                problems.append((f"矛盾 {f}->{tt} 的两种关系并不互斥：{sorted(rels)}",
                                 rec))
            else:
                for r in rels:
                    holders = [vid for vid, us in unit_of.items()
                               if ("edge", (f, tt, r)) in us]
                    if not holders:
                        problems.append((f"矛盾声称有视图说过 {r}，但没有任何视图说过", rec))
        elif t == "omission":
            vid = rec["missing_in"]
            kind, key = rec["unit"]["kind"], rec["unit"]["key"]
            u = (kind, key)
            if vid not in by_id:
                problems.append((f"缺失记录指向不存在的视图 {vid}", rec))
                continue
            if u in unit_of[vid]:
                problems.append((f"缺失记录说 {vid} 没有 {u!r}，但它有", rec))
            if u in ref_covered[vid]:
                problems.append((f"{vid} 缺 {u!r}，但那是被 refinement 解释掉的", rec))
            if kind == "edge":
                f, tt, r = key
                if D._has_exclusive_counterpart(by_id[vid], f, tt, r):
                    problems.append((f"{vid} 在 {f}->{tt} 上说了互斥的话，"
                                     f"那该是 contradiction 不是 omission", rec))
                if (f, tt) in contra_pairs:
                    problems.append((f"{f}->{tt} 已被判为矛盾对，不该再报 omission", rec))
        elif t == "refinement":
            coarse, fine = rec["coarse"], rec["fine"]
            if coarse not in unit_of or fine not in unit_of:
                problems.append((f"refinement 指向不存在的视图 {coarse}/{fine}", rec))
                continue
            if not (unit_of[coarse] < unit_of[fine]):
                problems.append((f"refinement 声称 {coarse} ⊂ {fine}，实际不成立", rec))
            u = (rec["unit"]["kind"], rec["unit"]["key"])
            if u not in (unit_of[fine] - unit_of[coarse]):
                problems.append((f"refinement 的单元 {u!r} 不在细的那一侧多出来的部分里",
                                 rec))
        elif t == "alternative":
            src, rel = rec["source"], rec["relation"]
            sets = {vid: {e["to"] for e in by_id[vid]["edges"]
                          if e["from"] == src and e["relation"] == rel}
                    for vid in rec["views"]}
            vals = [v for v in sets.values() if v]
            if len(vals) < 2:
                problems.append((f"alternative {src}--{rel} 只有一边有后继", rec))
            else:
                for i in range(len(vals)):
                    for j in range(i + 1, len(vals)):
                        if vals[i] <= vals[j] or vals[j] <= vals[i]:
                            problems.append(
                                (f"alternative {src}--{rel} 的两边有包含关系"
                                 f"（该是 refinement 或 omission）", rec))
    return problems


def run_all() -> list:
    """Test 3 里**能当断言用**的两条：共识恒等式 + 每条记录过定义校验。

    ⚠️ 四类的**召回率故意不设门禁** —— 没有基线数据之前，任何「召回 ≥ 0.9 算过」
    都是拍出来的线（§T0.3）。恢复率照报，但不决定退出码。
    """
    head = measure(HEADLINE)
    c = head["result"]["consensus"]
    problems = _definition_ok(head["views_objs"], head["syn"])
    return [
        ("Test3 共识 = 全部视图的交集（恒等式核对）",
         c["planted"] == c["hit"] and c["type_confuse"] == 0 and c["miss"] == 0,
         f"植 {c['planted']} / 命中 {c['hit']} / 漏 {c['miss']} / 多报 {c['spurious']}"),
        ("Test3 每条报出来的记录都满足该类的定义",
         not problems,
         f"报出 {sum(len(v) for k, v in _subjects(head['syn']).items())} 条主语，"
         f"定义不符 {len(problems)} 条"
         + (f"：{problems[:2]}" if problems else "")),
    ]
