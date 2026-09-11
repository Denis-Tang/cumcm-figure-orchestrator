# CUMCM 论文绘图总控 Skill

根据完整数学建模论文、数据与代码规划和制作图表，按图型选择渲染器，并检查数值、文字、布局、灰度、导出和来源证据。**V02 是唯一正式个人配色基线。**

## 安装与使用

下载 ZIP 或克隆仓库，将 `.agents/skills/cumcm-figure-orchestrator` 整个目录复制到你的项目 `.agents/skills/`，或个人 `~/.codex/skills/`。不要只复制 `SKILL.md`。重新开启 Codex 会话后调用：

```text
$cumcm-figure-orchestrator
请根据这份完整论文、数据和代码制作图表，使用默认配色，检查数值与版面，并交付可复现源码。
```

也可直接在本仓库工作。入口：`.agents/skills/cumcm-figure-orchestrator/SKILL.md`。论文、数据及结果存在冲突或缺失时，应报告受影响图表，不能补造研究结果。

## 唯一配色基线：V02

正式配色只读取：

- `.agents/skills/cumcm-figure-orchestrator/assets/personal-color-baseline.json`
- `.agents/skills/cumcm-figure-orchestrator/assets/personal-color-baseline-v02.json`

两者均以 `personal-cumcm-v02` 为基线。V02 六色：

- blue `#2389DA`
- coral `#D95B52`
- amber `#E5A33D`
- teal `#49A88D`
- violet `#8876AF`
- slate `#687D91`

简单图按科学语义优先使用 **blue + coral**，第三分类才使用 amber，第四色使用 violet，teal 最后使用。`slate` 是中性色，专用于基准、边界、reference 与次要上下文，不占分类色优先级。

柱条、环形等较大面积分类填充使用 V02 的 76% 原色 + 24% 白色；流程节点、箱线和语义背景使用 soft fills。默认白底，不使用无语义装饰背景。

完整规则见：

- `references/personal-color-baseline.md`
- `references/figure-style-contract.md`

## 竞赛论文图形规则

- 同级 panel 默认等权布局，不使用无科学理由的“大主图 + 小副图”结构。
- 单个 panel 优先接近 `1:1`、`4:3`、`16:9` 等常规比例；禁止无必要的极扁或极窄比例。
- 常规 Cartesian 数值图四边 spine 全部显示，默认只显示左侧和底部 ticks / tick labels；顶部、右侧不重复显示刻度。twin axis 或特殊坐标需求除外。
- 文字不仅不得重叠，还必须与数据实线、marker、柱边界和坐标框保持舒适净空。
- 只有本质连续、仅因采样离散的变量可以做形状保持平滑；分时电价、开关量、调度决策、整数/分段控制量必须保持阶梯、柱状或离散表达。
- 数值型正式图不得由图像生成模型承担精确几何、坐标、公式或标签。非数值概念示意图仍可使用 image generation 作为候选，正式使用前需重建和核验。

## 运行环境

建议 Python 3.11+，创建独立虚拟环境，然后安装基本依赖：

```text
python -m pip install -r requirements.txt
python .agents/skills/cumcm-figure-orchestrator/scripts/check_environment.py
python -B -m unittest discover -s tests -v
```

基础依赖支持数据图和核心验证；D2、Graphviz、R、地理库及其他 Agent Skills 按任务另行安装，未随仓库附带。Windows 的 D2 安装/渲染脚本依赖 PowerShell 与 Edge；其他平台须使用适合本机的渲染链。中文图需要本机可用的中文字体。依赖不足时由路由报告或选择满足约束的备选。

## 示例与验证边界

`examples/paper-plan.json` 是规划/回归夹具，引用的是占位路径，不是可直接验收的论文。`python .agents/skills/cumcm-figure-orchestrator/scripts/demo_batch.py --out outputs/demo` 可生成合成验收批次；视觉检查仍需实际执行。不得将测试中的模拟审查证据复制到正式论文。

自动检查不保证论文推导正确。参赛前需核对当年赛区格式及 AI 使用要求。

尚未完成多篇完整论文的端到端评测。自动化检查不替代最终尺寸图件审阅。
