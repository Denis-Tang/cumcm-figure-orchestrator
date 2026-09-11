# 仓库绘图入口

绘图前必须读取 `.agents/skills/cumcm-figure-orchestrator/SKILL.md`，以及其中引用的配色、风格与生产契约。该目录必须完整保留。

所有使用者默认应用 V02、四边封闭坐标轴、组图绘图区比例白名单、同级面板等大、文字与无关实线至少 4 pt 净空、图例避让和按科学语义处理的平滑曲线。以 JSON 的实际参数和 Skill 的适用范围、例外为准；用户当次要求与科学准确性优先。

不得只阅读 README 后采用渲染器默认样式。下游渲染器必须收到相同配置、对象颜色映射及例外原因。实际渲染、检查并修复图件，交付可复现源码。自动检查不代替最终彩色与灰度图视觉审查，不能编造验证记录。

使用 `requirements.txt` 安装基础依赖；运行 `python -B -m unittest discover -s tests -v` 验证。完整合成示例为 Skill 的 `scripts/demo_batch.py`；选择全新输出目录，视觉审查在实际执行前保持 pending。
