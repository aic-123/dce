"""Adapter 层 —— 单向翻译，**核心永远不 import 这一层**。

---
这一层的存在理由，以及它的边界
----------------------------

上游（Scaffold / arena / nested）各自有自己的数据模型。DCE 需要的是
`Structured View`。两者之间的翻译必须发生在**一个明确的地方**，否则：

    上游的字段会慢慢渗进 `core/`，DCE 就变成上游的一次重新实现，
    而不是「结构空间之上的差分层」

所以这一层的规矩是**方向性的**：

    上游形状 → `Structured View`     允许，且只在这一层发生
    `Structured View` → 上游形状     禁止（DCE 是派生层，`§C7.1 ④` 单向性）

`checks/boundary.py` 把这条钉成可执行检查：`core/` / `analysis/` / `metrics/`
**不许 import `adapters`**。方向一旦反过来，那条检查就会红。

---
每个 adapter 必须声明「损失」
--------------------------

一个 adapter 最容易犯的错，是**假装读到的东西比真实的多**。
本仓库自己在 §十八 上就犯过：设计稿声明 Scaffold 提供
「Node / Edge / Situation / Cue / Source / Evidence Status」六项，
而实际情况是 —— **Scaffold 没有 Edge 实体，没有 Situation，一篇节点只有一个 source 槽位**
（`SPEC.md:38` 十一个字段不得增删；`relations` 是 `list[str]`，无种类无方向）。

所以每个 adapter 都返回一个 `Adaptation`，里面**必须**带：

    view                 翻译出来的 `Structured View`
    losses               逐条列出丢掉了什么、为什么丢
    declares             这个 adapter 自己**声明**的东西（上游没有、本层加的）
    can_produce          这份视图**能够**参与产生哪几类差异（见下）

最后一项不是装饰。**一份来自 Scaffold 的视图不可能产生 `contradiction`** ——
因为 Scaffold 的关系没有种类，而矛盾的定义要求「同一对端点上是两种被声明为互斥的关系」。
把这件事写在 adapter 的声明里，比让读者从结果里猜要好。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Adaptation:
    """一次翻译的结果，连同它的**声明**。

    ⚠️ 三个字段都是必填的语义，不是注释：`losses` 为空必须是因为**真的没丢东西**，
    而不是因为没去查。
    """

    view: dict
    losses: list = field(default_factory=list)
    declares: list = field(default_factory=list)
    can_produce: tuple = ()

    def describe(self) -> str:
        lines = [f"视图 {self.view['id']}（{len(self.view['nodes'])} 节点 / "
                 f"{len(self.view['edges'])} 边）",
                 f"  能够产生的差异类型：{list(self.can_produce) or '无'}"]
        for x in self.declares:
            lines.append(f"  本层声明：{x}")
        for x in self.losses:
            lines.append(f"  损失：{x}")
        if not self.losses:
            lines.append("  损失：无")
        return "\n".join(lines)


# 四类差异 + 共识，作为 `can_produce` 的取值域。
DIFFERENCE_TYPES = ("consensus", "contradiction", "alternative", "omission", "refinement")


def can_contradict(kinds) -> bool:
    """这组种类能不能**参与**矛盾。

    ⚠️ 判据是「**词表里**有没有哪一种与它互斥」，不是「这组种类内部有没有互斥的一对」。
    第一版写成了后者，于是把「一个视图只说了 supports」判成不能产生矛盾 ——
    但**矛盾是跨视图的**：这个视图说 `supports`、另一个视图说 `contradicts`，
    单看前一个视图当然看不到互斥对。

    反过来，Scaffold 的占位种类 `dce_untyped` 在 `EXCLUSIVE_PAIRS` 里**没有任何对应**，
    所以它真的不能参与矛盾 —— 这才是那条声明要表达的意思。
    """
    from core import edge as E
    return any(any(E.exclusive(k, other) for other in E.KNOWN_KINDS if other != k)
               for k in kinds)


def derived_can_produce(kinds) -> tuple:
    """从**实际吐出来的种类**推出 `can_produce`，而不是写死一张表。

    写死的那一版声称 arena 视图总能产生矛盾 —— 而实际上，如果这份输入里
    一条 `contradicts` 都没有，那个声称就是假的。**声称必须跟着数据走。**
    """
    can = ["consensus", "omission", "refinement"]
    if can_contradict(kinds):
        can.append("contradiction")
    if kinds:
        can.append("alternative")
    return tuple(c for c in DIFFERENCE_TYPES if c in can)


def check_can_produce(adaptation: Adaptation) -> None:
    """`can_produce` 必须与实际吐出的种类**一致**。

    这一条拦的是一类很隐蔽的错：adapter 声称某份视图能产生 `contradiction`，
    但那份视图的边全是无种类的。错会在很远的地方以「DCE 漏报」的形式出现。
    """
    from core import edge as E
    bad = [t for t in adaptation.can_produce if t not in DIFFERENCE_TYPES]
    if bad:
        raise ValueError(f"can_produce 里有未知类型 {bad}，只认 {list(DIFFERENCE_TYPES)}")
    kinds = {e["relation"] for e in adaptation.view["edges"]}
    want = derived_can_produce(kinds)
    if tuple(adaptation.can_produce) != want:
        raise ValueError(
            f"视图 {adaptation.view['id']} 的 can_produce={list(adaptation.can_produce)}，"
            f"但按它实际吐出的种类 {sorted(kinds)} 应为 {list(want)}。\n"
            "声称必须跟着数据走 —— 一份没有互斥种类的视图说不了矛盾，"
            "一份一条边都没有的视图也说不了竞争解释。"
        )
    if kinds and not any(E.is_product_kind(k) or k in E.DCE_DECLARED_KINDS
                         for k in kinds):
        raise ValueError(f"视图 {adaptation.view['id']} 的种类不在词表内：{sorted(kinds)}")
