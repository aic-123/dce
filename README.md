# DCE · Divergence-Consensus Engine

**Scaffold 结构空间上的多视图差分层。**

给定多个已经结构化、位于同一知识空间中的认知视图，识别它们的共同结构、
明确冲突、表达缺失与结构细化，并生成一个**可追溯的派生结构**。

DCE **不负责发现知识、不负责判断真伪、不负责决定哪一个模型正确。**
它负责回答：**这些视图在哪里相同？在哪里不同？差异究竟属于什么类型？**

> **Consensus ≠ Truth** · **Divergence ≠ Error**
> DCE 的输出全部属于 `derived structure`，不是 `ground truth`。

---

## 它在链上的位置

```text
Scaffold          知识空间长什么样
   ↓
Arena             不同主体在这个空间里说了什么、哪里发生分歧
   ↓
Structured Views
   ↓
DCE               多个结构化视图之间，在结构层面究竟有什么共同与不同   ← 本仓库
   ↓
Derived Structure
   ↓
（未来的认知层：情境激活 / 几何表示 / 动态构造 —— 不在本仓库）
```

### 它不是什么

知识库 · 向量数据库 · 搜索引擎 · RAG · 模型评测器 · 投票系统 · Truth Engine ·
自动裁判 · 自动合并知识 · 自动修改底层事实 · 新的 ontology。

**也不是**曲率、神经场、长期记忆或动态构造 —— 那些在设计稿里是**更后面的层**，
本仓库一个都不做（这条有可执行检查：`python -m checks.scope`）。

---

## 快速上手

零依赖、纯标准库、纯内存，只要 Python（开发时用 3.14，代码兼容 3.9+）。

```bash
python -m checks               # 全部检查与四组测试（23 条断言）
python -m checks identity      # 只跑某一组
python tests/run_tests.py      # 同一个测试集，另一个入口（本机没有 pytest）
```

```python
from core import view as V
from analysis import synthesis as S

a = V.make_view(view_id="A", source_ref="paper://x", source_kind="paper",
                nodes=["con-0001", "judge-0001"],
                edges=[("con-0001", "judge-0001", "supports")])
b = V.make_view(view_id="B", source_ref="model://y", source_kind="model",
                nodes=["con-0001", "judge-0001"],
                edges=[("con-0001", "judge-0001", "contradicts")])

syn = S.build([a, b])
S.verify_synthesis(syn, [a, b])       # 逐条与源视图对账
```

---

## 结论

### §十五 四组测试

| 测试 | 判据 | 结果 |
|---|---|---|
| **Test 1 Identity** | A=B=C → 100% 共识、0 分歧 | **过**：共识 = 全部单元，四类分歧全为 0 |
| **Test 2 Orthogonal** | A∩B=∅ → 0 共识、大量缺失，**不能全叫矛盾** | **过**：共识 0、缺失 2、**矛盾 0** |
| **Test 3 Controlled Divergence** | 植入 10 矛盾 / 20 缺失 / 10 精炼 / 5 竞争解释，**分别**恢复 | **过**：五类召回**全部 1.000**，类型串 0 |
| **Test 4 Interference** | `hash(A_before) == hash(A_after)` | **过**，另加三条更严的（见下） |

Test 4 额外验的三条（只比哈希不够）：

1. 每个视图**逐字段深层相等**（哈希相同但字段被重排过，不算通过）
2. 合成结果里记的视图指纹 = 当场重算的指纹
3. **后加入一个视图**，先前那些视图的指纹不变（增量写入不污染历史）

Test 3 的额外一条：**1400 条报出来的主语，逐条过定义校验，定义不符 0 条。**
这一条比「多报数」重要 —— 一条私有边**按定义就是 omission**，
拿它当 precision 的分子会把「定义如此」和「算法错了」抹平成同一个数字。

### §十六 消融（三个基线）

| | 划分是否与 DCE 相同 | 类别分辨率 | 5 类准确率 | 粗任务准确率 |
|---|---|---|---|---|
| **DCE** | — | **5 类** | **1.000** | 1.000 |
| **Baseline C** 并集+频次 | **完全相同** | 2 类 | 0.481（它只会说「共识」） | **1.000** |
| Baseline A 相似度 | — | — | 分歧/共识 **AUC 0.867** | — |
| Baseline B 相似度+聚类 | — | — | AUC 0.833（扫阈值取最好，cut=0.8） | — |

**这张表要说的是三句话，缺一句都会读错：**

1. **DCE 的划分与 union+frequency 完全相同。** 两者在定义上就是同一个
   （出现次数 == 视图数）。**DCE 在这一层没有增量。**
2. **增量在类型上**：5 类 vs 2 类；5 类准确率 1.000 vs 基线的**最好可能** 0.481。
3. **但粗任务上基线是 1.000 —— 和 DCE 一样准。**
   所以「DCE 比 union 更准」是错的；正确的说法是
   **「DCE 能把基线必须合并的东西分开」**，那是**表达力**增量，不是准确率增量。

⚠️ 基线 A/B 用的是**字符二元组 Dice**（rl-scaffold `tools/find_path.py` 的
`MATCH_SPEC` 就是这一条），**是「相似度的替代品」，不是 embedding** ——
§十七 要求纯标准库，而 embedding 需要一个模型。
基线 B 的「聚类」必须有一条切分阈值，而 `§T0.3` 禁止拍阈值，
所以本仓库**把它的阈值当旋钮扫描、报它最好的一档**：给基线它最强的一击。

### §十三 两个指标：Coverage 退化，Compression 才在动

在 16 个网格配置上量过：**Coverage 恒等于 1.0000**。

这不是实现问题，是**设计的推论**：分歧记录逐条罗列每一个差异，
而一个单元只有两种下场——要么在所有视图里都有（→ 共识），
要么至少缺在一个视图里（→ 某条缺失或被精炼认领）。**没有第三种。**

所以设计稿 §十三 说的「高 Coverage + 高 Compression 的区域」
**在本设计里退化成一条 Coverage = 1 的线**，真正在变的是 Compression，
而它只取决于**概括层级**：

| 口径 | 16 个配置上的范围 |
|---|---|
| `flat`（每条分歧记一条） | 1.07 – 2.03，**随视图数上升趋近 1** |
| `focused`（每个焦点算一条） | 2.00 – 5.44 |
| `synopsis`（焦点 + 类型直方图） | 1.91 – 4.57 |

`flat` 退化的原因很具体：缺失是逐 `(视图, 单元)` 罗列的，
于是合成与输入**同阶增长**。这条度量的是「有没有概括」，不是「DCE 好不好」。

---

## 目录

```
core/            view（结构化视图 + 规范化哈希）· node · edge（边身份 + 关系词表）· provenance
analysis/        consensus（合取，不是比例）· divergence（四类，互斥）· focus · synthesis
metrics/         coverage · compression
checks/          identity · interference · reconstruction（Test 3）· ablation（§十六）· scope（§二十）
generators/      synthetic（带 ground truth 的合成语料）
tests/           test_dce.py（32 条）· run_tests.py（不依赖 pytest 的入口）
```

**§十七 规定的目录，一个包不多一个不少** —— 这条有可执行检查
（`checks/scope.py` 盯模块清单）。加一个「曲率模块」或「记忆模块」进来，
它一定表现为多出一个顶层模块，检查会当场报出来。

---

## 三条边界（写死，不是风格偏好）

### 一、MVP 不解决 semantic alignment

输入视图**已经映射到 Scaffold 的统一节点空间**。DCE 不判断
「苹果」和「苹果公司」是不是同一个概念 —— 那是 alignment layer 的事。
节点身份 = id 的字面值，**不做任何同名归并**。

### 二、`support` 是描述性事实，不是排序键

设计稿 §八 给的 `support = 出现该节点的视图数 / 总数`（例 `0.8`），
而 arena `§C9` 不变量 #5 是 `Popularity = Evidence`，`§C7.1 ①` 明确把
「投票数 / 热度 / 参与量 / 曝光量」列为**禁止**信号，并给出推荐定义：

> 上层信号**不是「多少人说」，而是「是否在所有观点群里都成立」**……
> 它在结构上不可能违反 #5，**不需要靠人工检查去守**。

所以本仓库：

- **共识 = 合取**（`support == (n, n)`），**没有阈值**，没有「相关视图」这层过滤
- `support` 返回**元组不是比例**（比例会被顺手拿去过阈值或排序）
- 清单**按 key 排，绝不按 support 排**（这条有可执行检查）

### 三、边身份是三元组

`edge_identity = (from, to, relation)`。`A supports B` 与 `B supports A`
**不是同一个结构**（设计稿 §九）。

⚠️ **一个真实的接口缺口**：Scaffold 的 `relations` 是 `list[str]`、**不带种类**；
带种类的边**只有 Arena 有**（`relation.kind` = `§C3.2` 六种 ∪ `§C4` 四种）。
所以词表必须由 adapter **声明**，不能指望 Scaffold 给 —— 本仓库的词表是从
arena 抄的，互斥集 `supports ⊥ contradicts ⊥ qualifies` 也是（依据 `§C4`
把这三者放在同一对端点上的同一个单元格里），并用自检钉住。

---

## 它做不到什么（如实标记）

| 项 | 状态 |
|---|---|
| 真实 LLM 视图 | **没接**。MVP 只用合成 ground truth（§十四 的要求）。§十八 的三个 adapter 里，只有 Scaffold 的节点模型是读过的；**Arena 的 Position/Claim 映射与 Nested 的 pointer 映射尚未落地** |
| semantic alignment | **不做**，见上 |
| embedding 相似度 | **没做**。用的是字符二元组 Dice 替代品，标得很清楚 |
| 稀疏/长尾规模 | **没测**。测试床是 16 个视图 / 187 个单元。`flat` 口径下缺失记录已达 1314 条，**规模上去会先在这里出问题** |
| `support` 之外的共识机制 | `§C7.1` 的「跨群共识」在 MVP 规模下**全程休眠**（没有观点群）。本仓库的合取是它在无群情形下的退化形式 |

---

## 许可证

Apache License 2.0。

<!-- Copyright 2026 AIC-123 · SPDX-License-Identifier: Apache-2.0 -->
