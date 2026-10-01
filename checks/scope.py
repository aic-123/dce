"""§二十 的排除项 —— 做成**可执行检查**，不是一句声明。

设计稿 §二十 明确砍掉：

    ❌ 曲率   ❌ 神经场   ❌ latent field   ❌ 自动生成节点
    ❌ 自动 ontology alignment   ❌ 自动判断真假   ❌ 模型评分   ❌ 权威排序
    ❌ 长期记忆   ❌ 遗忘   ❌ 主体性   ❌ 实时模型构造

---
⚠️ 为什么不能拿一张关键词表去扫
------------------------------

**朴素的词扫描一定会误报，而且误报的是设计稿自己要求的东西：**

    §十四 要求合成语料带 ground truth          → "truth" 必须出现
    §十六 的基线 A 就叫 Embedding similarity    → "embedding" 必须出现
    §十五 Test 3 里"矛盾"是核心概念             → "contradiction" 必须出现

所以本检查盯的是**能力有没有被实现**，不是词有没有出现。四条判据：

    一、模块清单**恰好**是 §十七 规定的那几个 —— 多一个顶层模块就要解释它是什么
    二、**零第三方 import**（§十七：Python / 标准库 / 纯内存）
    三、产物结构里**没有**评分 / 权重 / 真值键（§C9 #1 / #4 / #7）
    四、`support` **不作为排序键**（§C5 #5：Popularity = Evidence）

第 1 条是这里最要紧的：一个「曲率模块」或「长期记忆模块」若被加进来，
**它一定表现为多出一个顶层模块**。盯模块清单比盯词准得多。
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

# §十七 规定的目录：这六个包 + 顶层 __init__。
LAYOUT = {"core", "analysis", "metrics", "checks", "generators", "tests", "adapters"}

# 每个包**恰好**该有的模块（§十七 逐个写死的那几个）。
EXPECTED = {
    "core": {"view", "node", "edge", "provenance", "__init__"},
    "analysis": {"consensus", "divergence", "focus", "synthesis", "__init__",
                 # `beta`：借自群落生态学的**周转/嵌套**分解，用来替掉四类互斥标签。
                 # 依据是 `betapart` 1.6.1 的 CRAN 参考手册（**读过正文**）。
                 # 它解开的正是本仓库量出的判据层毛病（四类边界随构造移动）。
                 "beta"},
    "metrics": {"coverage", "compression", "__init__",
                # `approximation`：借自粗糙集（Pawlak 1982）的**正域 / 依赖度 / 约简**。
                # **读过正文**（`RoughSets` 1.3-8 的 CRAN 参考手册）。
                # 它给出的 γ 是对 §十六「DCE 是否只是 graph frequency bookkeeping？」
                # 的**定量答案**：γ=1 ⟺ 类型判定完全由视图成员关系决定。
                # ⚠️ 只用**经典** RST —— 模糊扩展会把一整排参数请回来。
                "approximation"},
    # ⚠️ `corpus` 同样是**放进去时才解释的**：
    # 前面四组各自在一个（或几个）配置上判一次，而「每条结论都在一整片配置上
    # 撞一遍、并报出反例」是另一件事 —— 上一轮的量出证据是：
    # 所有结论都只在**一个标题配置**上验过，而那个配置所在的语言库
    # 可达率只有 38%、形状覆盖近乎为零。**一个点上的结论和一个扫描过的结论，
    # 在报告里长得一样。**
    "checks": {"identity", "interference", "reconstruction", "ablation",
               "__init__", "__main__", "scope", "corpus",
               # ⚠️ `boundary` 也是**放进去时才解释的**：
               # 「核心不能被上游结构带跑」是一条**方向性**的约束，而方向一旦反过来
               # 不会让任何测试变红 —— DCE 只会慢慢变成 arena 的一次重新实现。
               # 所以它需要一条专门盯方向的检查。
               "boundary",
               # ⚠️ `realdata`：前面所有检查跑的都是合成语料，而合成数据
               # **永远测不出「同名不同义」**这类错位 —— 真实语料里
               # Scaffold 的 `source.kind` 是中文的「论文/教材/…」，
               # 而 DCE 的是英文的「model/human/paper/…」，交集为空。
               # 它还需要一个**第三态**：语料不在时显式跳过（跳过不等于通过）。
               "realdata",
               # ⚠️ `positions`：判据要按设计稿定，而**上游给不出判据需要的形状**。
               # 所以材料得按判据自己造 —— 本模块验的就是「造出来的三份立场
               # 是否按判据分类」。顺序不能反：不一致时改**材料**，不改判据。
               "positions",
               # ⚠️ `radius`：§十一 的第三条聚类依据（局部图距离）需要一个半径，
               # 而 §T0.3 禁「断言没有基线数据的具体阈值」。**它禁的不是「有参数」**：
               # 半径是显式参数，且**上界由结构算出来**（`focus.calibrate`），
               # 曲线每次都报。这个模块证明机制**不是空转的** ——
               # 少了它，「半径没用」无法与「机制是死的」区分开。
               "radius",
               # `beta`：周转/嵌套分解的检查。定理用**精确有理数穷尽验证**
               # （9261 组、无容差），实现按**声明的**容差对齐 ——
               # 两件事分开测，否则分不清是定理错还是浮点错。
               "beta",
               # `approximation`：粗糙集那条的检查。重点是**验证等价式本身**
               # （γ=1 ⟺ 类型是签名的函数），而不只是验证实现。
               "approximation",
               # ⚠️ `focus`：焦点机制的**要求**（R1–R6）与三种依据的对照。
               # 它存在是因为**要求被重写过一次**：原先焦点被实现成**划分**，
               # 而那个前提从没被论证过。核到双聚类的 checkerboard 之后才发现
               # 可以不是划分 —— 于是要求写成六条，「是划分」不在其中。
               "focus"},
    # ⚠️ `adapters` 是 §十八 要求的边界层。它单列成一个顶层包，
    # **就是那条方向约束的结构形式**：核心不许 import 这一层，
    # 而 `checks/boundary.py` 把这条钉成可执行检查。
    "adapters": {"__init__", "scaffold", "arena"},
    # ⚠️ `topology` 是**放进去时才解释的**（这条检查的作用正是逼我解释一句）：
    # 语料库的「骨架长什么样」与「视图怎么构造并植入」是两件事，
    # 混在一个 700 行的文件里以后没人分得清改了哪个。
    # 拆出来的直接动因：上一轮量出语料库只会造连通的随机图，
    # 于是 §十一 的焦点机制全程空转（1416 条分歧塌成 1 个焦点）。
    "generators": {"synthetic", "topology", "__init__",
                   # `positions`：按 `CRITERIA.md` 的判据自己造的多视图材料
                   # （三份立场），词汇表取自真实语料，结构由本层设计。
                   "positions"},
    "tests": {"test_dce", "run_tests"},
}


def _py_files():
    for p in sorted(ROOT.rglob("*.py")):
        if "__pycache__" in str(p):
            continue
        yield p


def check_layout() -> tuple[bool, str]:
    """§十七 的目录与模块清单。多一个顶层模块就要解释它是什么。

    ⚠️ **排除所有以 `.` 开头的目录**（`.git` / `.github` / `.venv` …）。
    第一版只排除了 `__pycache__`，于是在 `git init` 之前一直是绿的，
    一旦提交，`.git` 就成了「多出来的顶层目录」——
    **检查在它变成仓库的那一刻才变红，而那正好是它最该可靠的时候。**
    """
    top = {p.name for p in ROOT.iterdir()
           if p.is_dir() and not p.name.startswith(".") and p.name != "__pycache__"}
    extra = top - LAYOUT
    missing = LAYOUT - top
    if extra or missing:
        return False, f"顶层目录多了 {sorted(extra)}，少了 {sorted(missing)}"
    detail = []
    for pkg, want in sorted(EXPECTED.items()):
        got = {p.stem for p in (ROOT / pkg).glob("*.py")}
        extra_m = got - want
        if extra_m:
            detail.append(f"{pkg} 多出 {sorted(extra_m)}")
    if detail:
        return False, "；".join(detail)
    return True, f"{len(LAYOUT)} 个包、{sum(len(v) for v in EXPECTED.values())} " \
                 "个模块，与 §十七 一致"


def _is_local(mod: str, from_file: Path) -> bool:
    """这个模块名是不是本仓库自己的。

    ⚠️ 三个地方都要看，少一个就误报：
        仓库根           `import core` / `from analysis import ...`
        导入者所在目录    `tests/run_tests.py` 里的 `import test_dce`
        各包目录         `checks/__init__.py` 里的 `from checks import x`

    第一版只看仓库根，于是 `tests/run_tests.py: import test_dce` 被报成第三方依赖。
    **检查的误报和漏报一样要修，不能靠加豁免。**
    """
    for base in (ROOT, from_file.parent):
        if (base / (mod + ".py")).exists() or (base / mod).is_dir():
            return True
    return False


def check_no_third_party() -> tuple[bool, str]:
    """零第三方 import。§十七：Python / 标准库 / 纯内存。"""
    stdlib = set(sys.stdlib_module_names)
    bad = []
    for p in _py_files():
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                mods = [node.module.split(".")[0]]
            for m in mods:
                if m not in stdlib and not _is_local(m, p):
                    bad.append((p.relative_to(ROOT).as_posix(), m))
    if bad:
        return False, f"非标准库 import：{bad[:5]}"
    return True, f"扫了 {len(list(_py_files()))} 个文件，第三方依赖 0 个"


def check_no_scoring_in_products() -> tuple[bool, str]:
    """产物里没有评分 / 权重 / 真值键（§C9 #1 / #4 / #7）。"""
    from analysis import synthesis as S
    from generators import synthetic as SYN
    base = SYN.base_graph(n_nodes=10, n_edges=12, seed=61)
    views, _t = SYN.make(base, {"n_views": 7, "n_core": 8, "private": 1,
                                "contradictions": 1, "omissions": 1,
                                "refinements": 1, "alternatives": 1})
    hits = S.forbidden_keys_in(S.build(views))
    if hits:
        return False, f"产物里出现 {hits[:5]}"
    return True, f"合成结构里禁用键 0 处（词表 {len(S.FORBIDDEN_KEYS)} 个）"


def check_support_is_never_a_sort_key() -> tuple[bool, str]:
    """`support` 不作为排序键。§C9 #5：Popularity = Evidence。

    判据：构造一个「出现次数」与「key 字典序」相反的输入，
    断言输出的顺序跟的是 key，不是出现次数。
    """
    from analysis import consensus as C
    from core import view as V
    # con-0001 出现在 2 个视图（少），con-0002 出现在 1 个视图 —— 
    # 若按 support 排，con-0001 会排在前面；按 key 排也是 con-0001 在前。
    # 所以要让两者**相反**：让 key 大的那个 support 高。
    a = V.make_view(view_id="A", source_ref="x://A", source_kind="experiment",
                    nodes=["con-0009", "con-0001"], edges=[])
    b = V.make_view(view_id="B", source_ref="x://B", source_kind="experiment",
                    nodes=["con-0009"], edges=[])
    rows = C.support_table([a, b])
    keys = [r["unit"]["key"] for r in rows]
    if keys != sorted(keys):
        return False, f"support 表没按 key 排：{keys}"
    sup = {r["unit"]["key"]: r["support"] for r in rows}
    if sup["con-0009"] <= sup["con-0001"]:
        return False, "测试输入没造出「key 序与 support 序相反」的情形，检查是空转的"
    return True, f"key 序 {keys} 与 support 序相反（{sup['con-0009']} > {sup['con-0001']}），" \
                 "输出跟的是 key"


CHECKS = (
    ("§二十/§十七 目录与模块清单", check_layout),
    ("§十七 零第三方依赖", check_no_third_party),
    ("§二十 产物无评分/权重/真值", check_no_scoring_in_products),
    ("§C9 #5 support 不作排序键", check_support_is_never_a_sort_key),
)


def run_all() -> list:
    out = []
    for title, fn in CHECKS:
        try:
            ok, detail = fn()
        except Exception as e:                        # noqa: BLE001
            ok, detail = False, f"{type(e).__name__}: {e}"
        out.append((title, ok, detail))
    return out


def report() -> list:
    return []


if __name__ == "__main__":
    bad = 0
    for t, ok, d in run_all():
        print(f"  {'过    ' if ok else '**红的**'} {t:<28} {d}")
        if not ok:
            bad += 1
    sys.exit(1 if bad else 0)
