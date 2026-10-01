# 可借鉴的成熟思想（不是工程史，跨领域）

这份是**调研**。
⚠️ **状态：第 1、2 条已实现并跑通（见 §实现进度），其余仍未动手。**
每条按同一个格式写：**它是什么 / 映射到 DCE 的哪一处 / 会改什么 / 代价是什么**。
最后一条最重要 —— 一个思想若不能说出代价，就不算被理解。

---

## 实现进度

| 条目 | 状态 | 落在哪 |
|---|---|---|
| 一 · 生态学 β 分解 | ✅ **已实现** | `analysis/beta.py` · `checks/beta.py`（10 条断言） |
| 二 · 空间统计扫描+蒙特卡洛 | ⬜ 未做 | 半径部分已做（`analysis/focus.py`），**零模型与显著性未做** |
| 三 · 持久同调 / 合并树 | ⬜ 未做 | ✅ 公式已核到（HDBSCAN `stability`、FOSC）；纯拓扑定义仍未核到 |
| 四 · 粗糙集 | ✅ **已实现** | `metrics/approximation.py` · `checks/approximation.py`（9 条断言） |
| 五 · FCA（`Sep`） | ⬜ 未做 | `Sep` 需要焦点层次，而那依赖半径的嵌套家族 |
| 六 · 胞腔层上同调 | ⬜ 未做 | ✅ 定义已核到（`δ^k`、`H⁰ ≅ Γ(X;F)`）；**实现太早** |
| 七 · 地图方程 | ⬜ 未做 | ✅ 公式已核到；⚠️「不需要分辨率参数」**已撤** |
| 八 · 自适应尺度 | ⬜ 未做 | ⚠️ 公式三源二手确认；🆕 另核到 **`find.radius`**（可能更省事） |

**两处实现各自带回了一条新结论**（详见 `DECLARATION.md`）：

- β 分解：四类互斥标签 → **两个分量 + 方向**。立场材料上 P1×P2 是纯周转、
  P1×P3 是纯嵌套 —— 那个「边界随构造移动」的歧义**消失了**。
- 粗糙集：**γ 成了 §十六 那个问题的定量答案**。`γ = 1 ⟺ 类型判定完全由
  「出现在哪几个视图」决定 ⟺ 类型没有携带成员关系之外的信息`。

---

## 先把要解决的问题写精确

前面几轮量出来的开口有三个，顺序按重要性：

    P1  焦点怎么聚：共享节点并查集是传递闭包，在共享节点空间下恒等于 1；
        半径救不了（r*=0）。§十一 与 §七 的前提互相拆台。
    P2  两个指标退化：Coverage 恒等于 1（设计的推论）；Compression 只在焦点
        不退化时有意义 —— 而焦点在预期用法下就退化。
    P3  共识太脆：合取意味着「少一份视图提到就没了」。真立场材料上它必然趋近 0。
    P4  四类的边界随构造移动：同一个单元**可以**既是「相对 A 的精炼」
        又是「相对 C 的缺失」—— 我量出过 strict 召回 15/115、accounted 100%。

**P4 是最要紧的**，因为它是判据层面的毛病，不是指标的毛病。

---

## 核对结果：哪些读了正文，哪些还只是检索片段

⚠️ **这一节是这份文档最该先看的部分。** 第一版是从检索摘要推的，按本仓库的规矩不能那样用。
现在把能拿到正文的核对了，**并且更正了两处我原先写错的地方**。

| 条目 | 状态 | 依据 |
|---|---|---|
| 一 · β 多样性周转/嵌套 | ✅ **读了正文** | `betapart` 1.6.1 参考手册（维护者 = Baselga 本人） |
| 二 · 扫描统计量 + 蒙特卡洛 | ✅ **读了正文** | `scanstatistics` 1.1.2 参考手册（含 p 值公式） |
| 四 · 粗糙集 | ✅ **读了正文**，且**更正了一处公式错误** | `RoughSets` 1.3-8 参考手册 |
| 五 · 形式概念分析 | ✅ **读了正文** | `fcaR` 的 lattice metrics vignette（含精确公式） |
| 三 · 持久同调 / 合并树 | ✅ **部分读到正文**：HDBSCAN 稳定性公式、FOSC、`clusterTree` 字段 | `hdbscan` 官方文档、CRAN `dbscan` / `TDA` 参考手册 |
| 六 · 胞腔层上同调 | ✅ **读到正文**（三篇 arXiv HTML，含 `δ^k` 与 `H⁰ ≅ Γ` 的确切表述） | arXiv 1808.01513 / 2511.00677 / 2503.02556 |
| 七 · 地图方程 | ✅ **公式读到正文**；❌ **「不需要分辨率参数」没有正文支持，且有反证线索** | arXiv 2409.10263 有精确式；2311.04036 的目录有 `Resolution limit.` 小节 |
| 八 · 自适应尺度 | ⚠️ **三源二手确认**（公式一致），**原论文措辞未核对**（NIPS 全文是 PDF） | CRAN `T4cluster` / `FuzzySpec` + MetricGate 文档 |

**第二轮检索（补上原先只有片段的四条）另核到：**

- **HDBSCAN 稳定性的精确式子**（`λ = 1/distance`，`stability = Σ_p (λ_p − λ_birth)`），
  以及抽取规则（自下而上，子簇稳定性之和大于本簇则取和，否则宣布本簇已选并取消其后代）
- **FOSC 的跨尺度形式化**：`max J = Σ δ_i S(C_i)`、`S(C_i) = Σ (1/h_min − 1/h_max)`，
  并且原文的语义正是「**在所有可能的阈值上扫一遍，跨多个阈值存活的簇才是更强的候选**」
  —— 那是我在第 3 条里想说的东西的**确切出处**
- **胞腔层的确切定义**：stalk、限制映射、上边界算子 `δ^k`、以及
  **`H⁰(X;F) ≅ Γ(X;F)`（整体截面）** 和 `H¹` 是粘合障碍
- **`find.radius`（自然近邻）**：一个**声称 parameter-free 的自适应邻域大小**
  做法 —— 这条直接对着 P1，见 §八

⚠️ **三处必须标出来的问题**（详见各节）：

1. **§七 那句「Infomap 没有分辨率参数」是错的或至少未经验证** —— 已撤。
2. **「excess of mass」这个术语在任何抓到的正文里都没出现**，只有 "stability"。
3. **`pers(b) = death − birth` 那个教科书定义没在抓到的正文里出现** ——
   所以「持续性的确切定义」只核到了 HDBSCAN 与 FOSC 两个**工程版本**，
   纯拓扑版本的定义**仍未核对**。

---

## 一、生态学：β 多样性的**周转 / 嵌套**分解 —— 直接命中 P4 与 P3

### 是什么（已核对正文）

群落生态学研究「多个地点之间的物种组成差异有多大」，把那差异（β 多样性）
拆成两个分量。**实现方就是方法本人**：`betapart` 1.6.1 的维护者是
Andres Baselga，包名副标题就是
`Partitioning Beta Diversity into Turnover and Nestedness Components`
（[CRAN 参考手册](https://cloud.r-project.org/web/packages/betapart/refman/betapart.html)）。

**核到的确切结构**（`beta.pair` / `beta.multi` 的 `Value` 段）：

    两个指数族：sorensen 与 jaccard
    beta.pair 返回 **3 个**矩阵：

      sorensen 族   beta.sim  周转，用 **Simpson** 成对相异度
                    beta.sne  嵌套，用 **Sørensen 的嵌套分数**
                    beta.sor  总相异度，用 Sørensen（β 多样性的单调变换）

      jaccard 族    beta.jtu  周转，用 **Jaccard 的周转分数**
                    beta.jne  嵌套，用 **Jaccard 的嵌套分数**
                    beta.jac  总相异度，用 Jaccard

⚠️ **更正一**：我原先只写了 `β_jac = β_jtu + β_jne` 这一条，
而且暗示分量与总量是「Simpson / Sørensen / 三者相加」的随意搭配。
实际上**两个指数族各自内部才可加**，而且周转分量在 Sørensen 族里用的是
**Simpson** 指数 —— 跨族混用是错的。要用就得先声明用哪一族。

⚠️ **更正二**：我原先只说了「成对分解」。**`beta.multi` 是多地点的**
（`beta.SIM`/`beta.SNE`/`beta.SOR` 与 `beta.JTU`/`beta.JNE`/`beta.JAC`）。
这一条对 DCE 比对成对版本重要得多 —— DCE 是 N 个视图，不是 2 个。

**另外三项核到的、第一版完全没提的东西：**

1. **`beta.sample`：重采样 + 显著性检验是这个框架自带的一步。**
   手册的例子直接把 p 值算出来：
   `p.value.beta.SIM <- length(which(south < north)) / 100`，
   并注释「p<0.01」—— 也就是说**这个领域早就把「置换检验」当成标准配件**，
   而不是像我以为的那样要从空间统计那边借。对 DCE 的意义：
   「焦点是不是真的」这个问题，生态学有现成的做法可以直接照搬。
2. **`beta.temp`：时间维的同一套分解。** DCE 的视图若来自不同时间片，这条路已经铺好。
3. **⚠️ 命名并不统一 —— 有竞争性的分解。** 手册的参考文献里同时列着
   [Legendre 2014](https://www.sciencedirect.com/science/article/abs/pii/S1574954116000133)，
   而 Legendre 那两个分量叫 **replacement / richness difference**，不叫 nestedness；
   还有 Baselga & Leprieur 2015《Comparing methods to separate components of beta diversity》。
   **所以「嵌套」这个命名本身是有争论的** —— 借它的时候不能以为它是唯一答案。

配套概念（**这两条仍是检索片段，未核对正文**）：

- **α / β / γ**：Whittaker 的关系是 `β = γ / α`
- **dark diversity**：**「本该在那里却不在」** —— 生态学对「缺失」的正式概念，
  而且它**不是**「对立」。对应 DCE 的 omission，且这个对应是第一版里我最看好的一条


### 映射到 DCE

**这张表几乎是一一对应的：**

    DCE 的 consensus        ↔  α（局域共有）
    DCE 的分歧总量           ↔  β
    DCE 的 alternative
      + contradiction        ↔  **β_jtu 周转**：同一位置上给出**互不包含**的结构
    DCE 的 refinement
      + omission             ↔  **β_jne 嵌套**：一方是另一方的**真子集**
    DCE 的 omission          ↔  **dark diversity**：本该在、却不在（且没有表态反对）

### 会改什么（这一条是重点）

**P4 会被它正面解开。** DCE 现在把四类做成**互斥标签**，于是必须决定
「这个单元到底算 refinement 还是 omission」—— 而我量出那个决定**随构造移动**：
同一个单元相对 A 是精炼、相对 C 是缺失。生态学早就放弃了这种互斥：

    不要去问「它是哪一种」，而是问「它在这两个分量上各占多少」。
    refinement 与 omission **不是两类东西，是同一个嵌套现象的两个方向。**

而嵌套分量在生态学里**本来就是有方向的**（谁嵌套谁），这正好对应我发现的
「refinement 的主语是 (粗, 细, 单元) 而 omission 的主语是 (视图, 单元)」——
**我以为是我发现的，其实生态学有名字、有度量、有几十年的争论。**

**P3 也会松一点**：`β = γ/α` 的形式说明「共识」与「差异」不是两个独立的阈值判断，
而是同一个量的两端。合取是 `α` 的一种极端取法。

### 代价

- 四个类型名要**重写**：从互斥标签改成两个连续分量 + 方向。这会动 §五/§六
- 「分别恢复四类」这个测试（§十五 Test 3）的判据要重设计 ——
  而我已经量出它**只在无歧义构造下才有定义**，所以这一步本来就要做
- 生态学的度量是为**物种有无**设计的（二值、对称），DCE 的单元是**有类型的三元边**，
  照搬度量要重新推

---

## 二、流行病学 / 空间统计：**扫描统计量与蒙特卡洛** —— 直接命中 P1

### 是什么（已核对正文）

`scanstatistics` 1.1.2，包名标题就是 `Space-Time Anomaly Detection using Scan Statistics`，
描述里写着 **`Hypothesis testing is made possible by Monte Carlo simulation`**
（[CRAN 参考手册](https://cran.r-project.org/web/packages/scanstatistics/refman/scanstatistics.html)）。

**核到的确切机制：**

    zones 是一个**必填**参数 —— 候选簇的「家族」由**调用方给出**，不是算法自己选。
    包提供三种标准的家族构造：

      knn_zones(k_nearest)      对每个位置，取它的 1、2、…、k 个最近邻构成
                                **逐层递增的嵌套集合**（这就是「自适应尺度」的现成形式）
      flexible_zones(knn, adj)  Tango (2005) 的**连通**柔性形状 ——
                                要求区域内部连通（任何两点可通过区域内部相邻点到达）
      powerset_zones(n)         1..n 的全部 2^(n-1) 个非空子集（穷举）

    蒙特卡洛 p 值（手册给了精确式子）：

      (1 + Σ_{i=1..R} I(λ_i > λ*)) / (1 + R)

    另有 Gumbel 版本：把 replicate 拟合一个 Gumbel 分布再算 p。
    零模型由 `permute_matrix(A)` 提供 —— **保持行与列的边际**做置换。

⚠️ **更正三（这条最重要）**：我原先写「**不去定半径，而是把所有半径都扫一遍**」——
**那是不准确的。** 扫描统计量**不负责选半径**：`zones` 是调用方必须提供的输入。
它解决的是「**在给定的候选家族里，哪些簇是真的**」，而不是「半径该是多少」。

    它把「选一个半径」换成了「**给出一个可辩护的候选簇家族**」，
    并用蒙特卡洛回答「这个簇显著吗」。

对 DCE 的意义因此要改写：**不能指望它替我们选半径。**
它能给的是 —— 我们给出一个锚点邻域家族（照 `knn_zones` 的样子逐层递增），
然后用置换检验说「哪些焦点是真的」。**半径那一步仍然是本层要声明的判据**，
只不过可以照 `knn_zones` 那样声明成「逐层递增的嵌套家族」而不是一个数 ——
那就把我们那个「扫半径报曲线」升级成「扫家族并做显著性判断」。


### 映射到 DCE

**这正好是你说「先给一个半径，但不固定它，让它随数据校准」的成熟版本，
而且比我们现在做的更彻底：**

    我们现在：扫半径 → 算 r*（塌成 1 的最小半径）→ 报曲线
    扫描统计量：扫半径 → 每一步与**零模型**比 → 显著的那些才是簇

区别在**有没有零模型**。我们现在的 `r*` 只是一个「什么时候全糊成一团」的
几何事实，它**没有说哪些焦点是真的**。加了零模型（例如把分歧记录在结构图上
随机重排）就能回答那个问题，而且**不需要任何阈值** ——
这正是本仓库一直在用的手法（`field/` 里的置换检验 + Holm 校正就是同一个家族）。

### 代价

- 要定义**零模型**。而「分歧记录在结构图上随机」有几种合理写法，
  选哪一种会影响结论 —— **零模型的选择会成为一个新的、需要声明的判据**
- 蒙特卡洛要跑很多次，性能与确定性都要安排（本仓库全程确定性、无 `random`；
  置换检验要自写可复现的置换，而不是用 `random`）
- 它解决「哪些焦点显著」，**不解决** P3（共识太脆）

---

## 三、拓扑：**持久同调 / 合并树** —— 「不固定半径」的原理化版本

### 是什么（读了正文，**但纯拓扑那一半仍未核对**）

不要为一个点云选一个尺度，而是**在所有尺度上看它**，只保留活得久的。

**工程版本（已核到确切公式）：HDBSCAN 的簇稳定性**
（[hdbscan 官方文档](https://hdbscan.readthedocs.io/en/latest/how_hdbscan_works.html)）：

    λ = 1 / distance
    λ_birth(簇分裂出来时)   λ_death(它再分裂时)
    λ_p = 点 p 掉出该簇时的 λ，介于 λ_birth 与 λ_death 之间

    **stability = Σ_{p ∈ 簇} ( λ_p − λ_birth )**

    抽取规则：先设所有叶节点为已选；按**逆拓扑序自下而上**，若子簇稳定性之和
    > 本簇稳定性，则把本簇稳定性**设为子簇之和**，否则**宣布本簇已选并取消其全部后代**

同页还给互可达距离：`d_mreach-k(a,b) = max{ core_k(a), core_k(b), d(a,b) }`

**另一个工程版本（已核到确切公式）：FOSC 的跨尺度形式化**
（[CRAN dbscan 参考手册](https://cran.r-project.org/web/packages/dbscan/refman/dbscan.html)，
出处 Campello/Moulavi/Zimek/Sander 2013, DMKD 27(3):344-371）：

    max_{δ₂..δ_k}  J = Σ_{i=2}^{k} δ_i · S(C_i)
    S(C_i) = Σ_{x_j ∈ C_i} ( 1/h_min(x_j, C_i) − 1/h_max(C_i) )

而它的说明文字**正是我在第 3 条里想说的东西**：

> if you vary the linkage/distance threshold across **all possible values**,
> more prominent clusters that **survive over many threshold variations**
> should be considered as stronger candidates

**合并树**（[CRAN TDA 参考手册](https://cran.r-project.org/web/packages/TDA/refman/TDA.html)）：
`clusterTree` 返回超水平集的簇树（`lambda` 树与 `kappa` 树），字段含
`id/children/parent/.../lambdaBottom/lambdaTop/rBottom/rTop`；
`diagram` 是 `P×3` 矩阵：第一列维数（0/1/2），第二三列 Birth 与 Death。

### ⚠️ 两处必须标出来的未核对

1. **「excess of mass」这个术语在任何抓到的正文里都没出现** —— 只有 "stability"。
   第一版用了那个词，**撤掉**。
2. **`pers(b) = death − birth` 那个教科书定义没在抓到的正文里出现** ——
   TDA 手册的 `silhouette` / `maxPersistence` 段没进抓取窗口。
   所以「持续性的确切定义」**只核到了 HDBSCAN 与 FOSC 两个工程版本**，
   纯拓扑的 barcode/persistence 定义**仍未核对**。
   `h_min` / `h_max` 的准确定义也没核到（手册只给符号，DMKD 原文付费墙）。


### 映射到 DCE

    半径 r 从 0 涨到直径 —— 这就是一个**单参数族**。
    我们已经在算这条曲线（`focus.radius_curve`），但只看了「焦点数」。
    合并树要看的是：**哪几次合并只是昙花一现，哪几次持续很宽**。

    「持续宽度」就是校准 —— 而不是我那个 `r*`（塌成 1 的点）。

而且它能顺手给出 **P2 的替代指标**：一条分歧记录/一个焦点若只在很窄的半径区间里
存在，它就是**噪声性的**；跨很宽区间存在的才是结构。那比 `focused` 压缩比
（在焦点为 1 时是假压缩）有意义得多。

### 代价

- 我们现在的「距离」是**图上跳数**，是离散的，合并树会很浅（直径 3~9）
- 真正的持久同调需要**带权距离**（例如结构相似度），而权重从哪来又是一个判据问题
- 比扫描统计量更远离「能直接落地」

---

## 四、粗糙集：**下近似 / 上近似 / 边界域** —— 正面对付 P3（共识太脆）

### 是什么（已核对正文，且**更正了一处公式错误**）

`RoughSets` 1.3-8（[CRAN 参考手册](https://cran.r-project.org/web/packages/RoughSets/refman/RoughSets.html)）。
手册里有一句**正好印证本仓库那条规矩**的原文：

> By using the indiscernibility relation for objects/instances,
> **RST does not require additional parameters to analyze the data.**

RST 由 **Pawlak 1982** 提出。包自己列的基础概念是四项：
**不可分辨关系 / 下上近似 / 正域 / 可辨矩阵**，
而正域的用途手册写的是「determine objects that are included in positive region
and **the degree of dependency**」。

⚠️ **更正四：我原先写的 `γ_P(X) = |下近似| / |X|` 把两个不同的量混成了一个。**
粗糙集里有两个都叫「质量」的东西，**必须分开**：

    近似精度（accuracy of approximation）
        α_R(X) = |R̲X| / |R̄X|      **下近似 ÷ 上近似**
    近似质量 / 依赖度（quality of approximation / degree of dependency）
        γ_R(X) = |POS_R(X)| / |U|  **正域 ÷ 全体**

我原先那个式子是 α 的形状却挂了 γ 的名字。**对 DCE 而言两者含义不同，
选哪一个是有后果的**：α 说的是「确定在里面的占可能在里面的多少」（紧不紧），
γ 说的是「全体里有多少是能确定的」（覆盖多少）。P2 要的是哪一个，得先想清楚
—— 这正是「先写判据」那条规矩的用处。

**另外两条核到的、值得记的：**

1. **模糊粗糙集把参数又请回来了。** 包的 FRST 部分有 `t.tnorm` / `t.implicator` /
   `alpha`（FVPRS）/ `beta.quasi`（β-PFRS）/ `k.rfrs`（RFRS）/ `q.some`,`q.most`（VQRS）
   一整排参数。**经典 RST 无参数，扩展版不是。**
   对 DCE 的含义：**要借就借经典那一半**，模糊那半会重新引入本仓库不能有的阈值。
2. **离散化在包里是一个独立任务**（`D.discretization.RST`），因为 RST 要求离散属性。
   **而 DCE 的属性本来就是二值的**（单元在不在某个视图里），
   所以这一步对我们是**免费**的 —— 这是这段借用里最省事的一点。


### 映射到 DCE

    对象 = 结构单元        属性 = 视图
    单元在视图里 = 1，不在 = 0

    下近似  ↔  **共识**（在全部视图里）—— 就是我们现在算的合取
    上近似  ↔  至少出现在一个视图里 —— 就是 `universe`
    边界域  ↔  **分歧的载体** —— 而且它天生就是「可能」的语义，不是「冲突」
    γ       ↔  **P2 缺的那个指标**：共识占全体多少。它是个比例，
               但**不是「多少人说」**（那撞 §C9 #5）—— 是「多少结构是全体的共识」，
               量的是**结构**不是**人**。这个区分很细但成立。
    约简     ↔  **哪些视图对这个分歧是冗余的** —— 一个真正的压缩定义，
               而且它**不需要阈值**

`γ` 这一条值得单独说：我一直没能给 Compression 找到一个不与
`§C9 #5` 冲突的定义，因为「压缩」听起来总像在给结构加权。
粗糙集给的是「**可分辨关系**」—— 哪些视图换掉之后分歧的划分不变。
**那是结构性的，与热度无关。**

### 代价

- 粗糙集的经典形式要求**离散属性**。我们的视图就是离散的（在/不在），**正好合适**
- 「约简」在属性多的时候是 NP-难的，但我们的视图数是个位数 —— 可枚举
- 它给判据，**不给聚类**。P1 还得靠别的

---

## 五、形式概念分析：**概念格 + 稳定性** —— 共识结构的另一种正式化

### 是什么（已核对正文）

`fcaR` 的 lattice metrics vignette
（[CRAN](https://mirrors.cstcloud.cn/CRAN/web/packages/fcaR/vignettes/advanced_lattice_metrics.html)）。
从「对象 × 属性」表构造**概念格**：每个概念是一对（外延 = 对象集，内涵 = 属性集）且极大配对。
**整格是无参数的** —— 这一点由「找概念」本身不引入阈值保证。

**核到的精确公式（三个指标，我只写了第一个）：**

    稳定性（intensional stability，对噪声的稳健性）
        σ(C) = |{ A ⊆ Ext(C) | A' = Int(C) }| / 2^{|Ext(C)|}

    分离度（separation，这个概念引入了多少**新**对象）
        Sep(C) = |Ext(C)| − |∪_{K ≺ C} Ext(K)|
                 （≺ 是直接子概念）

    模糊密度（density，概念在原始关系里的内聚程度）
        ρ(C) = Σ_{g ∈ Ext(C), m ∈ Int(C)} I(g,m) / (|Ext(C)| · |Int(C)|)
        ⚠️ 二值数据下密度恒为 1 或 0 —— **对 DCE 无用**，因为我们就是二值的

⚠️ **新增：`Sep(C)` 是我原先完全漏掉、而它可能比稳定性更有用的一个量。**
它问的是「这个概念比它的直接子概念多覆盖了哪些对象」——
翻成 DCE 的话：**这个焦点比它下面的焦点多解释了什么结构。**
那正是 P2（压缩）缺的那种「这一步到底有没有新增信息」的判据，
而且它是**纯结构的、不需要阈值**。

（这条仍是检索片段，未核对）


### 映射到 DCE

    对象 = 结构单元，属性 = 视图
    **共识结构 = 外延为全体视图的那个概念的内涵**
    分歧结构 = 格中「外延不是全体」的那些概念

它比粗糙集更结构化：**格本身就把「哪些单元被哪些视图共同持有」的
全部层次关系摆出来了**，而 DCE 现在只取了最顶上的一个合取。

不稳定（低稳定性）的共识 = **脆共识** —— 那正好是 P3 的症状，
而它给了一个量化它的办法，且不需要阈值。

### 代价

- 概念格在对象多时**指数膨胀**（我们的单元数几十到几百，可能已经不可行；
  真实规模肯定不可行），要用冰山格，而冰山格**需要阈值** —— 又回来了
- 与粗糙集有重叠，两者选一即可

---

## 六、应用拓扑：**胞腔层与上同调** —— 「分歧能不能粘起来」

### 是什么（**读到正文，含确切定义**）

把局部数据当成一个**层（sheaf）**：局部一致的部分是 `H⁰`，**粘不起来的障碍**是 `H¹`。
确切定义（[Hansen & Ghrist, arXiv:1808.01513v1](https://arxiv.org/html/1808.01513v1)）：

    胞腔层：每个胞腔 σ 赋一个向量空间 F(σ)（stalk）；
            每个关联对 σ ⊴ τ 给一个线性映射 F_{σ⊴τ}: F(σ) → F(τ)；
            并要求 F_{σ⊴σ} = id 且 ρ ⊴ σ ⊴ τ ⟹ F_{ρ⊴τ} = F_{σ⊴τ} ∘ F_{ρ⊴σ}

    整体截面：x 是「每胞腔取 x_σ ∈ F(σ) 且 x_τ = F_{σ⊴τ} x_σ 对**所有** σ ⊴ τ 成立」
              其空间记作 Γ(X; F)

    C^k(X;F) = ⊕_{dim σ = k} F(σ)
    带符号关联数 [σ:τ] ∈ {0, ±1}，且 Σ_γ [σ:γ][γ:τ] = 0      ← 上边界算子的来源

    δ^k|_{F(σ)} = Σ_{dim τ = k+1} [σ:τ] · F_{σ⊴τ}

原文接着写：`δ^k ∘ δ^{k−1} = 0`，且
**`H⁰(X;F)` 自然同构于 `Γ(X;F)`，即整体截面的空间。**

"`H⁰` classifies global sections and **H¹ the obstructions thereunto**"、
"the obstacle is **precisely the torsion in `H¹ = C¹/im d`**"
（[Ghrist & Ding, arXiv:2511.00677](https://arxiv.org/html/2511.00677)）

⚠️ **两版渲染的编号不同**：arXiv 版里胞腔层是 Def 2、整体截面是 Def 3；
ar5iv 版是 Def 4、Def 5。**引用必须注明版本**，否则对不上号。

同一条思路在分布式系统里也有（[arXiv:2503.02556](https://arxiv.org/html/2503.02556)）：
「胞腔层是分析**局部计算的全局一致性要求**的自然数学框架」、
「**终止解恰好就是它的整体截面**」、「任务层的上同调**编码了求解的障碍**」。


### 映射到 DCE

**这是对 DCE 核心问题最精确的数学表述：**

    每份视图是局部的；问题是「它们能不能粘成一个全局结构」
    H⁰  = **共识**（能粘起来的部分）
    H¹  = **障碍**（无论怎么粘都粘不上的那部分）

关键在于：`H¹` 区分了**「局部不一致但可调和」**与
**「存在绕任何一圈都消不掉的矛盾」** —— 后者才是**真正不可调和的分歧**。
DCE 现在做不到这个区分：它把所有分歧平铺成一堆记录。

### 代价

- 数学上最重的一条。要定义层、余边界算子、上同调，且要能解释给用户
- 它解决「分歧的**性质**」，不解决聚类与指标
- 我判断**现在上这个太早**：DCE 连 Consensus 是不是合取都还没定

---

## 七、信息论：**地图方程 / 描述长度** —— 「几个焦点」由谁定

### 是什么（**公式读了正文；但有一句话没有正文支持，已撤**）

Infomap 的地图方程用**最小描述长度**选社区划分。**两级形式的精确式子**（Eq.1）：

    L(M) = q_↶ · H(Q) + Σ_{m∈M} p_m^↻ · H(P_m)

    q_↶  = Σ_m q_m^↶        整体模块进入率
    q_m^↶                   模块 m 的进入率
    p_m^↻ = q_m^↷ + Σ_{u∈m} p_u   模块使用率（q_m^↷ 是离开率）
    H                        Shannon 熵
    Q   = { q_m^↶ / q_↶ }
    P_m = { q_m^↷ / p_m^↻ } ∪ { p_u / p_m^↻ }
    T_uv = w_uv / Σ_v w_uv,  p_v = Σ_u p_u T_uv

**多级形式**（Eq.2）：`L(M) = q_↶ H(Q) + Σ_{m∈M} L(m)`
（[arXiv:2409.10263v1](https://arxiv.org/html/2409.10263v1)）

MDL 论证（[综述 arXiv:2311.04036](https://arxiv.org/html/2311.04036v3)）：
「使网络流量的压缩最大化的那个划分，等价于识别出最能抓住那些流量规律性的模块」；
「给定一个划分，地图方程算出随机游走**每步描述长度的下界**」；
「找到能用**最短代码**解释数据的模型，在模型复杂度与拟合之间权衡」。

### ⚠️ 更正五：**「不需要分辨率参数」这句话我写了，但没有正文支持**

第一版写的是「与模块度不同，它**没有分辨率参数**（模块度有分辨率极限问题）」。
**撤掉。** 检索的结论是：

- 读到的支持最多只到「MDL 自动权衡复杂度与拟合，**自动决定簇数**」
  （2409.10263 有 `automatically selecting the optimal number of clusters`、
  `does not require explicit regularisation`）—— 那是**关于簇数**的，不是
  关于**分辨率**的，两者不是一回事
- 而**反证线索**：那篇综述的目录里**明确有 `Resolution limit.` 小节**
  （§III.3 *Challenges and remedies* 的第一项）。**它的正文没抓到**，
  但一个小节的存在本身就说明这个领域把它当成一个问题在讨论

**所以这句不许当作已验证结论引用。** 这也是一条方法论上的收获：
「我印象里它没有那个毛病」与「正文说了它没有那个毛病」是两件事，
而这次差别体现在一个**方向相反**的结论上。

（抓取失败记录：`mapequation.org` 已改版，`how-it-works` 页 404、
`/map-equation/` 404；`mapequation.r-universe.dev` 403 Cloudflare；
`raw.githubusercontent.com/mapequation/infomap/master/README.md` 404（分支名不对）。）


### 映射到 DCE

    「应该有几个焦点」现在由 `r*` 间接决定（塌成 1 之前）。
    地图方程给的是：**由描述长度决定** —— 一个不需要阈值的原则。

而且它天然与 P2 的 Compression 同源：**压缩就是描述长度**。
这可能是把 Compression 从「输入/输出」这个粗糙比值升级成
「结构本身的描述长度」的路子。

### 代价

- 随机游走需要**转移概率**，而我们的结构图是**无权的** —— 权重从哪来又是判据问题
- 与领域距离最远的一条

---

## 八、聚类方法侧：**自适应尺度**（把半径变成局部量）

### 是什么（**三源二手确认；原论文措辞未核对**）

- **自调谐谱聚类**：每个点有自己的局部尺度，于是「半径」不再是全局常数，而是逐点导出

      σ_i  =  **到第 k 个近邻的距离**
      A_ij =  exp( −d(x_i, x_j)² / (σ_i · σ_j) )

  出处：Zelnik-Manor & Perona, NIPS 17 (2004/2005), 1601-1608。

  ⚠️ **这条是三个独立的 HTML 二手源一致确认的，不是原论文**：

      CRAN `T4cluster` 的 `sc05Z`  —— 「σ_i is the distance from a point x_i to its
                                       nnbd-th nearest neighbor」，默认 `nnbd = 7`
                                      （[出处](https://search.r-project.org/CRAN/refmans/T4cluster/html/sc05Z.html)）
                                      ※ 该页把 `d(x_i, d_j)` 写成了 `d_j`，是笔误
      CRAN `FuzzySpec` 的 `compute.sigma` / `make.adjacency`
                                      （[出处](https://cran.r-project.org/web/packages/FuzzySpec/refman/FuzzySpec.html)）
      MetricGate 的文档                 （[出处](https://metricgate.com/docs/self-tuning-spectral-clustering/)）

  **原论文全文是 PDF**（`proceedings.neurips.cc`），本环境抓不了；
  唯一的 HTML 落地页只有摘要（只说 "a 'local' scale should be used"，**无公式**）。
  所以：**公式 = 三源二手确认；原文措辞 = 未核对；`k=7` 这个默认值来自第三方文档。**

- **HDBSCAN**：见第三节，稳定性代替 ε

### 🆕 新核到的一条，可能最省事：`find.radius`（自然近邻）

[CRAN `FuzzySpec` 参考手册](https://cran.r-project.org/web/packages/FuzzySpec/refman/FuzzySpec.html)：

> `find.radius`：**自然近邻**（natural nearest neighbor）。让 r 递增，
> 直到「入度为 0 的点数不再下降」就停。原文称这是一种
> **parameter-free way to adaptively set the neighbourhood size**
> （改自 Zhu / Feng / Huang 2016, PRL 80:30-36）

**这一条直接对着 P1，而且它的形式比 `knn_zones` 更贴近我们要的：**
它的停止条件是**数据本身的一个现象**（没有点再是「孤立」的），不是我拍的半径。
本仓库那个 `r*`（焦点塌成 1 的最小半径）也是从结构算出来的，
但它是**塌缩点**，而 `find.radius` 是**饱和点** —— 两者都可能有用，
而且都满足「上界由数据算出」那条规矩。

### 映射到 DCE

我们现在的半径是**全局**的（`_within(adj, a, radius)`）。
**自适应版本**是：每条分歧记录自己的尺度。于是：

    锚点稀疏处 → 尺度大（不会强行与远处并）
    锚点密集处 → 尺度小（近处就并）

这**可能正好解开 P1**：共享节点空间下全局半径必然过度合并，
而逐点尺度不会 —— 因为尺度由**分歧本身的分布**决定，不由图的连通性决定。

**这是第三节以下最可能直接能用的一条**，而且改动很小
（`cluster()` 里把常量 `radius` 换成每条记录的局部尺度）。

### 代价

- 需要一个 k（近邻数），而 k 又是一个参数 —— 但它比半径温和得多
  （k 是「看几个邻居」，半径是「多远算近」，前者对结果的影响小一个量级）。
  **而 `find.radius` 那条正好可能把 k 也消掉**（用饱和条件代替选 k）——
  这是它比自调谐谱聚类更值得先试的理由
- 自适应尺度会让结果**不再有单调性**（半径那套单调不增的断言会失效），
  要换一组不变量来钉


---

## 判断与优先级（读正文之后修订过）

| 优先 | 借什么 | 解开 | 成本 | 判断 |
|---|---|---|---|---|
| **1** | 生态学的**周转/嵌套**分解 | **P4** | 中：四类名要重写；**且要先声明用 sorensen 还是 jaccard 族** | **仍然最该借。**核过正文之后理由更硬：它带**多地点版本**（`beta.multi`，正是 N 视图所需）**和自带的重采样显著性检验**（`beta.sample`） |
| **2** | 粗糙集的**正域 / 依赖度 + 约简** | **P2/P3** | 低：属性二值，**离散化免费**；视图数是个位数，约简可枚举 | 借**经典那一半**（无参数）。⚠️ **但先要判据上想清用 α 还是 γ** —— 两个量不是一个意思 |
| **3** | 形式概念分析的**分离度 `Sep(C)`** | **P2** | 低：公式就是「比子概念多覆盖了什么」 | 这一条是新加的、原先漏掉的。它比稳定性更贴合 P2 要问的「这一步有没有新增信息」 |
| **4** | 空间统计的**候选簇家族 + 蒙特卡洛** | **P1 的显著性那一半** | 中：要定义零模型 | ⚠️ **更正后的判断**：它**不替我们选半径**（`zones` 是必填输入）。它能给的是「给出家族之后，哪些焦点是真的」。**半径那一步仍是本层要声明的判据** |
| 5 | **`find.radius`（自然近邻）** —— 🆕 第二轮的收获 | **P1** | **低**：改 `cluster()` 一处 | **升到最高优先级的候选。**它的停止条件是**数据里的一个现象**（入度为 0 的点不再下降），不是我拍的半径；**而且它可能把 k 也消掉**（用饱和代替选 k） |
| 6 | 自适应局部尺度（`σ_i` = 到第 k 近邻距离） | P1 | 低 | 三源二手确认了公式；比第 5 条多一个要选的 k，所以**排在它后面** |
| 7 | HDBSCAN 稳定性 / FOSC / 合并树 | P1/P2 | 中高：需要带权距离 | ✅ 公式已核到（`stability = Σ(λ_p − λ_birth)`；FOSC `Σ(1/h_min − 1/h_max)`）。**纯拓扑的 barcode 定义仍未核到**，但两个工程版本够用 |
| 8 | 概念格 + 稳定性 | P3 | 高：指数膨胀 | 与粗糙集重叠，二选一；**但它的 `Sep` 单独可用**（见上） |
| 9 | 地图方程 | P1/P2 | 高：需要权重 | ✅ 公式已核到（两级 `L(M) = q_↶H(Q) + Σ p_m^↻H(P_m)`）。⚠️ 但第一版那句「不需要分辨率参数」**已撤** |
| 10 | 胞腔层上同调 | 分歧的**性质** | 最高 | ✅ 定义已核到（`δ^k`、`H⁰ ≅ Γ(X;F)`）。**但实现仍然太早**：DCE 连共识是不是合取都还没定 |

**一句话（第二轮修订版）**：P4 借生态学（✅ 已实现）；P2 借粗糙集（✅ 已实现）
加上 FCA 的 `Sep`；P1 **先试 `find.radius`**（改动最小、且可能连 k 一起消掉），
其次 `σ_i` 局部尺度；**判别「哪些焦点是真的」再上零模型**。
第 10 条定义齐了但实现太早，第 9 条公式齐了但缺权重来源。


**读正文之后新增的一条元结论**：这四个领域里有三个（生态、粗糙集、FCA）
**都自带「不要阈值」的机制，而且都是在自己的领域里解决了几十年的问题**。
DCE 现在卡的那两处（焦点、指标），不是没人解决过，是**我们没去找**。


---

## 第三批：五个难题的候选解法（**已核到两条，其余仍未核到**）

前面两批是把「别处有什么成熟思想」摸清。这一批是**对着本仓库的五个具体难题**去找。
结果：**核到两条**，而且两条都比预期更贴。

### 难题一：共识太脆 → **Krippendorff 的 alpha**（✅ 核到正文，对比极有信息量）

现在的共识是合取（出现在**全部**视图里），一有视图漏一条就没了。

**评分者间信度这个领域整片都在处理「评分有缺失」**，而核到的东西给出一条很硬的对比：
[CRAN `irr` 参考手册](https://cran.r-project.org/web/packages/irr/refman/irr.html)里，
**每一个其他系数**的 Details 段都写着同一句话：

> **Missing data are omitted in a listwise way.**

（Cohen's kappa、Fleiss' kappa、ICC、Finn、Kendall's W、Bhapkar、Stuart-Maxwell、
meancor、meanrho、Robinson's A、Maxwell、relInterIntra —— 逐条都写了。）

**而 `kripp.alpha` 是唯一的例外**：它的说明里**没有这句话**，
而它的示例数据**直接带 `NA`**：

```r
nmm <- matrix(c(1,1,NA,1,2,2,3,2,3,3,3,3,3,3,3,3,2,2,2,2,1,2,3,4,4,4,4,4,
                1,1,2,1,2,2,2,2,NA,5,5,5,NA,NA,1,1,NA,NA,3,NA), nrow=4)
kripp.alpha(nmm)          # 默认 nominal
kripp.alpha(nmm,"ordinal")
```

它返回的字段里有 **`cm`（concordance/discordance matrix，算 alpha 用的那张表）**
与 `nmatchval`（匹配计数）—— **它不靠「把有缺失的对象整条删掉」，而是在「对子」上建表。**

```r
kripp.alpha(x, method=c("nominal","ordinal","interval","ratio"))
$value       alpha 的值
$cm          **一致性/不一致性矩阵**（计算所用的那张表）
$stat.name   "nil" —— **没有检验统计量**（Krippendorff 1980）
```

**对 DCE 的意义**（我的判断，不是引文）：

    合取  =  listwise deletion 的**极端**（一条都不许缺）
    α     =  在「对子」上建一致性表，**从而容忍缺失**，且没有阈值、没有检验统计量

这正好是 P3 要的东西：**一个不靠阈值、能容忍缺失、且不退化成空集的共识定义。**
⚠️ 但**它是不是一个「集合」还需要设计**：α 输出的是一个标量，而 DCE 需要知道
**哪些结构是共识**。可能的桥是 `cm` 那张表本身 —— 但那要先想清判据再动手。

### 难题四：两方对立接不上 → **Dung 抽象论辩框架**（✅ 核到确切定义）

⚠️ **这条比我预期的更贴。** 核到的正文是
[Hackage `Dung-1.1` 的模块文档](https://hackage-content-origin.haskell.org/package/Dung-1.1/docs/Language-Dung-AF.html)：

```haskell
data DungAF arg = AF [arg] [(arg, arg)]
-- "a set of arguments ... and an **attack relation on these arguments**"
```

**攻击关系是「论证对论证」** —— 不是「论证对结论」。这正是难题四的症结所在：
Arena 里「同一结论被一条证据支持、被另一条反对」，在 Dung 里**天然可表达**，
因为攻击挂在**论证**之间，不需要主客体都相同。

核到的核心定义（逐条来自正文）：

    conflictFree   args 内部无攻击
    f              **特征函数**：给出「相对 args 可接受」的那些论证
    admissible     args 是 conflictFree **且** args ⊆ f(af, args)
    grounded       在**空集**上迭代 f 到不动点 → **唯一**（`groundedF`）
    complete       没有 illegallyIn / illegallyOut / illegallyUndec 的标注
    preferred      inLab 在**集合包含下极大**（`isPreferredExt`）
    stable         `undecLab labs == []`（`isStable`）
    semiStable     undecLab 在集合包含下**极小**（`isSemiStable`）

    三值标注 Status = In | Out | **Undecided**
    illegallyIn   标了 In，但不是**所有**攻击者都是 Out
    illegallyOut  标了 Out，但**没有**一个 In 的攻击者
    illegallyUndec 标了 Undecided，但「攻击者全是 Out」**或**「有 In 的攻击者」

**对 DCE 的第三点意义**：那个 **`Undecided`** 三值 ——
它与本仓库的 `omission`、以及粗糙集的**边界域**是同一个位置的东西：
「不能确定在里面，也不能确定在外面」。**三个不同领域各给了一个第三值。**

### ⚠️ 还没核到的（这一批的缺口）

| 难题 | 候选 | 状态 |
|---|---|---|
| 三 · 缺失表示会爆炸 | 对比集挖掘 / emerging patterns | ❌ 只搜到 PDF（JMLR 综述） |
| 五 · 按邻近性分组会塌 | **双聚类 / 共聚类** | ❌ **`biclust` 的 refman 返回 404**（换 URL 再试） |
| 二 · 压缩指标没意义 | MDL 两段式编码 / 率失真 | ❌ 未试 |
| — | 系统发生学的 strict / majority-rule consensus | ❌ 未试 |

**难题五尤其要紧**，因为它是刚刚被量出来的**活阻塞点**：
立场材料上换尺度不行、换合并规则也不行，所以焦点机制需要**换分组依据**
（按特征而非按位置）—— 而双聚类正是那个依据的现成候选。**它还没核到。**

---


## 附：第二轮检索的其余收获（都有正文与 URL）

这些是检索过程中撞见的、与「多视图差异度量 / 无阈值分组 / 显著性检验」相关的成熟条目。
**都读到了正文**，但**都还没评估是否值得借**。

| 条目 | 核心式子 / 说法 | 出处 |
|---|---|---|
| **DBCV**（密度聚类的内部有效性指标） | DSC = 簇内 MST（基于 all-points-core-distance 的互可达距离）最大边权；DSPC = 两簇 MST 内部节点间最小可达距离；指数 ∈ [−1,1]；噪声只进加权平均 | CRAN `dbscan` refman |
| **Bottleneck / Wasserstein 距离** | 「两个图里点的最优匹配的代价」，对角线点参与匹配；Wasserstein 由 p 定幂次 | CRAN `TDA` refman |
| **TDA 的显著性检验** | `bootstrapDiagram`（取 (1−α) 分位的 bottleneck/Wasserstein）；`bootstrapBand`（ℓ∞ bootstrap 一致置信带）；`hausdInterval`（c=2q，[0,c] 为有效 (1−α) 置信区间，引 Fasy et al. 2013 Thm 3）；`multipBootstrap` | CRAN `TDA` refman |
| **蒙特卡洛 p 值**（与第二节同式） | `φ = (1 + Σ_{i=1..R} I(λ_i > λ*)) / (1 + R)` | CRAN `scanstatistics` refman |
| **FARI**（模糊 Adjusted Rand Index） | Frobenius 内积，比较行和为 1 的隶属矩阵 | Andrews/Browne/Hvingelby 2022, J. Classification 39:326-342 |
| **SNN**（共享最近邻相似度） | `SNN(i,j) = |N_r(i) ∩ N_r(j)| / r` | CRAN `FuzzySpec` refman |
| **`find.radius`（自然近邻）** | 见 §八 —— **这条已单列进优先级表** | CRAN `FuzzySpec` refman |
| **算术持续性 / 精度分级条码** | `dim_{R/π} im(∂_k) = #{j : 1 ≤ a_j ≤ k}`；`|H¹_tors| = (#(R/π))^{Σ a_j}`；`d ≡ d' (mod π^m) ⟹ ∂_k(d) = ∂_k(d')` for k < m | [arXiv:2511.00677](https://arxiv.org/html/2511.00677) |

⚠️ **注意其中两条的性质**：`bootstrapDiagram` / `hausdInterval` 那一族是
**bootstrap 置信区间**，而本仓库的规矩是「阈值要有基线数据」——
bootstrap 正好是**用数据自己造基线**，与那条规矩相容。
这与 `field/` 里已经用熟的置换检验 + Holm 校正同族。

---

## 附：抓取失败清单（免得下次重复踩）

| URL | 结果 |
|---|---|
| `mapequation.org/infomap/how-it-works/` | 站点改版，404（公式页已不存在） |
| `mapequation.org/map-equation/` | 404 |
| `mapequation.r-universe.dev/infomap/doc/manual.html` | 403 Cloudflare |
| `raw.githubusercontent.com/mapequation/infomap/master/README.md` | 404（分支名非 master） |
| `github.com/mapequation/infomap` | 被导航栏占满，正文前截断 |
| `ar5iv.labs.arxiv.org/html/2311.04036`（及 v1） | `fetch failed` / 超时（两次） |
| `arxiv.org/html/2503.02556v1`、`/2511.00677v1` | 超时（**去掉版本号后成功**） |
| `export.arxiv.org/api/query?...` | `fetch failed` |
| `proceedings.neurips.cc` 的 NIPS 2004 全文、`arXiv:1402.4385`（地图方程分辨率极限） | **仅 PDF**，抓不了 |
| Wiley `doi/full`、`en.wikipedia.org`、`plato.stanford.edu` | 已知 403 / `fetch failed` |

**可复用的路子（两轮都靠它拿到正文）**：

    CRAN 参考手册      https://cran.r-project.org/web/packages/<包>/refman/<包>.html
    hdbscan 官方文档    https://hdbscan.readthedocs.io/...
    arXiv HTML 版      https://arxiv.org/html/<id>      ← **不要带 v1 后缀，容易超时**

---

## 我不打算借的

- **任何需要「重要性」「权威」「热度」的权重来源** —— 撞 `§C9 #5` / §二十，
  上面好几条（地图方程、持久同调）卡在这一点上，这不是巧合：那些方法
  假定权重是给定的，而 DCE 的整个约束就是**不能有那种权重**
- **任何以「模型评分」为核心的 LLM-as-judge 路线** —— §二十 明文排除
- **把四类合成一个 F1 的做法** —— 已经量出它会把「定义使然」与「算法错了」抹平

---

## 怎么处置这份文档

**第 1、2 条已经做了**（见开头「实现进度」）。剩下的：

1. ~~先只做第 1 条（生态学）~~ ✅ 做完了：`analysis/beta.py`。
   它动的是判据而不是指标，而判据是地基 —— 事后看这个顺序是对的。
2. ~~第 2 条（粗糙集）~~ ✅ 做完了：`metrics/approximation.py`。
   顺带把 §十六 那个问题变成了一个数。
3. **接下来最该做的是第 8 条（自适应局部尺度）**，因为改动只有一处，
   而且 `scanstatistics` 的 `knn_zones` 已经给了现成形式（逐层递增的嵌套家族）。
   它也是第 5 条（FCA 的 `Sep`）的前置 —— `Sep` 需要焦点层次，
   而层次只能从嵌套家族里来。
4. **再做第 2 条的零模型部分**（蒙特卡洛显著性），
   把「哪些焦点是真的」变成一个可判定的问题。
   注意它的前置是本仓库自己定过的那条规矩：**零模型的选择会成为新的判据**，
   得先写下来再跑。
5. 第 3、6、7 条**先放着** —— 三条里有两条连正文都没核到，
   在没读正文的情况下动手，就是这份文档一开始要避免的那种事。

⚠️ **已实现的两条都照本仓库的老规矩走完了**：先写判据（`CRITERIA.md` /
模块 docstring），再造材料，再拿检查去撞，然后如实报 ——
包括**报出两处我自己写错的东西**：
β 的定理陈述（第一版漏了「空视图」这个退化情形）与原子的 α/γ 混淆。

