# Developer figure style v2

色值由 `assets/personal-color-baseline.json` 管理（V02 单基准，不做版本切换）；选择策略、坐标轴、布局、线条与 QA 参数由 `assets/personal-figure-style.json` 管理，加载器按 `profile_id` 与 `baseline_id` 记录本次策略。

## 配色决策与 renderer 接口

科学准确性 > 可读性 > 可复现性 > 个人美学。不能改数据、单位、时间索引、统计口径、轴变换、必要标签或结论来满足视觉规则。

分类色默认顺序 blue、coral、amber、violet、teal（先红蓝、再橙、再紫、最后绿），各角色的默认用途与「按类别数取色」的完整阶梯见 `personal-color-baseline.md`；一个强调对象可选 blue 或 coral。slate 用于参考/中性/边界，不自动补成第六分类。超过五类先评估 marker、hatch、线型或分面；不要循环色序造成歧义，也不要删除必要系列。颜色不自行代表好坏、安全或风险。已有跨图对象映射优先；科学语义和用户当次覆盖可提前用绿色等，但须记录 reason。连续 colormap 仍独立按科学语义选择。

```python
from figure_style import load_style, select_colors, matplotlib_style, declare_continuity
profile, palette = load_style()
mapping = select_colors(['control', 'experiment'], existing=batch_object_mapping,
                        profile=profile, palette=palette)
with plt.rc_context(matplotlib_style(profile, palette)):
    # lines/points/edges: mapping[id]['colors']
    # bars/donuts: mapping[id]['large_area_fills'], alpha=1
    # boxes/flow nodes: mapping[id]['soft_fills'] + original edge
    line, = ax.plot(x, y)
    declarations = declare_continuity(line, 'continuous', name='response_curve')  # merge into style_policy
```

持久化完整批次对象映射，调用方将新返回记录合并回批次表；不要只保存最后一张图的子集。Matplotlib cycle 只辅助初始化；正式多系列图显式使用 mapping，避免默认 cycle 超量后循环。每个 renderer 都须接收相同 profile、palette、对象映射和理由；D2/SVG/R 等直接读取 JSON，由自身几何测量或人工检查执行同等规则，不能声称 Matplotlib 检查了其他 renderer。

## 坐标轴：四周封闭

直角坐标数据图必须四边 spine 全部可见，形成闭合边框。禁止只保留左边和底边的开放式坐标轴。

- 刻度与刻度标签默认只在左边和底边（`xtick.top=false`、`ytick.right=false`）。顶边、右边是否补刻度或镜像标签按图型决定，例如上下对齐读数的宽幅时间序列、双 x 轴、需要四边读数的矩阵图；**无论是否加刻度，边框线都必须闭合**。
- 顶/右刻度属于「按具体情况决定」，因此**默认关闭，要开必须写明理由**：在 `style_policy.tick_side_justifications` 按 panel 标签记录，否则 `axes_frame_closed` 判失败。twin 轴叠加后视觉上只应呈现一套干净的封闭矩形框，避免重复加粗边框。
- 不适用（记为 `skipped`，不计失败）：极坐标、3D、地图/投影坐标（cartopy、geo 等）、`axison=False` 的无坐标轴概念图、colorbar 轴。
- `matplotlib_style()` 已把 `axes.spines.{left,right,top,bottom}` 设为可见。不要再用 `ax.spines[[...]].set_visible(False)`；确需例外（如与相邻子图共边拼版）必须在 `style_policy.frame_exemptions` 按 panel 标签写明原因。若某个 renderer 或第三方代码在事后重置了 spine/刻度，用 `figure_style.apply_closed_cartesian_style(ax)` 重新套用（共享 x 轴网格只在外圈子图显示标签时传 `labels=False`）。
- 自动检查 `axes_frame_closed` 在最终尺寸下逐个 axes 读取 spine 可见性与实际刻度边，并区分「边框未闭合」和「顶/右刻度无理由开启」两类失败。

## 组图子图长宽比

同一 figure 内存在两个及以上数据 axes 时，**每个子图绘图区**（axes bbox，不含标签留白）的宽高比必须落在白名单内：`1:1`、`4:3`、`16:9`，容差 ±2%。

- 允许倒数镜像（`3:4`、`9:16`）用于纵向排布；由 `panel_aspect_allow_reciprocal` 控制。
- 禁止细长条、极扁或极窄的子图。比例的具体选择按数据密度和阅读方向决定，但必须命中白名单。
- 推荐用 `ax.set_box_aspect(3/4)` 精确锁定 4:3 绘图区（该参数是**高/宽**，不要写反），而不是反复调 figsize 试凑。
- 单子图不适用（检查结果 `applies=false`，并说明原因）。地图、inset、双轴等确需不同比例时，在 `style_policy.layout_justifications` 按 panel 标签或 group 名写明原因。
- 自动检查 `panel_aspect_whitelist` 与 `panel_size_uniformity` 互补：前者管形状是否正常，后者管同级子图是否等大。

## 线条连续性与平滑

每条可见实线数据线必须通过 `line.set_gid(...)` 命名，并在 `style_policy.continuity_declarations` 中声明以下四类之一。

| 声明 | 适用 | 要求 |
|---|---|---|
| `continuous` | 连续量（默认） | 必须平滑绘制：密集采样或解析求值，不得把少量原始点直接连成粗折线；**必须同时声明原始数据的 `y_range`** |
| `discrete` | 离散点、不连续量 | 保持原始采样点，禁止插值加密；**必须声明原始 `sample_count`** |
| `step` | 阶梯、分段常数 | 使用 `drawstyle="steps-*"` |
| `piecewise_linear` | 确有真实折点的连续量 | 保留折点，须记录理由；**必须声明原始 `sample_count`** |

声明写法：短式 `{"latch": "step"}`，或完整对象 `{"response_curve": {"kind": "continuous", "y_range": [0, 8], "x_range": [0, 24], "turning_points": 1}, "observed_span": {"kind": "discrete", "sample_count": 6}}`。`y_range` 与 `sample_count` 取**原始数据**的极值和点数，不是平滑后曲线的；`turning_points` 为原始数据的转折点个数，可选。推荐用 `figure_style.declare_continuity()` 生成这些记录。

### 语义门控：先判断变量含义，再决定画法

「看起来有锯齿」**不是**平滑的充分理由。先判断这个量在两个采样点之间有没有连续的科学含义。

**允许考虑平滑**（连续量）：

- 负载预测；
- 光伏、风电等连续功率预测；
- 温度、连续传感器读数；
- 其他确有连续物理含义的状态量。

**禁止平滑**（本质离散或分段常数）：

- 分时电价；
- 开关量；
- 整数决策；
- 时段调度功率；
- 充放电控制；
- 分段政策；
- 事件计数。

上面这些量用 `step`、`stairs`、柱状或离散 marker 表达，不要为了好看硬掰成曲线。稀疏且噪声大的实测序列也不要强行平滑以掩盖离散性，应改用点+线、误差带或分面表达。

允许平滑时仍须满足：原始样本不改、平滑曲线穿过原采样值、优先 shape-preserving 方法（例如 PCHIP）、不产生无数据依据的 overshoot/新峰值/新谷值、只改变 presentation 而不改变统计量与模型输入输出。

- 平滑方式按图选择并在 manifest 记录，规范只约束结果：`continuous` 曲线须满足采样密度下限（默认 ≥24 点，或为严格直线）、相邻长线段之间不得出现超过 12° 的硬转角、不得越出 `y_range`/`x_range` 声明的原始数据包络、转折点不得超过原始数据。
- 硬约束不因平滑而放宽：平滑后的曲线必须过原始数据点；不得为外观修改数据、单位、区间或结论；`data_contract` 的 reference/plotted 数据仍是原始值，平滑只发生在视觉层。
- 轴向参考线（`axhline`/`axvline` 等两点轴对齐直线）自动跳过；对角参考线、理论边界线按 `piecewise_linear` 声明。
- 自动检查 `curve_smoothing` 逐线核对声明与渲染路径几何；缺声明、缺包络、粗折线、过冲、虚构极值、被插值篡改的离散线都会判失败。

## 同级 panel 与安全距离

优先 1×2、2×1、3×1、2×2、4×2 等等宽等高网格，并同时满足上面的长宽比白名单。final-size draw 后 plotting area 的 max/min−1 默认不超过 2%，宽高分别验收。`panel_groups` 显式分组必须覆盖每个可见非 colorbar axes；默认全部为同级。地图/inset/双轴等结构需科学分组或 `layout_justifications={group: reason}`，将分组与原因写入 style_policy 和 QA evidence。不同组也不能仅为规避检查而拆分。

`inspect_figure_layout` 输出 collision/clipping 字段和六个带对象/距离/测量的检查：

- `panel_size_uniformity`：真实 plot 区宽高，保留超差值及例外原因。
- `text_solid_stroke_clearance`：文字 bbox 到变换后的实线段/曲线折线化路径距离减半线宽，换算 pt；接触/交叉硬失败，未接触但小于 4 pt 也失败。覆盖标题、tick/axis label、注释、数值、legend 和 figure text，以及折线、reference、patch 轮廓、spine、collection 边和 marker。虚线/点线网格不当作实线。
- `legend_data_region_clearance`：整块图例到数据路径/marker 的间距，默认 4 pt；图例自带 handle/frame 不当作外部数据。
- `axes_frame_closed`：逐 axes 的四边 spine 可见性、实际刻度边，以及顶/右刻度是否有理由记录。
- `panel_aspect_whitelist`：逐 axes 绘图区宽高比、最近白名单比例与偏差。
- `curve_smoothing`：逐线声明类型、采样点数、最大转角、值域与极值对比。

默认 tick pad 6 pt、axis label pad 9 pt、title pad 12 pt，辅助网格低对比点线。注释冲突先移动文字、改 offset/对齐、用 adjustText，必要才用克制 bbox/halo；不得省略必要标签。文字自己的 bbox/annotation leader、图例自己的 handle/frame 是结构关系豁免；与任何其他实线的接触不能通过 `ignored_artists` 或 exemption 隐藏。非接触的小间距仅可用 `(text, stroke, reason)` 成对例外，证据保留实际距离。

## 两层 QA 与证据

新生产图设置 `style_policy`（profile_id、baseline_id、input_files，另可记录 object_mapping、panel_groups、layout_justifications、frame_exemptions、tick_side_justifications、continuity_declarations、overrides）。input_files 至少绑定实际 profile、palette、style helper 和 layout QA 源码；严格验收新增六项 QA 的真实、当前证据，沿用 qa_evidence 哈希绑定。无 style_policy 的历史 v2 保持兼容，不伪装已完成新风格验收。

程序化 QA 后，将最终 PDF/矢量图按最终物理尺寸 rasterize 到至少 300 dpi，检查彩色和灰度：文字贴线、图例遮挡、标题压图、等尺寸与长宽比视觉效果、边框闭合、留白和字体。生成器默认 visual_review pending；实际看过图后才记录 Agent/人工身份、源矢量图、栅格图、最终尺寸及观察。失败继续改图，输出变化后重做绑定。现有数值、裁切、导出、claim/caption、语义、来源和 AI disclosure 不变。

## 已知边界

这是保守的 bbox/path 几何筛查，不是 glyph 轮廓或最终渲染像素的证明；曲线折线化存在近似。`curve_smoothing` 用转角与采样密度近似"看起来是否平滑"，无法证明插值方法在科学上合适，也不能替代对数据语义的判断；`axes_frame_closed` 只证明 spine 被绘制，不证明边框遮挡了数据。当前处理矩形 clip box；非矩形 clipping、复杂投影/3D、自定义 artist、透明遮挡和 halo 的视觉效果必须补充专项/视觉证据。图例内部 handle/frame 间距仍须视觉检查。scatter collection 按 marker 几何检查，密集图开销随文字数和路径数增加。最终 PDF 字体/嵌入缩放仍以重新栅格化图为准。
