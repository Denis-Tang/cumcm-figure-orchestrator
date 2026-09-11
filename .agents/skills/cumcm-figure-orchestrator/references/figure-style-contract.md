# Figure Style Contract

本文件定义 CUMCM 正式图件的结构、美观与科学表达约束。它补充数值/来源验证，不替代模型、统计或赛区规则。

## 1. Panel geometry

同一逻辑层级的 panel 默认等权：

- 优先规则网格：`1×2`、`2×1`、`2×2`、`3×1`、`4×2` 等。
- 不通过“一个特别大、其他特别小”的尺寸差异制造主次关系。
- 主次优先写在总图名、panel title、caption 或正文解释里。
- 单 panel 尽量使用常规比例，优先接近 `1:1`、`4:3`、`16:9`。
- 允许按数据密度灵活调整，但 `5:1`、`1:4` 等异常比例需要明确理由并在 QA 中人工确认。
- colorbar、极坐标、地图、网络图等专用附属 axes 不参与普通 panel 等权比较。

## 2. Closed Cartesian frame

常规 Cartesian 数值图默认四边封闭：

- `left`, `bottom`, `top`, `right` spine 全部可见；
- 默认只显示 left/bottom ticks 与 tick labels；
- top/right ticks 与 labels 默认关闭；
- `twinx()` / `twiny()` 或特殊坐标需要时可启用对应 ticks；
- twin axes 叠加后最终视觉上只应呈现一套干净的封闭矩形框，避免重复加粗。

非 Cartesian 图（流程图、网络拓扑、地图、极坐标、Sankey 等）不机械套矩形框。

## 3. Semantic smoothing

“看起来锯齿”不是平滑的充分理由。先判断变量在采样点之间是否具有连续科学含义。

### 允许考虑平滑

- 负载预测；
- 光伏/风电连续功率预测；
- 温度、连续传感器量；
- 某些连续状态量。

要求：

- 原始样本不改；
- 平滑曲线穿过原采样值；
- 使用 shape-preserving 方法（例如 PCHIP）；
- 不产生无数据依据的 overshoot、新峰值或新谷值；
- 只改变 presentation，不改变统计量和模型输入输出。

### 禁止平滑

- 分时电价；
- 开关量；
- 整数决策；
- 时段调度功率；
- 充/放电控制；
- 分段政策；
- 事件计数；
- 其他本质离散或 piecewise-constant 变量。

上述量使用 `step`、`stairs`、bar 或离散 marker。

## 4. Text clearance

目标不是“bbox 没相交”，而是保持优雅净空：

- 文字不得接触任何数据实线；
- annotation 不得骑在 marker、柱边界、reference line 或坐标框上；
- 标题、panel 标签和顶部图例必须与 top spine 留出肉眼可辨的间距；
- 图例不得覆盖关键数据；
- 优先移动文字或增加 offset；
- 必要时可以使用轻量白底 annotation，但不得大面积遮挡数据。

最终尺寸 PNG 人工复核是强制步骤。自动检测只能作为证据之一。

## 5. V02 color discipline

读取 `personal-color-baseline.md`：

- 简单图优先 blue + coral；
- 第三分类 amber；
- 第四分类 violet；
- teal 最后使用；
- slate 专职中性 reference；
- 大面积和 soft fill 使用 V02 指定浅色，不为了“丰富”额外加色。

## 6. Final-size QA

至少检查：

1. 四边 spine 是否完整；
2. top/right ticks 是否在无理由情况下被打开；
3. 同级 panel 是否面积接近、比例正常；
4. 文字是否与线、marker、柱、spine 保持净空；
5. 图例是否侵占数据区域；
6. 平滑是否只用于连续变量且没有造峰；
7. 离散量是否仍保持阶梯/柱状语义；
8. 灰度下是否仍可区分；
9. PDF/PNG 是否裁切；
10. 最终插入论文后的字号和视觉密度是否合适。

## Matplotlib 自动检查接入

绘图完成后在最终物理尺寸调用 `apply_closed_cartesian_style` 和 `run_style_qa`。普通 twin 用 `apply_closed_cartesian_style(twin, right_ticks=True, frame_owner=primary)`，再将 twin 索引传给 `twin_or_special_tick_axes`；twiny 对应 top_ticks=True。frame_owner 负责唯一外框。

色条、axis-off 和非 Cartesian 投影自动排除；使用普通 rectilinear axes 的地图/流程/网络须调用 `set_style_role(ax, "map"/"flowchart"/"network", reason="具体理由")`，排除理由会写进结果。peer_groups 显式声明同级数据 panel。比例阈值可通过 check_panel_aspect_ratios 参数调整，科学例外需记录理由与最终视觉复核。

净空采用渲染后的线段与扩展文字框相交检查，覆盖 ax.text/Annotation 和 panel title 与 Line2D；文字框不包括 annotation 的引导箭头。默认 clearance_px=6，调用方应按最终 DPI 换算期望间距（例如 2pt × dpi/72）。该筛查不完整覆盖 marker、柱边界、spine、图例以及复杂裁剪路径，这些必须另作最终 PNG 目视检查，不能把自动通过称作全量净空通过。

将 style QA 原始报告纳入 collision_check 的结果（任何 error 导致 fail），warnings 必须在 visual_review 中说明处理；将 style helper、配色配置和绘图源码纳入 input_files 以绑定哈希。不要只生成未参与交付验收的独立报告。语义平滑须记录插值方法、连续性依据与原样本，禁止跨缺失区间自动连接；外推默认禁止。
