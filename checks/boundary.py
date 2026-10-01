"""边界检查 —— 「核心不能被上游结构带跑」的可执行形式。

---
这个模块挡的是什么
-----------------

上游（Scaffold / arena / nested）各有自己的数据模型。一旦让它们的字段渗进
`core/` / `analysis/` / `metrics/`，会发生两件**不会报错**的事：

    一、DCE 慢慢变成上游的一次重新实现 —— 而 §十九 划的那条边界（交互层 vs 视图层）
        会在没人注意的时候消失
    二、核心开始依赖某种特定来源的形状，于是「多视图结构差分」这个一般能力
        退化成「处理 arena 数据的一段脚本」

两件事都不会让任何测试变红。所以必须有一条检查专门盯着**方向**。

三条判据：

    一、`core/` `analysis/` `metrics/` **不许 import `adapters`**（方向）
    二、DCE 的结构里**不许出现上游交互层的字段名**（词汇）
    三、adapter 吐出来的关系种类必须**落在声明的词表里**（词表纪律）

第二条尤其要紧，因为它挡的是最隐蔽的一种渗漏：不是在代码里 import 了上游，
而是把 `vote` / `revision` / `origin` 这类字段**当成普通数据搬进了视图**。
而 `vote` 和 `origin` 恰好是 `§C9 #4/#5` 与 §二十 明令禁止的两样东西。
"""

from __future__ import annotations

import ast
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

# ① 方向：这些包**不许** import `adapters`（也不许 import `generators` ——
# 合成语料是检查用的，不是核心的依赖）。
CORE_PACKAGES = ("core", "analysis", "metrics")

# ② 上游交互层的字段名。它们出现在**键**上就是渗漏。
FOREIGN_KEYS = (
    "vote", "votes", "revision", "revisions", "parent_rev", "event", "events",
    "seq", "superseded_by", "created_at", "actor", "payload", "state", "status",
    "origin", "author", "score", "weight", "truth_score",
)


def _imports_of(path: Path) -> set:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            out.add(node.module.split(".")[0])
    return out


def check_core_does_not_import_adapters() -> tuple[bool, str]:
    """方向：核心不许依赖边界层。"""
    bad = []
    n = 0
    for pkg in CORE_PACKAGES:
        for p in sorted((ROOT / pkg).rglob("*.py")):
            if "__pycache__" in str(p):
                continue
            n += 1
            got = _imports_of(p)
            for forbidden in ("adapters", "generators"):
                if forbidden in got:
                    bad.append(f"{p.relative_to(ROOT).as_posix()} import 了 {forbidden}")
    if bad:
        return False, "；".join(bad)
    return True, f"扫了 {n} 个核心文件，adapters / generators 依赖 0 处"


def check_no_foreign_keys_in_structures() -> tuple[bool, str]:
    """词汇：DCE 的结构里不许出现上游交互层的字段名。

    判据是**看真实产物**，不是看源码里有没有这个词 ——
    `adapters/arena.py` 里必须提到 `vote`（那是它丢掉的东西），
    而 `core/` 的产物里出现 `vote` 才是渗漏。
    """
    from core import view as V
    from generators import synthetic as SYN
    from analysis import synthesis as S

    art = [{"id": "claim-0001", "type": "claim", "author": "u1", "state": "active"},
           {"id": "evid-0001", "type": "evid", "author": "u1", "created_at": "2026"},
           {"id": "vote-0001", "type": "vote", "author": "u2"}]
    rels = [{"kind": "supports", "from_id": "evid-0001", "to_id": "claim-0001",
             "seq": 7, "state": "active"}]
    from adapters import arena as A
    views = [x.view for x in A.to_views(art, rels)]

    base = SYN.base_graph(n_nodes=10, n_edges=12, seed=71)
    syn_views, _t = SYN.make(base, {"n_views": 3, "n_core": 6, "private": 1})
    views += syn_views
    syn = S.build(views)

    hits = []

    def walk(obj, path="$"):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in FOREIGN_KEYS:
                    hits.append(f"{path}.{k}")
                walk(v, f"{path}.{k}")
        elif isinstance(obj, (list, tuple)):
            for i, v in enumerate(obj):
                walk(v, f"{path}[{i}]")

    for v in views:
        walk(v, f"view:{v['id']}")
    walk(syn, "synthesis")
    if hits:
        return False, f"结构里出现上游字段 {sorted(set(hits))[:5]}"
    return True, f"{len(views)} 个视图 + 合成结构，上游交互层字段 0 处"


def check_adapter_vocabulary_is_declared() -> tuple[bool, str]:
    """词表纪律：adapter 吐出来的每种关系种类都要落在声明的词表里。

    并且：**不能声称 `contradiction` 却给不出互斥的种类** —— 那一条由
    `adapters.check_can_produce` 在构造时强制，这里把它真的跑一遍。
    （一个从不被执行的检查与一条永远通过的检查，在输出上长得一样。）
    """
    from core import edge as E
    from adapters import arena as A
    from adapters import scaffold as SC

    art = [{"id": "claim-0001", "type": "claim", "author": "u1"},
           {"id": "evid-0001", "type": "evid", "author": "u1"},
           {"id": "claim-0002", "type": "claim", "author": "u2"},
           {"id": "evid-0002", "type": "evid", "author": "u2"}]
    rels = [{"kind": "supports", "from_id": "evid-0001", "to_id": "claim-0001"},
            {"kind": "contradicts", "from_id": "evid-0002", "to_id": "claim-0002"},
            {"kind": "refines", "from_id": "claim-0001", "to_id": "claim-0002"},
            {"kind": "vote", "from_id": "claim-0001", "to_id": "claim-0002"}]
    avs = A.to_views(art, rels)
    svs = [SC.to_view("SC", [{"id": "con-0001", "relations": ["judge-0001"],
                              "title": "x", "evidence_status": "已确立"},
                             {"id": "judge-0001", "relations": []}])]

    kinds = set()
    for a in avs + svs:
        kinds |= {e["relation"] for e in a.view["edges"]}
    undeclared = [k for k in kinds if k not in E.KNOWN_KINDS]
    if undeclared:
        return False, f"adapter 吐出了词表外的种类 {sorted(undeclared)}"

    # `refines` 必须被丢掉（SPEC_ONLY），且要被记账
    junk = [x for a in avs for x in a.losses if "refines" in x]
    if not junk:
        return False, "kind='refines' 是 SPEC_ONLY_KINDS，本该被丢掉并记账，但没看到记录"

    # 声称 must-match 实际：Scaffold 的视图不许声称 contradiction
    sc = svs[0]
    if "contradiction" in sc.can_produce:
        return False, "Scaffold 视图声称能产生 contradiction，但它的边没有种类"
    if E.SCAFFOLD_UNTYPED not in kinds:
        return False, f"Scaffold 视图本该用占位种类 {E.SCAFFOLD_UNTYPED}，但没出现"
    return True, (f"种类 {sorted(kinds)} 全部在词表内；refines 已丢弃并记账；"
                  f"Scaffold 视图 can_produce={list(sc.can_produce)}（无 contradiction）")


def check_adapters_do_not_mutate_inputs() -> tuple[bool, str]:
    """单向性：adapter **只读**输入，不改。**

    与 `§C7.1 ④`「上层不得把判断写回底层」同源。这里测的是最直接的一种形式：
    把输入深拷贝一份，跑完 adapter 之后逐字节比对。
    """
    import json
    from adapters import arena as A
    from adapters import scaffold as SC

    art = [{"id": "claim-0001", "type": "claim", "author": "u1"},
           {"id": "vote-0001", "type": "vote", "author": "u2"}]
    rels = [{"kind": "supports", "from_id": "claim-0001", "to_id": "claim-0001"}]
    nodes = [{"id": "con-0001", "relations": [], "title": "t"}]

    before_a = json.dumps([art, rels], sort_keys=True)
    before_n = json.dumps(nodes, sort_keys=True)
    A.to_views(art, rels)
    SC.to_view("SC", nodes)
    if json.dumps([art, rels], sort_keys=True) != before_a:
        return False, "arena adapter 改了入参"
    if json.dumps(nodes, sort_keys=True) != before_n:
        return False, "scaffold adapter 改了入参"
    return True, "两个 adapter 跑完，入参逐字节不变"


def check_no_scaffold_at_frontier() -> tuple[bool, str]:
    """`SPEC_ONLY_KINDS` 不许出现在**生成器与 adapter 吐出的边**上。

    这条是这一轮的核心更正：合成语料原先用 `refines` / `related_to`
    （arena 产品代码从不产生），等于在一个上游不存在的形态上验证 DCE。
    """
    from core import edge as E
    from generators import synthetic as SYN

    base = SYN.base_graph(n_nodes=24, n_edges=40, seed=3,
                          topology="forest", n_components=3)
    bad = sorted({e[2] for e in base["edges"] if not E.is_product_kind(e[2])})
    if bad:
        return False, f"骨架产生了非产品种类 {bad}"

    views, _t = SYN.make(base, {"n_views": 3, "n_core": 8, "private": 1,
                                "contradictions": 1, "omissions": 1})
    bad2 = sorted({e["relation"] for v in views for e in v["edges"]
                   if not E.is_product_kind(e["relation"])})
    if bad2:
        return False, f"视图里有非产品种类 {bad2}"
    return True, (f"骨架与视图的关系种类全部是产品种类；"
                  f"规格独有的 {list(E.SPEC_ONLY_KINDS)} 一处未用")


def check_adapters_actually_produce() -> tuple[bool, str]:
    """**防空转**：adapter 对非空输入必须产出非空结构。

    ⚠️ 这条是踩出来的。arena adapter 曾经因为混了两个 id 空间（分组用 arena 原 id、
    边用映射后的 id），**每个视图都是 0 节点 0 边** —— 而当时那五条边界检查
    全部通过：它们验方向、验词汇、验词表，**没有一条验产出**。

    空输出通过全部检查，是最难发现的一种坏 —— 它与「这段输入本来就没有结构」
    在输出上长得一模一样。所以这里显式把两者分开。
    """
    from adapters import arena as A
    from adapters import scaffold as SC

    art = [{"id": "topic-0001", "type": "topic", "author": "u1"},
           {"id": "pos-0001", "type": "pos", "author": "u1"},
           {"id": "claim-0001", "type": "claim", "author": "u1"},
           {"id": "evid-0001", "type": "evid", "author": "u1"},
           {"id": "claim-0002", "type": "claim", "author": "u2"},
           {"id": "evid-0002", "type": "evid", "author": "u2"}]
    rels = [{"kind": "contains", "from_id": "topic-0001", "to_id": "pos-0001"},
            {"kind": "supports", "from_id": "evid-0001", "to_id": "claim-0001"},
            {"kind": "contradicts", "from_id": "evid-0002", "to_id": "claim-0002"}]
    avs = A.to_views(art, rels)
    if not avs:
        return False, "arena adapter 对 6 个实体、3 条关系的输入产出了 0 个视图"
    empty = [a.view["id"] for a in avs if not a.view["edges"]]
    if empty:
        return False, f"这些视图有输入却 0 边：{empty}（多半是 id 空间混了）"
    # u1 有 contains 与 supports 两条边，u2 有 contradicts 一条
    got = {a.view["id"]: len(a.view["edges"]) for a in avs}
    if got.get("A-u1") != 2 or got.get("A-u2") != 1:
        return False, f"每个来源的边数不对：{got}（期望 A-u1=2, A-u2=1）"

    # Scaffold：无种类的引用必须留成边，不能凭空消失
    sc = SC.to_view("SC", [{"id": "con-0001", "relations": ["judge-0001"]},
                           {"id": "judge-0001", "relations": []}])
    if len(sc.view["edges"]) != 1:
        return False, f"Scaffold adapter 丢了那条无种类的引用：{sc.view['edges']}"
    return True, (f"arena 产出 {len(avs)} 个视图，边数 {got}；"
                  f"Scaffold 的无种类引用留成了 1 条边")


def measure_arena_disagreement_gap() -> tuple:
    """**接口错位测量**：Arena 的「两方对立」形状，在 DCE 的矛盾判据下报不出来。

    ⚠️ 这是一处**真实错位**，我刻意**不**去顺手改 DCE 的核心定义 ——
    那正是「被上游结构带着跑」。这里只把它量出来、记在案，决定权留在 DCE 这边。

    Arena 里两方对立长这样：

        evid-0001 --supports----> claim-0001
        evid-0002 --contradicts-> claim-0001

    **共享的是 `to`，不同的是 `from`。** 而 DCE 的矛盾判据要求
    `(from, to)` 相同、只有 relation 互斥。于是上面这对在 DCE 里
    **一条矛盾都报不出来**，只会报成一堆 omission（两个视图的端点集不同）。

    可能的三条出路，都还没走：

        一、把 DCE 的 contradiction 从「同 (from,to)」放宽成「同 to、互斥 kind」
           —— 但那是改本层的核心判据，需要设计稿点头
        二、在 adapter 里 **reify**：把「对同一 claim 的两种对立态度」显式建成
           一个共享端点，让 DCE 的判据够得着 —— 这是 adapter 的活
        三、承认这形状在 MVP 范围外
    """
    from adapters import arena as A
    from analysis import divergence as D

    art = [{"id": "claim-0001", "type": "claim", "author": "u1"},
           {"id": "evid-0001", "type": "evid", "author": "u1"},
           {"id": "evid-0002", "type": "evid", "author": "u2"}]
    rels = [{"kind": "supports", "from_id": "evid-0001", "to_id": "claim-0001"},
            {"kind": "contradicts", "from_id": "evid-0002", "to_id": "claim-0001"}]
    views = [a.view for a in A.to_views(art, rels)]
    d = D.analyse(views)
    n = len(d["contradiction"])
    return n, (f"Arena 的两方对立（共享 to、不同 from、互斥 kind）→ "
               f"DCE 报出矛盾 **{n} 条**，同一输入报出 omission "
               f"{len(d['omission'])} 条。**这是判据错位，不是实现 bug。**")


CHECKS = (
    ("方向：核心不许 import adapters", check_core_does_not_import_adapters),
    ("词汇：结构里无上游交互层字段", check_no_foreign_keys_in_structures),
    ("词表：adapter 的种类已声明", check_adapter_vocabulary_is_declared),
    ("单向：adapter 不改入参", check_adapters_do_not_mutate_inputs),
    ("保真：只用产品真的会产生的种类", check_no_scaffold_at_frontier),
    ("防空转：adapter 真的产出结构", check_adapters_actually_produce),
)


def run_all() -> list:
    out = []
    for title, fn in CHECKS:
        try:
            ok, detail = fn()
        except Exception as e:                       # noqa: BLE001
            ok, detail = False, f"{type(e).__name__}: {e}"
        out.append((title, ok, detail))
    return out


def report() -> list:
    """度量（不进退出码）：接口错位有多大。"""
    _n, detail = measure_arena_disagreement_gap()
    return [("接口错位：Arena 对立形状 → DCE 矛盾判据", detail),
            ("  └ 尚未走的出路", "改 DCE 判据（需设计稿点头）／adapter reify／"
                                 "承认在范围外 —— 三条都还没走")]


if __name__ == "__main__":
    import sys
    bad = 0
    for t, ok, d in run_all():
        print(f"  {'过    ' if ok else '**红的**'} {t:<30} {d}")
        bad += 0 if ok else 1
    sys.exit(1 if bad else 0)
