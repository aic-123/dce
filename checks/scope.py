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
LAYOUT = {"core", "analysis", "metrics", "checks", "generators", "tests"}

# 每个包**恰好**该有的模块（§十七 逐个写死的那几个）。
EXPECTED = {
    "core": {"view", "node", "edge", "provenance", "__init__"},
    "analysis": {"consensus", "divergence", "focus", "synthesis", "__init__"},
    "metrics": {"coverage", "compression", "__init__"},
    "checks": {"identity", "interference", "reconstruction", "ablation",
               "__init__", "__main__", "scope"},
    "generators": {"synthetic", "__init__"},
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
    return True, f"6 个包、{sum(len(v) for v in EXPECTED.values())} 个模块，与 §十七 一致"


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
