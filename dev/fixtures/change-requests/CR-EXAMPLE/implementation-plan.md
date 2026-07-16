# Implementation Plan: CR-EXAMPLE

> 由 Dev Agent 产出。实现待办事项 CRUD 接口。

## 技术方案

### 架构设计
采用标准三层架构：Router → Service → Repository，数据库使用 PostgreSQL + SQLAlchemy。

### 技术选型
| 组件 | 选型 | 理由 |
|---|---|---|
| Web 框架 | FastAPI | 自动生成 OpenAPI 文档，async 支持 |
| ORM | SQLAlchemy 2.0 | 成熟稳定，类型支持好 |
| 数据库 | PostgreSQL 15 | 事务支持、JSON 字段、性能优秀 |
| 迁移工具 | Alembic | SQLAlchemy 生态标配 |

### 核心流程

```
客户端请求 → FastAPI Router → TodoService → TodoRepository → PostgreSQL
                  ↓
            Pydantic 校验
                  ↓
            统一响应格式
```

## 实施步骤

### Step 1: 数据模型
- [x] 创建 `src/models/todo.py` — Todo ORM 模型
- [x] 创建 Alembic 迁移：`create_todos_table`
- [x] 字段：id, title, description, status, due_date, created_at, updated_at, deleted_at

### Step 2: Schema 层
- [x] 创建 `src/schemas/todo.py` — Pydantic 请求/响应模型
- [x] TodoCreate, TodoUpdate, TodoResponse, TodoListResponse

### Step 3: Service 层
- [x] 创建 `src/services/todo_service.py`
- [x] 实现 create, list, get, update, delete 方法
- [x] 软删除逻辑（设置 deleted_at，查询时排除）

### Step 4: API 层
- [x] 创建 `src/api/todos.py` — 路由定义
- [x] POST /api/todos — 创建
- [x] GET /api/todos — 列表（分页+筛选）
- [x] PATCH /api/todos/{id} — 更新
- [x] DELETE /api/todos/{id} — 删除

### Step 5: 测试
- [x] 单元测试：TodoService 逻辑
- [x] 集成测试：API 端到端
- [x] 性能测试：P95 < 100ms 验证

## 文件清单

| 文件 | 类型 | 说明 |
|---|---|---|
| `src/models/todo.py` | 新增 | ORM 模型 |
| `src/schemas/todo.py` | 新增 | Pydantic Schema |
| `src/services/todo_service.py` | 新增 | 业务逻辑 |
| `src/api/todos.py` | 新增 | 路由定义 |
| `src/main.py` | 修改 | 注册路由 |
| `tests/test_todos.py` | 新增 | 测试用例 |
| `alembic/versions/001_create_todos.py` | 新增 | 数据库迁移 |

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|---|---|---|
| offset 分页大数据量慢 | 查询延迟增加 | 当前数据量小，后续可改 cursor 分页 |
