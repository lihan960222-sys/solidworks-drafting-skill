# SolidWorks Drafting Skill

独立新技能：保留用户认可的工程图模板，复用原生尺寸/已有 PMI，通过比例与视图/表格布局生成工程师审核草稿，交付目录只有 DWG 和从该 DWG 打印的 PDF。

安装：把此目录整体复制到 Codex 的 `skills/solidworks-drafting`，不要只复制 MD。运行环境与真实能力边界见 [SKILL.md](SKILL.md)。原工程图技能与迁移技能保留兼容；新包运行时不调用它们。

当前版本保留模板图框、标题栏、投影、字体和箭头设置；自动 DimXpert 方案、局部视图按用户决定延期，后续测试有需要再实现，不作为当前阶段验收条件。已有模型尺寸与已有 PMI 复用保留；必要定义超出后端支持时仍须报告缺项。最终字体、符号、视图和覆盖项必须实际复核。开发验证状态见 [verification.md](references/verification.md)，未通过项不会写成通过，草稿不等于制造放行。

离线检查：`python -m unittest discover -s tests -v`。原生编译/验收入口：`tests/native-acceptance.ps1`。开发样件由 `tests/SampleParts.cs` 创建，用户图纸与参考 DWG 不随技能发布。

发布快照：**2026.10.07-rc1**。独立项目：[solidworks-drafting-skill](https://github.com/lihan960222-sys/solidworks-drafting-skill)。本次拆分与版本更新保留既有代码和能力边界；实机测试证据仍为 2026-10-06，不将重新发布当作新增原生验收。

同系列独立项目：旧原生工程图 [solidworks-drawing-skill](https://github.com/lihan960222-sys/solidworks-drawing-skill)，通用自动化迁移 [solidworks-automation-port-skill](https://github.com/lihan960222-sys/solidworks-automation-port-skill)。
