# Skill-level scorecard

Skill 负责理解、设计和审查，renderer 负责生成最终资产。两层必须分开打分，否则会把“会给好建议”误当成“能输出可复现矢量图”。以下为 2026-08-31 基线，0–10 分；详细维度见 `assets/skill-scorecard.json`。

| Skill | 数据图 | 流程图 | 概念视觉 | 正式成图资格 | 当前定位 |
| --- | ---: | ---: | ---: | --- | --- |
| `data-analytics:visualize-data` | 9.8 | 4.0 | 4.0 | 需配确定性 renderer | 数据语义、图型选择和视觉 QA 首选 |
| `engineering-figure-agent` | 7.5 | 7.5 | 9.2 | plot 模式可用；image 模式仅候选 | 当前已安装的概念图/混合图首选 |
| `imagegen` | 0.0 | 4.0 | 9.5 | 否 | 自由概念视觉探索最好，精确文字/数值不合格 |
| `visualize:visualize` | 8.8 | 6.0 | 6.0 | 否 | 交互探索和解释，不作为静态论文图默认终点 |
| K-Dense `scientific-visualization` | 9.5 | 5.0 | 5.0 | 可，但本机未安装 | 开源出版图规则与导出 QA 强 |
| PaperBanana | 2.0 | 5.5 | 9.2 | 否 | 概念图候选；可靠统计图尚不作为完成能力 |

流程图的最终首选不是某个生成式 Skill，而是本总控直接生成结构化 D2 源码并交给 D2+ELK。这让准确文字、连线含义、矢量输出和重跑能力都能接受审计。

