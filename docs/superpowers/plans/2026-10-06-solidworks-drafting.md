# 独立 SOLIDWORKS 制造图 skill 执行计划

2026-10-07 发布位置更新：本技能已拆分至独立 `solidworks-drafting-skill` 仓库，仓库根目录即安装包。下文 `skills/solidworks-drafting/` 是初始整合时期的路径记录；当前相应资源在根目录。自动 DimXpert 方案和局部视图按用户决定延期。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 本计划默认在当前会话串行实施，CAD 会话始终只有一个驱动。

**Goal:** 将旧工程图与迁移自动化代码整合成独立 `solidworks-drafting` skill，生成可审核的单页工程图，只交付 DWG 和 PDF，允许表格及混合标注。

**最新范围修正：** 自动 DimXpert 方案、局部视图延期，作为用户后续测试后再决定的待改进项，不作为当前阶段验收条件。保留已有模型尺寸和已有 PMI 复用。以下相应任务属于后续候选方案；遇到当前后端无法完整表达的具体零件仍报告缺项，不默默漏标。

**Architecture:** 新包自带说明、契约、配置、PowerShell/C#/Python 和测试，复用两套旧技能的可用代码，运行时不依赖旧包。SOLIDWORKS 完成内部原生视图、尺寸与排版；导出 DWG 后独立回读该 DWG 生成 PDF。统一串行工作进程、特征覆盖数据和阶段报告。

**Tech Stack:** Windows PowerShell 5.1、隐藏 STA 工作进程、SOLIDWORKS 官方 COM/.NET interop、Python 3.9+ 标准库；PDF 内容检查/必要合成使用 pypdf，视觉检查使用已有可用的 PDF 查看或渲染工具。不新增独立 CAD 软件依赖。

**Spec:** [设计依据](../specs/2026-10-06-solidworks-drafting-design.md)。此计划取代早期“旧 skill 作为统一入口、交付 PNG”的方案；新增功能尚未实现，步骤中的验收不能预先标记通过。

## 全局约束

- 新包：`skills/solidworks-drafting/`，包括 MD 和代码；不是路由器或仅有说明的包装。
- 首期：一次一个已保存、无未保存修改的原生 SLDPRT；不实现装配、批处理和 STEP 通用识别。
- 最终 `deliverables/` 只有 `.dwg`、`.pdf`；其他文件进入 `internal/`，不新增 PNG 出图功能。
- 严格单张 A4/A3/A2，可横纵向；无法完整且可读地放下则失败，不增加页数或缩小字号。
- 投影跟随模板，核对标识、视图位置和对齐；关联正投影视图统一比例。
- 常规标注、表格或混合表达均可；不再执行全面禁止表格规则。
- 不猜公差、功能基准、螺纹等级、材料和粗糙度；DimXpert 自动方案必须有明确制造规则。
- 保持源件完整，工作副本重新检查引用；超时为未知状态，先检查，不自动重跑，不结束 SOLIDWORKS。
- DWG 与 PDF 的内容检查及视觉检查通过后才标 `DRAFT_VERIFIED`，始终不等于生产放行。
- 只同步通用代码、文档、配置和合成测试，不上传用户 CAD、参考 DWG、真实图纸或原始尺寸数据。

## 首先核对的失败条件

1. 未保存/已修改源件、非目标配置、上次中断：保留用户现场，禁止覆写或重复操作；任务 2/8 验证。
2. DWG 回读改变纸幅/单位/比例、丢中文字/符号/表格：阻止成功，PDF不能换成原生图直接导出冒充；任务 3 验证。
3. 密集孔群及模型尺寸不全：尺寸计数不等于覆盖；表格必须有标识、单位、坐标系及来源；任务 5/6 验证。
4. 镜像/旋转方向、第一角与第三角、标题栏遮挡：按模板真实投影关系布局，禁止固定坐标套用；任务 4/7 验证。
5. A2 仍拥挤或必要局部视图无法创建：返回失败与具体缺项，禁止漏标、缩字和加页；任务 6/7/8 验证。

## 文件组织与接口

以下为计划创建的文件，尚不是已发布接口。

```text
skills/solidworks-drafting/
  SKILL.md                         新技能触发、完整流程及实际能力边界
  README.md                        安装、调用、依赖和交付说明
  agents/openai.yaml               新技能元数据
  references/plan-contract.md      v2计划、单位、来源与错误规则
  references/layout-reference.md   实际参考图归纳与来源
  references/verification.md      原生/DWG/PDF/覆盖验收
  configs/layout-profiles.json     板、轴、支架及A4/A3/A2规则
  examples/request.template.json   去除个人路径的输入示例
  scripts/run.ps1                  检查/执行/验证入口、锁及阶段编排
  scripts/worker.ps1               隐藏STA工作进程与结果落盘
  scripts/src/                     C#原生操作及内部复用代码
  scripts/planner.py               视图/图幅/比例候选和布局选择
  scripts/validate_plan.py         v2契约及覆盖校验
  scripts/verify_outputs.py        输出身份、PDF页数/纸幅/内容检查
  tests/                          合成离线回归与原生验收操作
  SNAPSHOT.json                    包内文件摘要及来源基线
```

旧来源为仓库根目录 `scripts/`；迁移来源为本地 `solidworks-automation-port/skill/solidworks-automation-port/scripts/`。将真正使用的通用代码放入新包；保留来源说明及原行为验收，不复制示例零件或无关装配/建模功能。不通过个人机器绝对路径引用旧 skill。

共同数据边界：

- `Inspect(source, configuration) -> FactsV2`：身份/摘要、配置、几何/边证据、特征、尺寸及 PMI 清单。
- `candidate_layouts(facts, view_requests, profiles) -> list[LayoutCandidate]`：纸幅、比例、位置、预计标注空间；不把预计边界当作真实无碰撞证明。
- `validate(plan, facts) -> ValidationResult`：必须在 COM 修改前通过；覆盖清单包含证据和应表达项。
- `Execute(planPath, reportPath) -> StageReport`：串行原生操作，输出实际结果、未支持项和内部文件。
- `ExportDwgAndPdf(nativeDrawing, outputDwg, outputPdf, exportOptions) -> ExportReport`：必须从实际 DWG 独立回读生成 PDF。
- `verify_outputs(report, coverage) -> VerificationResult`：区分 `FAILED/UNKNOWN/REVIEW_REQUIRED/DRAFT_VERIFIED`，每个检查保留证据。

## 任务 1：修正旧仓库，固定新设计基线

**文件：** 修改根目录 `README.md`、`SKILL.md`、`references/plan-contract.md`、`references/native-layout.md`、`references/pdf-font-repair.md`、`SNAPSHOT.json`；新增本计划和对应设计/一句话说明。

**产物：** 旧 skill 允许表格；明确 v1 仅支持 `nominal_hole_schedule`，独立 layout 不建表。新技能目标单独记录，不能混称已实现。

- [x] 移除五份文档中的全面禁止表格规则，补充标识、单位、坐标系、完整字段及验收条件。
- [x] 运行现有 `python -m unittest discover -s tests -v`；七项离线测试通过。
- [x] 进行修改前后独立行为检查：密集孔群允许表格/混合表达，且不虚报其他表格 role 已支持。
- [x] 更新 SNAPSHOT 摘要，核对运行时代码摘要未改变；验证 Markdown 路径、技能 frontmatter 和差异。
- [x] 同步正确仓库 `lihan960222-sys/solidworks-drawing-skill`；将早期 cad-agent 文档标记为被本设计取代。本机旧技能配置同步为新包目标及仅 DWG/PDF 交付。

## 任务 2：建立独立可执行包与统一会话入口

**文件：** 新包 `SKILL.md`、`README.md`、`agents/openai.yaml`、`scripts/run.ps1`、`scripts/worker.ps1`、`scripts/src/`、`references/plan-contract.md`、`tests/test_contract.py`、`tests/test_worker.ps1`。

**接口：** `run.ps1 -Mode Inspect -Source <SLDPRT> -Configuration <name> -Output <facts.json>`；`-Mode Execute -Plan <plan.json> -Output <report.json>`；`-Mode Verify -Plan <plan.json> -Output <new-report.json>`。可显式指定 `-InteropPath` 和 `-TimeoutSeconds`；所有结果路径绝对且不得已存在。v2 原生与交付路径由运行目录派生，不能由参考图数据指定。

- [ ] 先写并运行失败用例：已有输出/源件修改拒绝；两个工作进程不能同时获得同一锁；超时报告 `UNKNOWN` 且不结束 CAD、不自动重试。
- [ ] 复制旧几何/视图/关联尺寸及校验基础，在新包内封装；提取迁移的会话锁、隐藏 STA、超时处理和尺寸导入。COM 修改只从此入口进入。
- [ ] 以新包路径独立编译执行 Inspect；移开两套旧 skill 仍可运行。未知 v2 字段、PNG输出配置、额外页数及 A2 以上图幅必须被拒绝。
- [ ] 运行 `python -m unittest discover -s skills/solidworks-drafting/tests -v` 及 `powershell.exe -NoProfile -File skills/solidworks-drafting/tests/test_worker.ps1`，确认失败保护与独立运行通过；提交包基线。

## 任务 3：先打通 DWG → 独立回读 → PDF

**文件：** `scripts/src/NativeExport.cs`、`scripts/verify_outputs.py`、`references/verification.md`、`tests/test_outputs.py`、`tests/native-acceptance.ps1`。

**接口：** `ExportDwgAndPdf(...) -> ExportReport`，报告包含源原生图摘要、DWG摘要、回读选项、回读文档身份、PDF来源DWG摘要、实际页面/单位/比例、错误/警告、文字/表格比对与设置恢复结果。

- [ ] 离线用例先断言：两页 PDF、A3 图框误成 A4、缺失直径/角度/中文、表格漏行及 PDF来源摘要不符均不通过。真实 CAD 用例包含特殊符号、文字、关联尺寸、表格和剖面。
- [ ] 使用已安装 interop 和官方帮助核实导出/导入具体参数；先用自建简单样件验证。快照/恢复会影响结果的导出选项；显式固定页面、单位、纸空间及比例。
- [ ] 从新 DWG 的独立导入文档生成 PDF，保留中间文件于 internal/。采用原生 Print/SaveAs 合成时仍须来源于该回读文档，不能使用原始图纸的通道。
- [ ] 核对内容、字体符号、单位/比例、PDF单页纸幅及DWG真实回读；失败则停止该路线并记录证据，不能继续宣称整体功能完成。
- [ ] 运行 outputs 离线测试和 `native-acceptance.ps1 -Case ExportRoundTrip -OutputDirectory <new-dir>`；保存本机验证结论到说明，提交通用实现。

**关口：** 此任务未通过，不进入新技能的最终自动出图验收；先解决转换路线。

## 任务 4：参考图归纳、模板配置与初始布局候选

**文件：** `references/layout-reference.md`、`configs/layout-profiles.json`、`scripts/planner.py`、`tests/test_planner.py`。

**接口：** `candidate_layouts(...)` 输入实际模型投影范围、必要视图请求、尺寸/表格空间和模板配置。配置包含 `family`、`projection`、纸幅/绘图区/禁入区、关联方向、字号/箭头/线型/间距、有限比例候选及本地模板路径参数。

- [ ] 先测试：第三角俯视在上/右视在右，第一角俯视在下/右视在左；相关视图统一比例；全部边界和预留空间不入标题栏。纵向与横向长零件得到不同可行候选。
- [ ] 从用户网站实际查看板/轴/支架类适用参考图；记录来源、采纳/不采纳理由和排版归纳。样图数量服从是否覆盖三类需求，不下载全库、不复制几何数值。
- [ ] 采用实际本地 drwdot 副本建立 A4/A3/A2 配置，检查模板投影信息；缺少可信标识时配置需补齐并验证。商业模板不发布。
- [ ] 实现有限候选搜索与可行性预筛；没有候选返回明确失败，不能默认缩文字。运行 planner 测试，并在原生预览中验证一角/三角及横纵向；提交规则和通用归纳。

## 任务 5：完整特征、尺寸与 PMI 清单及受控导入

**文件：** `scripts/src/NativeInspection.cs`、`scripts/src/NativeAnnotations.cs`、`references/plan-contract.md`、`tests/test_coverage.py`、`tests/native-acceptance.ps1`。

**接口：** `Inspect(...) -> FactsV2`；`ImportModelDimensions(document, options) -> AnnotationResult`；`ImportExistingPmi(view, options) -> AnnotationResult`；`ApplyDimensionScheme(workingCopy, explicitRules) -> AnnotationResult`。返回实际对象身份/类型/实体证据/值/来源，不仅是数量。

- [ ] 覆盖测试先断言：相同数值不同实体不能去重；重复遍历同一对象要去重；漏掉孔深或槽宽则为 `missing_geometry_definition`；只有未知公差进入制造规格待补项。
- [ ] 递归特征和子特征枚举全部可读取模型尺寸，结合几何/孔向导信息建立外形、孔、槽、台阶、圆角和倒角清单；无法可靠识别的特征明确记为待处理。
- [ ] 使用迁移尺寸导入逻辑并分别核对 marked/unmarked 清单；DimXpert用独立 ImportAnnotations 入口，不混用开关。按实体/含义/方向筛选和去重。
- [ ] 在工作副本验证有明确规则的 Auto Dimension Scheme；无规则不调用。重新检查引用、源件摘要和副本几何。接口不可用/许可不支持时报告具体不支持，不能猜制造数据。
- [ ] 运行 coverage 测试及原生 PMI/模型尺寸验收，核对实际尺寸值、关联和来源；提交被真实验证的操作，并同步能力说明。

## 任务 6：必要视图、尺寸补齐与表格混合表达

**文件：** `scripts/src/NativeViews.cs`、`scripts/src/NativeAnnotations.cs`、`scripts/validate_plan.py`、`tests/test_coverage.py`、`tests/test_tables.py`、`tests/native-acceptance.ps1`。

**接口：** `CreateRequiredViews(plan, facts) -> ViewResult`；`CreateFeatureDefinition(definition, facts) -> AnnotationResult`。定义项含唯一 `id`、特征及实体引用、含义、单位、期望值、目标视图或表格行；返回实际创建对象及验证结果。

- [ ] 先测试表格与视图映射：缺编号、重复编号、无单位/坐标原点/轴向、行来源不符、缺必要孔深均失败；表格与图上尺寸矛盾不能通过。
- [ ] 复用标准/反向/直线完整剖视，添加并真实验证必要的局部视图操作；未支持的截面或尺寸形式必须显式失败，不能漏项或生成伪视图。
- [ ] 逐类补齐外形、台阶、槽、孔径/位置/深度、圆角和倒角。先核实目标原生API再封装；优先关联尺寸，必须用字面说明/通用表时记录非关联属性及测量证据。
- [ ] 扩展新 v2 表格角色 `nominal_hole_schedule`、`nominal_feature_schedule`，按来源定义数据生成行，校验适用必需字段。允许规则选择常规/表格/混合方式，不使用任意自由文本表绕过覆盖检查。
- [ ] 运行 table/coverage 离线测试；用含盲孔/贯穿孔/槽/圆角/倒角及局部视图的合成样件验证真实对象、数值和保存重开。提交通过的能力，保留未通过项。

## 任务 7：动态排版反馈与真实图纸验证

**文件：** `scripts/src/NativeLayout.cs`、`scripts/planner.py`、`scripts/validate_plan.py`、`scripts/src/NativeVerification.cs`、`tests/test_planner.py`、`tests/test_layout.py`。

**接口：** `MeasureLayout(document) -> LayoutObservation`；`RepairLayout(document, candidate, observation) -> LayoutObservation`；`VerifyNative(plan, baseline) -> NativeVerificationResult`。观察包括实际视图范围、可量测文字/箭头/引线/表格、悬空、重叠及未量测项。

- [ ] 先测试标题栏禁入、尺寸层碰撞、拥挤表格和 A2 仍不能容纳完整图；必须失败，不得加页、缩字或删除定义。保存重开文字/尺寸/行丢失必须失败。
- [ ] 对选中尺寸调用原生 AlignDimensions，然后复用旧外侧尺寸分层规则，反馈调整视图/表格位置、常用比例与图幅。不能把局部自动排列当作全图无碰撞证明。
- [ ] 读取真实原生范围与显示数据，以保守文字边界检查，无法量测项留为视觉审核。执行失败最多三次有依据修复；预设候选搜索与失败重试分开记录。
- [ ] 保存重开后核对实际全体尺寸/PMI/注释/表格及模型引用；不能沿用旧 v1 的“新增尺寸数量必须恰等于计划数量”作为含导入标注的新验证规则。
- [ ] 运行 planner/layout 测试及原生代表例；检查一角/三角、单页、打印字号、关联与表格，再提交。

## 任务 8：一请求完成、验收、安装及 GitHub 同步

**文件：** `scripts/run.ps1`、`scripts/worker.ps1`、`scripts/verify_outputs.py`、`SKILL.md`、`README.md`、`examples/request.template.json`、`references/verification.md`、`SNAPSHOT.json`、根目录 `README.md`。

**接口：** Agent 按新 skill 自动完成 Inspect → grounded plan → Validate → Execute → Verify；用户不逐步骤确认。运行目录是 `internal/` + `deliverables/`，报告记录每阶段结果、源件摘要、文件身份、覆盖项和集中问题。

- [ ] 集成失败用例：错误活跃文档、错误配置、用户未保存更改、中断后已有结果、DWG成功但PDF失败；结果必须可复核且不假报成功。
- [ ] 跑板类密集孔、轴类台阶/孔深、支架槽/圆角/倒角，以及无法单页布局的失败例；检查 deliverables 只有 DWG/PDF。以真实导出结果做文字/符号/表格/视图视觉审核。
- [ ] 对代表性冻结PDF进行独立盲重建，冻结模型后再比较几何；记录首轮失败和修复，隔离不成立则该项不通过。
- [ ] 新技能前后行为测试，明确允许表格、只有 DWG/PDF、原生图内部保留及能力限制。执行全部离线回归、目标环境原生验收、技能校验、文件摘要及安装独立性检查。
- [ ] 备份同名安装目录，安装完整新 skill；旧 skill 保留兼容，避免将旧包描述成新主入口。首次安装验证真实新入口。
- [ ] 提交并同步 `solidworks-drawing-skill`：新包、MD、代码、测试和配置一起发布；核对远端提交及文件路径，给用户新 skill 名称、安装路径和 GitHub链接。同步成功前不宣称已完成。

## 完成标准与当前进度

2026-10-06 后续实施记录：新包已包含独立 MD、配置、示例与 PowerShell/C#/Python 代码。用户确认原模板后，采用保留 GB A3 图框、视图等比例放大和侧置孔表的布局。板件 DWG→eDrawings→PDF 结构验证通过，状态 REVIEW_REQUIRED；简单轴件原生长度/直径可见。支架关联壁厚验收仍失败，完整高级样件、局部视图、自动 DimXpert 方案和盲重建未通过。此候选包不等同于下面全部完成标准达成；发布与安装候选版不将未通过任务改写为完成。

任务 1 已完成：旧表格规则修正、既有离线/行为检查、文件摘要、文档和正确 GitHub仓库同步。任务 2–8 已部分实施：独立代码整合、原模板布局和板件 DWG/PDF 闭环已有实际验证；其余高级特征与完整验收仍按上述未勾选项推进。

最终完成要求：新包独立安装运行；两类技能的实际代码已归入一个入口；目标合成样例通过特征覆盖、源件保护、原生保存重开、动态布局、真实 DWG/PDF 及视觉检查；代表性盲重建已验收；失败例正确停止；本机安装与正确 GitHub仓库一致。缺少其中任一必要项则记录未完成，不以文档或文件存在代替验收。
