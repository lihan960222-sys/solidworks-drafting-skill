# SolidWorks Drafting Skill

独立新技能：保留用户认可的工程图模板，复用原生尺寸/已有 PMI，通过比例与视图/表格布局生成工程师审核草稿，交付目录只有 DWG 和从该 DWG 打印的 PDF。

安装：把此目录整体复制到 Codex 的 `skills/solidworks-drafting`，不要只复制 MD。运行环境与真实能力边界见 [SKILL.md](SKILL.md)。原工程图技能与迁移技能保留兼容；新包运行时不调用它们。

当前版本保留模板图框、标题栏、投影、字体和箭头设置；自动 DimXpert 方案、局部视图按用户决定延期，后续测试有需要再实现，不作为当前阶段验收条件。已有模型尺寸与已有 PMI 复用保留；必要定义超出后端支持时仍须报告缺项。最终字体、符号、视图和覆盖项必须实际复核。开发验证状态见 [verification.md](references/verification.md)，未通过项不会写成通过，草稿不等于制造放行。

尺寸选择以[几何定义完整性](references/geometric-definition.md)为准：图纸本身必须唯一确定名义形状、大小、位置、方向和深度，尺寸链完整且没有重复的驱动定义。先测量实际可导入尺寸，再按几何需要选择；导入数量不代表可制造性。允许明确推导得到的尺寸不重复标注；不能借源模型、隐含对称或看图估算补足缺项。`geometry_audit` 记录重建和去重证据，最终验收缺少此记录会失败；检查器不冒充通用几何重建求解器。公差与表面要求可按用户要求暂缓。

离线检查：`python -m unittest discover -s tests -v`。原生编译/验收入口：`tests/native-acceptance.ps1`。开发样件由 `tests/SampleParts.cs` 创建，用户图纸与参考 DWG 不随技能发布。

发布快照：**2026.10.07-rc2**。独立项目：[solidworks-drafting-skill](https://github.com/lihan960222-sys/solidworks-drafting-skill)。本次修复增加实际尺寸导入预检、按特征区分同名标注、隐藏特征选项及名义几何完整性/去重审核。实际回归证据和边界见 [verification.md](references/verification.md)；模块测试不替代完整图纸验收。

同系列独立项目：旧原生工程图 [solidworks-drawing-skill](https://github.com/lihan960222-sys/solidworks-drawing-skill)，通用自动化迁移 [solidworks-automation-port-skill](https://github.com/lihan960222-sys/solidworks-automation-port-skill)。
