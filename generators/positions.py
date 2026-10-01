"""多视图材料（自己造）—— **按 `CRITERIA.md` 的判据造，不迁就上游的写法。**

---
为什么是自己造的，以及为什么这不算作弊
------------------------------------

上游给不出 DCE 需要的形状。Arena 表达「两方对立」用的是
`evid-0001 supports claim-0001` 对 `evid-0002 contradicts claim-0001` ——
**共享 `to`、不同 `from`**；而按设计稿 §五·二 与 §九，矛盾的判据是
**同一有序端点对上是两种互斥的关系**。这不是 DCE 的实现缺陷，是两种表达方式不同。

`CRITERIA.md` §五 裁决了三条出路，选了第三条：**承认对不上，然后把材料按判据造。**

那不是把测试喂成训练集 —— 区别在这里：

    合成随机图（前一版 generators/synthetic.py）  验的是**机制在任意形状上稳不稳**
    本模块（立场语料）                            验的是**判据在多份真实立场上够不够用**

两者都不是「用真语料测准确率」，因为**那不成立**：DCE 没有真值可对，
它输出的是派生结构。所以材料的作用是**把判据逼到边界上**，不是刷分。

具体地，本模块造三份立场，**每一类差异都由立场之间的真实差别自然产生**，
不是把四类分别种在四个专用视图上（那正是上一轮被证伪的做法）：

    P1  损失聚合与裁剪上界这条路线          是 P3 的**真子集** → 精炼
    P2  归一化偏差这条路线                  → 与 P1 在**同一有序端点对上说了相反的话**
    P3  P1 加上例外与案例                  → 比 P1 更细

---
词汇表来自真实语料，结构是本层设计的
------------------------------------

节点 id 与标题取自 `rl-scaffold` 的 36 个真节点（GRPO/RL 的规格化知识），
这样材料**读起来是真内容**，而**结构**（谁断言了什么）是本层按判据设计的。

⚠️ 必须说清：**这些立场是我造的，不是从那些论文里抽取的。**
`source_ref` 一律是 `authored://`，不是 `paper://` ——
把它们当成「论文说了什么」会是伪造引用。
"""

from __future__ import annotations

# 真实语料的节点 id → 标题（取自 rl-scaffold 的 36 个真节点，仅作词汇表）。
VOCAB = {
    "issue-0001": "为什么 GRPO 训练中回答会越来越长",
    "stance-0001": "DAPO：长度与熵的问题出在损失聚合和裁剪上界",
    "stance-0002": "Dr. GRPO：归一化本身就带偏差",
    "con-0001": "组内相对归一化",
    "con-0002": "不引入价值网络",
    "con-0004": "策略熵",
    "con-0005": "损失聚合粒度",
    "judge-0003": "回答长度增长",
    "case-0001": "DAPO 在 AIME24 上的结果",
    "case-0002": "Dr.GRPO 在 7B 上的 AIME 结果",
    "case-0003": "R1-Zero 纯 RL",
    "arg-0001": "增量消融：四项技术各加一项，分数单调上升",
    "arg-0002": "token 效率",
    "exc-0001": "去掉 std 的代价",
    "exc-0002": "非 Hopper 精度",
}

# ── 三份立场。每条边是 `(from, to, relation)`（§九：有序三元组）────────
#
# 共享骨架（三份都有 → 共识）：
#   ("con-0002", "con-0001", "assumes")     「不用价值网络」假设了「组内相对归一化」
#   ("judge-0003", "con-0001", "explains")  长度增长由归一化方式解释
#
# 差异（四类各自自然产生）：
#   case-0001 这个案例，P1/P3 读成支持、P2 读成反对  → **矛盾**（同一有序对、互斥种类）
#   judge-0003 的解释，P1 给 con-0004、P2 给 con-0005 → **替代解释**（后继集合互不包含）
#   P3 = P1 ∪ {例外与案例}                          → **精炼**（P1 是 P3 的真子集）
#   P2 缺 con-0004 等、且没有表态反对                → **缺失**
POSITIONS = {
    "P1": {
        "label": "损失聚合与裁剪上界这条路线",
        "edges": [
            ("con-0002", "con-0001", "assumes"),
            ("judge-0003", "con-0001", "explains"),
            ("case-0001", "con-0001", "supports"),      # ← 与 P2 同对互斥
            ("judge-0003", "con-0004", "explains"),     # ← 与 P2 争夺同一 judge
            ("con-0001", "con-0005", "explains"),       # ← P1 独有（P2 缺）
        ],
    },
    "P2": {
        "label": "归一化偏差这条路线",
        "edges": [
            ("con-0002", "con-0001", "assumes"),
            ("judge-0003", "con-0001", "explains"),
            ("case-0001", "con-0001", "contradicts"),   # ← 同一案例，读成反对
            ("judge-0003", "con-0005", "explains"),
            ("arg-0002", "con-0001", "supports"),       # ← P2 独有
        ],
    },
    "P3": {
        "label": "P1 加上例外与案例",
        "edges": [
            ("con-0002", "con-0001", "assumes"),
            ("judge-0003", "con-0001", "explains"),
            ("case-0001", "con-0001", "supports"),
            ("judge-0003", "con-0004", "explains"),
            ("con-0001", "con-0005", "explains"),
            ("exc-0001", "con-0005", "explains"),       # ← P1 没有（→ 精炼）
            ("case-0003", "con-0005", "supports"),      # ← P1 没有（→ 精炼）
        ],
    },
}

# 各立场自己的来源标记。**是造出来的，不是从论文抽取的。**
SOURCES = {
    "P1": "authored://dce/positions/P1（损失聚合路线）",
    "P2": "authored://dce/positions/P2（归一化偏差路线）",
    "P3": "authored://dce/positions/P3（P1 + 例外与案例）",
}


def build() -> tuple:
    """造出三份视图，并返回 `(views, intent)`。

    `intent` 是**我打算让每一类出现在哪里** —— 供 `checks/positions.py` 核对
    「按判据分类的结果」是否与设计一致。若不一致，改的是**材料**，不是判据。
    """
    from core import view as V

    views = []
    for pid in sorted(POSITIONS):
        spec = POSITIONS[pid]
        edges = sorted(set(spec["edges"]))
        nodes = sorted({x for e in edges for x in (e[0], e[1])})
        unknown = [n for n in nodes if n not in VOCAB]
        if unknown:
            raise ValueError(f"{pid} 用了词汇表外的节点 {unknown}")
        views.append(V.make_view(
            view_id=pid, source_ref=SOURCES[pid], source_kind="human",
            nodes=nodes, edges=edges,
            metadata={"labels": {n: VOCAB[n] for n in nodes},
                      "authored": True,
                      "label": spec["label"]},
        ))

    intent = {
        # 三份都有 → 共识（由定义算出，不是我以为共享的那些）
        "consensus": None,
        # 同一有序对 (case-0001, con-0001)：supports（P1,P3）⊥ contradicts（P2）
        "contradiction": [("case-0001", "con-0001", "supports", "contradicts")],
        # 同一 judge-0003 上的后继集合互不包含：P1{con-0001,con-0004} vs P2{con-0001,con-0005}
        "alternative": [("judge-0003", "explains")],
        # P1 是 P3 的真子集
        "refinement": [("P1", "P3")],
        # 至少这些缺失必须在（不做穷举断言 —— 穷举会把判据的推论当成预埋）
        "omission_expected": [
            ("P2", "node", "con-0004"),
            ("P2", "edge", ("con-0001", "con-0005", "explains")),
            ("P1", "node", "arg-0002"),
            ("P3", "edge", ("judge-0003", "con-0005", "explains")),
        ],
        # 这些**不该**被报成缺失：它们有互斥对应，归矛盾
        "omission_must_exclude": [
            ("P1", "edge", ("case-0001", "con-0001", "contradicts")),
            ("P2", "edge", ("case-0001", "con-0001", "supports")),
            ("P3", "edge", ("case-0001", "con-0001", "contradicts")),
        ],
    }
    return views, intent


def describe() -> str:
    lines = ["三份立场（词汇表取自 rl-scaffold 的 36 个真节点，结构由本层设计）："]
    for pid in sorted(POSITIONS):
        spec = POSITIONS[pid]
        edges = sorted(set(spec["edges"]))
        lines.append(f"  {pid} · {spec['label']}  "
                     f"{len({x for e in edges for x in (e[0], e[1])})} 节点 / "
                     f"{len(edges)} 边")
    return "\n".join(lines)
