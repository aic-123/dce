"""公开数据放在哪 —— **一处定义，别处都从这拿**。

⚠️ 原先**五个地方各写了一遍** `C:\\Users\\19253\\Desktop\\_kgdata`：
`checks/countries.py` · `checks/perspectrum.py` · `checks/climatefever.py`
· `checks/index.py` · `checks/acceptance.py`。

**那是我这台机器的路径** —— 别人把仓库 clone 下来，一个用到公开数据的检查
都跑不了，而 README 只说「数据不在仓库里」，**没说该放哪**。

⇒ 现在按顺序找：

    1. 环境变量 `DCE_DATA`            指向数据目录
    2. `<仓库>/_kgdata`              **推荐**：放在仓库旁边
    3. `<仓库>/../_kgdata`
    4. 历史绝对路径                  兜底（免得本机突然失效）

找不到就返回 `None`，调用方**走三态跳过** —— 而不是静默用别的东西顶替。

⚠️ 「跳过」与「过」在报告里是分开写的：**跳过不等于通过。**
"""

from __future__ import annotations

import os
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent

#: 历史绝对路径，**只作兜底**。新环境请用 `DCE_DATA` 或仓库旁的 `_kgdata/`。
LEGACY = pathlib.Path(r"C:\Users\19253\Desktop\_kgdata")

#: 期望放在数据目录下的文件名（README 的「公开数据从哪来」一节列了来源）。
FILES = {
    "countries_S1.txt": "villmow/datasets_knowledge_embedding · "
                        "other/countries/S1/train.txt",
    "countries_S2.txt": "同上 · S2/train.txt",
    "countries_S3.txt": "同上 · S3/train.txt",
    "perspectrum.json": "CogComp/perspectrum · "
                        "data/dataset/perspectrum_with_answers_v1.0.json",
    "evidence_pool.json": "同上仓库的 evidence 池（可选，`load_pools` 用）",
    "perspective_pool.json": "同上仓库的 perspective 池（可选）",
    "climate-fever.jsonl": "tdiggelm/climate-fever-dataset · "
                           "dataset/climate-fever.jsonl",
}


def candidates() -> list:
    """按优先级列出候选目录。**纯函数**，便于断言。"""
    out = []
    env = os.environ.get("DCE_DATA")
    if env:
        out.append(pathlib.Path(env))
    out.append(ROOT / "_kgdata")
    out.append(ROOT.parent / "_kgdata")
    out.append(LEGACY)
    return out


def directory():
    """第一个**真的存在**的候选目录；一个都没有就返回 `None`。"""
    for d in candidates():
        if d.is_dir():
            return d
    return None


def path(name: str):
    """数据目录下的某个文件；**目录不存在或文件不存在**都返回 `None`（三态）。"""
    d = directory()
    if d is None:
        return None
    p = d / name
    return p if p.is_file() else None


def where() -> str:
    """给报告用的一句话：数据从哪找的。"""
    d = directory()
    return str(d) if d is not None else "**没找到**（设 DCE_DATA 或放一份 _kgdata/）"
