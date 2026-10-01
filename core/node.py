"""节点身份 —— MVP 阶段**只是 id**，因为 §七 把对齐划到了范围外。

---
§七：MVP 不解决 semantic alignment
---------------------------------

设计稿 §七 假定：

    输入 View 已经映射到 Scaffold 的统一节点空间。
    DCE 不负责判断「苹果」和「苹果公司」是不是同一个概念。

所以本模块**不做任何同名归并、不做别名合并、不做相似度匹配**。
节点身份 = Scaffold 节点 id 的字面值。

⚠️ 这条边界要写死，否则「共识」会被悄悄放大：如果把两个名字相近的 id 当成同一个，
那 DCE 报出来的 consensus 里就掺进了一个**它自己做的判断** ——
而 §五·三 的 omission 与 §五·二 的 contradiction 都建立在「同一个节点」这个前提上。

---
id 形状照抄 Scaffold
-------------------

`schema/node.schema.yaml:23` 规定 `pattern: "^[a-z]{2,6}-\\d{4}$"`，
前缀与 type 的映射在 `types:` 那一节。本模块照抄这个形状做校验，
但**校验是可关的**（`strict=False`）—— 因为合成测试里可能用临时 id。
关掉时必须在自己的声明里写出来，不许默认关。

⚠️ 关掉它意味着「节点空间」这个前提不再被检查，而 §七 的整个边界就架在这个前提上。
"""

from __future__ import annotations

import re

# 照抄 Scaffold `schema/node.schema.yaml:23`。
ID_PATTERN = re.compile(r"^[a-z]{2,6}-\d{4}$")

# 照抄 Scaffold `schema/node.schema.yaml:99-108` 的前缀映射。
PREFIXES = {
    "con": "概念", "judge": "判断点", "cond": "条件", "exc": "例外",
    "issue": "议题", "stance": "立场", "arg": "论据", "claim": "断言",
    "case": "案例",
}


class NodeError(Exception):
    """节点 id 不对。"""


def prefix_of(node_id: str) -> str:
    """取前缀（`con-0001` → `con`）。形状不对时报错，不猜。"""
    if not isinstance(node_id, str) or "-" not in node_id:
        raise NodeError(f"节点 id 形状不对：{node_id!r}（应形如 con-0001）")
    return node_id.split("-", 1)[0]


def check_id(node_id: str, *, strict: bool = True) -> None:
    """校验 id。`strict=False` 时只要求非空字符串（合成测试用）。"""
    if not isinstance(node_id, str) or not node_id.strip():
        raise NodeError(f"节点 id 必须是非空字符串，收到 {node_id!r}")
    if not strict:
        return
    if not ID_PATTERN.match(node_id):
        raise NodeError(
            f"节点 id {node_id!r} 不符合 Scaffold 形状 ^[a-z]{{2,6}}-\\d{{4}}$"
            "（`schema/node.schema.yaml:23`）。\n"
            "§七 假定输入已经映射到 Scaffold 统一节点空间 —— 形状不对就说明这个前提没满足。"
            "合成测试要用临时 id 就显式传 strict=False，并把它写进声明。"
        )
    p = prefix_of(node_id)
    if p not in PREFIXES:
        raise NodeError(
            f"节点 id 前缀 {p!r} 不在 Scaffold 的类型映射里：{sorted(PREFIXES)}"
        )


def node_type(node_id: str) -> str | None:
    """从前缀推 type。未知前缀返回 `None`（不抛）—— 这个用途只是标注。"""
    try:
        return PREFIXES.get(prefix_of(node_id))
    except NodeError:
        return None
