# 架构设计: CR-EXAMPLE

> 第二道人工门禁。编码前必须有架构设计并经人工确认。

## CR-ID
CR-EXAMPLE

## 1. 模块拆分与目录结构

| 模块 | 职责 | 文件落点 |
|---|---|---|
| API Router | 暴露待办事项 CRUD 路由 | `src/api/todos.py` |
| Service | 封装业务规则、软删除与分页策略 | `src/services/todo_service.py` |
| Repository/Model | 持久化 Todo 数据 | `src/models/todo.py` |
| Schema | 请求和响应校验 | `src/schemas/todo.py` |
| Tests | 覆盖 CRUD、错误分支和性能预算 | `tests/test_todos.py` |

## 2. 数据流与状态管理

客户端请求进入 FastAPI Router，Router 使用 Pydantic Schema 完成边界校验后调用 TodoService。TodoService 通过 Repository/ORM 读写 PostgreSQL，并返回统一响应对象。软删除通过 `deleted_at` 状态字段表达，列表查询默认排除已删除记录。

## 3. 接口封装与依赖

HTTP 接口集中在 `src/api/todos.py`，业务逻辑集中在 `src/services/todo_service.py`，数据库访问封装在模型/Repository 层。外部依赖为 FastAPI、SQLAlchemy、Alembic、PostgreSQL，不在路由层直接拼接 SQL。

## 4. 异常处理与验证策略

- title 为空返回 422，由 Schema 层验证。
- id 不存在返回 404，由 Service 层统一处理。
- 删除使用软删除，重复查询不返回已删除项。
- 验证通过单元测试、集成测试、OpenAPI 检查和 P95 性能预算。

## 5. 设计分块到实现映射

| block | 目标文件 | 目标组件 | 数据字段 | 交互 | 设计源证据 |
|---|---|---|---|---|---|
| 创建待办 | `src/api/todos.py` | `create_todo` | title, description, due_date | POST /api/todos | AC-1 |
| 查询列表 | `src/api/todos.py` | `list_todos` | page, size, status | GET /api/todos | AC-2 |
| 更新待办 | `src/api/todos.py` | `update_todo` | partial TodoUpdate | PATCH /api/todos/{id} | AC-3 |
| 软删除 | `src/api/todos.py` | `delete_todo` | deleted_at | DELETE /api/todos/{id} | AC-4 |

## 6. 直读计划（direct-read plan）

本 CR 为 API 示例，无 UI 视觉常量。涉及 API 响应字段和错误状态时，以 acceptance-spec.md 与 traceability.yml 为设计源证据。

## 7. 平台差异与验证策略（如涉及多端）

N/A。该 CR 为后端 API 示例，不涉及移动端或多端 UI 差异。

## ArchitectureGate 检查点
- [x] 模块拆分/目录结构明确
- [x] 数据流与状态管理清晰
- [x] 接口封装与依赖列全
- [x] 异常处理与验证策略明确
- [x] 每个设计分块有实现映射
- [x] 直读计划列出关键证据源
- [x] 无残留模板变量

**ArchitectureGate 状态**：READY
**人工确认**：已确认（技术负责人 / 2026-06-21）
