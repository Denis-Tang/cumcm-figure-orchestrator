# Provider scorecard

评分对象分两层：上层 Skill 负责理解、设计或审查，下层 renderer 负责生成可复现资产。评分不是 GitHub 热度榜，也不使用一个总分覆盖所有场景。

## 维度

所有维度为 0–10 分，并单独记录 `evidence_confidence`：

- `visual_aesthetics`：默认构图、视觉层次和论文风格。
- `semantic_numeric_accuracy`：能否忠实表达数据、公式和几何关系。
- `text_accuracy`：标签、中文、公式和符号的精确性。
- `collision_avoidance`：自动布局、标签避让和裁切控制。
- `vector_export`：SVG/PDF 和后续编辑能力。
- `reproducibility`：源码、配置和固定输入能否稳定复现。
- `speed`：从结构化需求到可审查初稿的速度。
- `cumcm_auditability`：数据、代码、来源和 AI 使用能否完整留痕。
- `scenario_fit`：针对 data chart、flowchart、network、map、conceptual schematic 的适配分。

## 解释规则

路由先执行硬门禁，再计算加权分。因此，图像生成模型即使概念图审美分高，也不能进入“精确数值图”候选；不能输出矢量或不能保留准确文字的工具，不会成为正式流程图的首选。

评分是当前版本的专家基线，不是假装完成了大规模人工盲测。`evidence_confidence` 为 `high` 表示能力由确定性机制/官方文档和本地接口支持；`medium` 表示有文档和样例但尚未在本项目做全套基准；`low` 表示仅适合作候选试验。

## 当前结论

| 场景 | 首选 | 理由 |
| --- | --- | --- |
| 数据/统计图 | Matplotlib + Seaborn + constrained layout + adjustText | 数值、文字、尺寸和矢量输出可控，可在渲染后读取 artist 边界 |
| 正式流程/模型框架图 | D2 + ELK | 精确文本、自动布局、矢量导出和复现性平衡最好 |
| 快速可编辑流程图草稿 | Mermaid + ELK | 文本式源文件、快速、生态成熟；最终精细控制略弱于 D2 |
| 网络图 | NetworkX + Graphviz | 图结构与布局职责清晰，可复现 |
| 地图 | GeoPandas/Cartopy + Matplotlib | 投影、坐标和数值图层可审计 |
| 非数值概念示意候选 | engineering-figure-agent / imagegen | 视觉探索快，但文字和结构必须重建、复核 |

## 流行度参考（2026-08-31 快照）

热度只用于发现生态，不直接进入最终路由分。调研快照包括 Mermaid、D2、Matplotlib、Plotly.py、Seaborn、PlantUML、Altair、SciencePlots、PaperBanana、adjustText 和 ggrepel 等项目。星标会变化，应在需要发布新的“最受欢迎”结论时重新联网核验。

机制与文档入口：

- [Matplotlib constrained layout](https://matplotlib.org/stable/users/explain/axes/constrainedlayout_guide.html)
- [adjustText](https://github.com/Phlya/adjustText)
- [D2](https://github.com/terrastruct/d2)
- [Mermaid](https://github.com/mermaid-js/mermaid)
- [ELK layout](https://www.eclipse.org/elk/)
- [SciencePlots](https://github.com/garrettj403/SciencePlots)
- [PaperBanana](https://github.com/google/paperbanana)

