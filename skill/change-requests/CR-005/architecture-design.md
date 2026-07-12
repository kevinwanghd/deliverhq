# 架构设计: Productize DeliverHQ Packaging and Metadata

## CR-ID
CR-005

## 1. 模块拆分与目录结构

| 模块 | 职责 | 文件落点 |
|---|---|---|
| Python Package | 稳定包命名空间与共享实现 | `skill/deliverhq/` |
| Capability Registry | schema 校验、加载、Markdown 渲染 | `skill/deliverhq/capabilities.py`, `skill/capabilities.yml` |
| Compatibility Scripts | 保持现有命令和 import | `skill/scripts/capability_registry.py`, `capability_tiers.py`, runtime/routing wrappers |
| Package Policy | npm 发布白名单与预算测试 | `package.json`, `.npmignore`, `tests/test_packaging.py` |

## 2. 数据流与状态管理

人工只编辑 `capabilities.yml`。Registry loader 校验后供 capability tiers 使用，renderer 只替换 `CAPABILITY-MATRIX.md` 中受标记管理的表格区域。CI 的 check 模式比较渲染结果与已提交 Markdown，发现漂移即失败。

npm packlist 由 `package.json.files` 和 `.npmignore` 共同控制；测试解析 `npm pack --dry-run --json` 的结构化输出并验证预算和禁止路径。

## 3. 接口封装与依赖

- `deliverhq` 包仅依赖 Python 标准库与现有 PyYAML。
- `capabilities.py` 不依赖 scripts 层。
- scripts 兼容入口可以导入 `deliverhq`，包不得反向导入 scripts。
- runtime/routing 实现移动到包内；旧脚本只 re-export 并保持 CLI 行为。
- Markdown 是生成视图，不再作为能力数据输入。

## 4. 异常处理与验证策略

- YAML 缺字段、重复 ID、非法枚举、脚本路径不存在均返回明确错误。
- renderer 只更新显式标记区域；标记缺失时 fail-closed。
- npm 预算或禁止路径命中时测试列出具体文件。
- 每阶段运行 registry tests、packaging tests、17 项模块测试和 37 项 selftest。

## 5. 测试接缝 (Test Seams)

| 接缝 | 位置 | 覆盖范围 | 是否复用现有 | 测试类型 |
|---|---|---|---|---|
| Registry public interface | `tests/test_capability_registry.py` | schema、确定性渲染、漂移、错误输入 | 否 | 单元/契约 |
| npm tarball manifest | `tests/test_packaging.py` | 文件预算、体积预算、禁止路径、必要文件 | 否 | 集成 |
| Existing public entrypoints | 现有 test suites | Python/CLI 向后兼容 | 是 | 集成 |

**接缝选择理由**：registry 和 tarball 是本批真正的外部产物；内部 helper 不单独建立更多测试接缝。

## 6. 设计分块到实现映射

| block | 目标文件 | 目标组件 | 数据字段 | 交互 | 设计源证据 |
|---|---|---|---|---|---|
| Registry schema | `skill/capabilities.yml`, `skill/deliverhq/capabilities.py` | loader/validator | capability fields | YAML load | AC 场景 1/2 |
| Generated matrix | `CAPABILITY-MATRIX.md`, `capability_registry.py` | renderer/check | Markdown table | CLI | AC 场景 1 |
| Package namespace | `skill/deliverhq/runtime.py`, `routing.py` | compatibility exports | runtime results/routes | Python imports | AC 场景 4 |
| npm policy | `.npmignore`, `tests/test_packaging.py` | tarball audit | files/sizes | npm pack JSON | AC 场景 3 |

## 7. 直读计划（direct-read plan）

N/A。本 CR 不涉及 UI；数据源为 YAML registry 与 npm pack JSON。

## 8. 平台差异与验证策略

Windows/Linux 均通过现有 GitHub matrix；路径比较统一转为 POSIX `/`，临时 tarball 和 JSON 使用平台无关 API。

## ArchitectureGate 检查点

- [x] 模块拆分/目录结构明确
- [x] 数据流与状态管理清晰
- [x] 接口封装与依赖列全
- [x] 异常处理与验证策略明确
- [x] 测试接缝选择合理
- [x] 每个设计分块有实现映射
- [x] 直读计划已说明不适用
- [x] 无残留模板变量

**ArchitectureGate 状态**：READY
**人工确认**：已确认（Kevin / 2026-07-12）
